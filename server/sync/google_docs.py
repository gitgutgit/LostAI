"""Google Docs 동기화 (P1). author: Mal-Mi-Jal

방식: 로컬 Doc(doc_key)마다 Google Doc 안의 **전용 탭 하나**(탭 제목 = Doc.title)를 통째로 미러링한다.
- 기존 탭(사람이 쓴 계획서 등)은 건드리지 않는다. 전용 탭이 없으면 `addDocumentTab`으로 만든다.
- 섹션 제목 = 제목 2, 항목 = 글머리 기호. 이번 change가 바꾼 항목은 노란색, 끝에 회색으로 "· 누가".
- push 1회 = batchUpdate 1회 (지우기 → 쓰기 → 서식). 탭 위치·길이는 캐시, 시작·리셋·실패 뒤에만 조회.
  사람이 전용 탭을 직접 고치면 다음 전체 동기화(시작·리셋) 때 바로잡힌다.
- Docs 인덱스는 UTF-16 코드 단위다 (이모지는 2칸) → `_u16`.

호출은 Outbox 워커 하나에서만 온다 (동시 호출 금지, docs/ARCHITECTURE.md 3-5).
확인: `uv run python -m server.sync.google_docs --demo-change` (.env GOOGLE_DOC_ID 문서에 시드를 미러링)
"""
from __future__ import annotations

import os
from typing import Any

from server.model.docs import Doc, DocState
from server.sync import google_auth

IMPLEMENTED = True  # /api/links 가 화면 버튼 상태를 정할 때 본다

HIGHLIGHT = {"color": {"rgbColor": {"red": 1.0, "green": 0.95, "blue": 0.6}}}
GRAY = {"color": {"rgbColor": {"red": 0.55, "green": 0.55, "blue": 0.55}}}

# 항목 앵커("notes/s_risk/i_12") → 누가 (applied에서 넣고 reverted에서 뺀다)
_item_who: dict[str, tuple[str, str]] = {}  # anchor → (who, change_id)
# (문서 ID, 탭 제목) → tabId
_tabs: dict[tuple[str, str], str] = {}
# (문서 ID, 탭 제목) → 마지막으로 쓴 뒤 탭 본문 endIndex
_tab_end: dict[tuple[str, str], int] = {}


def enabled() -> bool:
    from server.sync import google_source  # 원본 모드는 화면에서 고른 문서로도 켜진다 (.env에 ID가 없어도)
    return bool(os.getenv("GOOGLE_DOC_ID")) or google_source.active()


def document_id() -> str:
    return google_auth.parse_id(os.environ["GOOGLE_DOC_ID"])


def _u16(s: str) -> int:
    return len(s.encode("utf-16-le")) // 2


# ---------------------------------------------------------------- 순수 변환 (네트워크 없음)

def doc_keys_in(change: dict[str, Any]) -> list[str]:
    keys: list[str] = []
    for d in change.get("diff") or []:
        if d.get("kind") in ("item", "section", "heading"):
            k = d["anchor"].split("/")[0]
            if k not in keys:
                keys.append(k)
    return keys


def changed_items(change: dict[str, Any], key: str) -> set[str]:
    return {d["anchor"] for d in change.get("diff") or []
            if d.get("kind") == "item" and d.get("after") and d["anchor"].split("/")[0] == key}


def record_who(event_type: str, change: dict[str, Any]) -> None:
    cid = change.get("change_id", "")
    anchors = [d["anchor"] for d in change.get("diff") or [] if d.get("kind") == "item"]
    if event_type == "change.reverted":
        for a in anchors:
            if _item_who.get(a, ("", ""))[1] == cid:
                _item_who.pop(a, None)
    else:
        who = change.get("requested_by") or "?"
        for a in anchors:
            _item_who[a] = (who, cid)


def layout(doc: Doc, key: str) -> tuple[str, list[dict[str, Any]]]:
    """탭에 넣을 글 전체와 문단 목록 [{start, end, kind: heading|item|empty, anchor?, who_start?}].
    인덱스는 탭 본문 시작(1) 기준 UTF-16."""
    text, paras, pos = "", [], 1

    def add(line: str, kind: str, **extra: Any) -> None:
        nonlocal text, pos
        line = line.replace("\n", " ") + "\n"
        paras.append({"start": pos, "end": pos + _u16(line), "kind": kind, **extra})
        text += line
        pos += _u16(line)

    for sec in doc.sections:
        add(sec.heading, "heading")
        if not sec.items:
            add("(없음)", "empty")
        for it in sec.items:
            anchor = f"{key}/{sec.section_id}/{it.item_id}"
            body = it.text + (f" — 담당 {it.meta['owner']}" if it.meta.get("owner") else "")
            who = _item_who.get(anchor, (None, None))[0]
            line = body + (f"  · {who}" if who else "")
            add(line, "item", anchor=anchor, who_start=(pos + _u16(body)) if who else None)
    return text, paras


def mirror_requests(doc: Doc, key: str, tab_id: str, tab_end: int, highlight: set[str]) -> list[dict[str, Any]]:
    """전용 탭을 doc과 똑같이 만드는 batchUpdate 요청들."""
    text, paras = layout(doc, key)
    reqs: list[dict[str, Any]] = []
    if tab_end > 2:  # 마지막 줄바꿈 하나는 지울 수 없다
        reqs.append({"deleteContentRange": {"range": {"startIndex": 1, "endIndex": tab_end - 1, "tabId": tab_id}}})
    if not text:
        return reqs
    text = text[:-1]  # 탭에 남은 마지막 줄바꿈을 마지막 문단으로 쓴다
    reqs.append({"insertText": {"location": {"index": 1, "tabId": tab_id}, "text": text}})
    whole = {"startIndex": 1, "endIndex": paras[-1]["end"], "tabId": tab_id}
    reqs += [
        {"deleteParagraphBullets": {"range": whole}},
        {"updateParagraphStyle": {"range": whole, "paragraphStyle": {"namedStyleType": "NORMAL_TEXT"},
                                  "fields": "namedStyleType"}},
        {"updateTextStyle": {"range": whole, "textStyle": {}, "fields": "backgroundColor,foregroundColor,italic"}},
    ]
    for p in paras:
        rng = {"startIndex": p["start"], "endIndex": p["end"], "tabId": tab_id}
        if p["kind"] == "heading":
            reqs.append({"updateParagraphStyle": {"range": rng, "paragraphStyle": {"namedStyleType": "HEADING_2"},
                                                  "fields": "namedStyleType"}})
        elif p["kind"] == "empty":
            reqs.append({"updateTextStyle": {"range": {**rng, "endIndex": p["end"] - 1},
                                             "textStyle": {"foregroundColor": GRAY, "italic": True},
                                             "fields": "foregroundColor,italic"}})
        else:
            reqs.append({"createParagraphBullets": {"range": rng, "bulletPreset": "BULLET_DISC_CIRCLE_SQUARE"}})
            if p["anchor"] in highlight and p["end"] - 1 > p["start"]:
                reqs.append({"updateTextStyle": {"range": {**rng, "endIndex": p["end"] - 1},
                                                 "textStyle": {"backgroundColor": HIGHLIGHT},
                                                 "fields": "backgroundColor"}})
            if p.get("who_start"):
                reqs.append({"updateTextStyle": {"range": {**rng, "startIndex": p["who_start"], "endIndex": p["end"] - 1},
                                                 "textStyle": {"foregroundColor": GRAY}, "fields": "foregroundColor"}})
    return reqs


# ---------------------------------------------------------------- Google 호출

def _api():
    return google_auth.service("docs", "v1").documents()


def _flatten(tabs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for t in tabs:
        out.append(t)
        out += _flatten(t.get("childTabs", []))
    return out


def _tab(did: str, title: str) -> tuple[str, int]:
    """(tabId, 탭 본문 endIndex). 없으면 탭을 만든다."""
    fields = "tabs(tabProperties(tabId,title),documentTab(body(content(endIndex))),childTabs)"
    tabs = _flatten(_api().get(documentId=did, includeTabsContent=True, fields=fields).execute().get("tabs", []))
    for t in tabs:
        if t["tabProperties"]["title"] == title:
            _tabs[(did, title)] = t["tabProperties"]["tabId"]
            content = t["documentTab"]["body"]["content"]
            return t["tabProperties"]["tabId"], content[-1]["endIndex"]
    res = _api().batchUpdate(documentId=did, body={"requests": [
        {"addDocumentTab": {"tabProperties": {"title": title}}}]}).execute()
    tab_id = res["replies"][0]["addDocumentTab"]["tabProperties"]["tabId"]
    _tabs[(did, title)] = tab_id
    return tab_id, 2


def mirror(state: DocState, key: str, highlight: set[str] | None = None, fresh: bool = False) -> None:
    """전용 탭은 우리만 쓰므로 마지막에 쓴 길이를 기억해 조회를 건너뛴다 (push 1회 = Google 호출 1회).
    실패하면 기억을 버린다 → Outbox 재시도 때 다시 조회. 시작·리셋 전체 동기화(fresh)는 항상 조회한다."""
    doc = state.doc(key)
    did = document_id()
    cached = None if fresh else _tab_end.get((did, doc.title))
    if cached and (did, doc.title) in _tabs:
        tab_id, end = _tabs[(did, doc.title)], cached
    else:
        tab_id, end = _tab(did, doc.title)
    reqs = mirror_requests(doc, key, tab_id, end, highlight or set())
    if not reqs:
        return
    try:
        _api().batchUpdate(documentId=did, body={"requests": reqs}).execute()
    except Exception:
        _tab_end.pop((did, doc.title), None)
        raise
    text = next((r["insertText"]["text"] for r in reqs if "insertText" in r), "")
    _tab_end[(did, doc.title)] = 1 + _u16(text) + 1  # 본문 시작 1 + 글 + 남겨 둔 마지막 줄바꿈


def push(state: DocState, event_type: str, change: dict[str, Any]) -> None:
    """event_type: change.applied | change.reverted. 실패하면 예외를 올린다 (Outbox가 재시도)."""
    from server.sync import google_source
    if google_source.active():  # 원본 모드: 바뀐 문단만 원본 탭에 직접
        google_source.push_doc(event_type, change)
        return
    record_who(event_type, change)
    for key in doc_keys_in(change):
        if key in state.docs and isinstance(state.docs[key], Doc):
            hl = changed_items(change, key) if event_type == "change.applied" else set()
            mirror(state, key, hl)


def push_all(state: DocState) -> list[str]:
    """모든 Doc을 미러링 (서버 시작·리셋 때). 새 방이므로 이전 출처도 지운다. 원본 모드에서는 안 한다."""
    from server.sync import google_source
    if google_source.active():
        return []
    _item_who.clear()
    keys = [k for k, d in state.docs.items() if isinstance(d, Doc)]
    for k in keys:
        mirror(state, k, fresh=True)
    return keys


def tab_id_for(title: str) -> str | None:
    """화면 바로가기용 (캐시만, Google 호출 없음)."""
    return _tabs.get((document_id(), title)) if enabled() else None


if __name__ == "__main__":
    import argparse
    import sys

    from dotenv import load_dotenv

    from server.model.docs import load_seed
    from server.ops.engine import apply_op

    load_dotenv(google_auth.ROOT / ".env")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(description="시드 Doc을 GOOGLE_DOC_ID 문서의 전용 탭에 미러링")
    p.add_argument("--seed", default=os.getenv("SEED", "sprint"))
    p.add_argument("--demo-change", action="store_true", help="add_decision 하나를 적용해 하이라이트·출처까지 확인")
    a = p.parse_args()
    if not enabled():
        sys.exit("GOOGLE_DOC_ID 없음 → `python -m server.sync.google_auth --doc <URL> --save`")
    st = load_seed(a.seed)
    print("미러링:", push_all(st))
    if a.demo_change:
        op = {"op": "add_decision", "text": "출시를 다음 주로 연기"}
        ch = {"change_id": "ch_demo", "requested_by": "Mal-Mi-Jal", "reason": "Mal-Mi-Jal: 동기화 테스트",
              "ops": [op], "diff": apply_op(st, op)}
        push(st, "change.applied", ch)
        print("demo change applied:", ch["diff"][0]["anchor"])
