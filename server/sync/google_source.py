"""원본 문서 모드 (`SEED=google`). author: Mal-Mi-Jal

팀이 실제로 쓰는 Google Sheet 첫 탭 / Google Doc 첫 탭을 **회의 시작 상태**로 불러오고,
회의 중 바뀐 칸·문단만 **원본에 직접** 고친다. 통째로 덮어쓰지 않는다.

- 불러오기 `pull_baseline()`: 서버 시작 때 1회 (Outbox 시작 전이라 동시 호출 없음)
  - Sheet → doc_key "board": 1행 = 열 이름, 2행부터 행 (row_id `r_g<원래 행 번호>`)
  - Doc → doc_key "notes": TITLE = 문서 제목, HEADING = 섹션, 그 아래 글 있는 문단 = 항목
    ('- ' 머리표는 떼고 기억했다가 쓸 때 다시 붙인다). '리스크' 섹션은 risks 바인딩(s_risk).
    원본에 없는 '결정 사항'·'액션'은 로컬에만 빈 섹션으로 두고, 처음 기록될 때 문서 끝에 추가한다.
- 쓰기 `push_sheet()` / `push_doc()`: change의 diff를 순서대로 원본 연산으로 바꾼다.
  - 행·항목 위치는 **Google 쪽 순서 모델**(`_rows`, `_sections`)로 찾는다. Outbox가 FIFO라 모델과 원본이 같이 움직인다.
  - 이번 change 칸·문단은 노란색, 직전 change의 노란색은 지운다. 시트는 셀 메모, 문서는 끝에 회색 '· 누가'.
  - Doc은 문단 위치가 글자 수에 따라 움직이므로 push마다 탭을 조회해 위치를 다시 잡는다.
- 복원 `restore()` (리셋): 회의 중 적용된 change를 역순으로 되돌린 뒤(호출은 Outbox가 함),
  우리가 끝에 추가한 빈 섹션을 지우고 하이라이트를 지운다 → 회의 시작 전 원본으로.

원본 구조를 사람이 회의 중 직접 바꾸면(섹션 추가 등) 위치가 어긋난다 → 검사해서 sync.failed로 알린다.
"""
from __future__ import annotations

import copy
import json
import os
import re
from pathlib import Path
from typing import Any

from server.model.docs import Doc, DocState, Item, Row, Section, Sheet
from server.sync import google_auth

HIGHLIGHT_SHEET = {"red": 1.0, "green": 0.95, "blue": 0.6}
HIGHLIGHT_DOC = {"color": {"rgbColor": {"red": 1.0, "green": 0.95, "blue": 0.6}}}
GRAY = {"color": {"rgbColor": {"red": 0.55, "green": 0.55, "blue": 0.55}}}
BULLET_RE = re.compile(r"^\s*([-•·*]\s+)")
BINDINGS = {"리스크": ("s_risk", "risks"), "위험": ("s_risk", "risks"), "결정 사항": ("s_dec", "decisions"),
            "결정": ("s_dec", "decisions"), "액션": ("s_act", "actions"), "할 일": ("s_act", "actions"),
            "메모": ("s_memo", "notes")}
EXTRA_SECTIONS = [("s_dec", "결정 사항", "decisions"), ("s_act", "액션", "actions")]

SHEET_KEY, DOC_KEY = "board", "notes"


class SourceState:
    def __init__(self) -> None:
        self.active = False
        self.sheet_id: str | None = None     # 스프레드시트 ID
        self.sheet_tab: tuple[str, int] | None = None  # (탭 제목, sheetId)
        self.doc_id: str | None = None
        self.doc_tab: str | None = None      # tabId
        self.baseline: DocState | None = None
        # Google 쪽 순서 모델
        self.rows: list[str] = []            # row_id 순서 (헤더 제외)
        self.cols: list[str] = []
        self.numeric_cols: set[str] = set()  # 원본에서 값이 숫자인 열 → "3" 같은 글도 숫자로 쓴다
        self.sections: list[dict[str, Any]] = []  # {section_id, in_google, created, items: [item_id]}
        self.prefix: dict[str, str] = {}     # item_id → '- ' 같은 머리표
        self.hl_cells: set[tuple[str, str]] = set()
        self.hl_items: set[str] = set()


S = SourceState()


def active() -> bool:
    return S.active


# ================================================================ 불러오기

def _sheets():
    return google_auth.service("sheets", "v4").spreadsheets()


def _docs():
    return google_auth.service("docs", "v1").documents()


def _para_text(p: dict[str, Any]) -> str:
    return "".join(r.get("textRun", {}).get("content", "") for r in p.get("elements", [])).rstrip("\n")


def _first_doc_tab(did: str) -> dict[str, Any]:
    d = _docs().get(documentId=did, includeTabsContent=True).execute()
    return d["tabs"][0]


def _doc_paragraphs(tab: dict[str, Any]) -> list[dict[str, Any]]:
    out = []
    for el in tab["documentTab"]["body"]["content"]:
        p = el.get("paragraph")
        if p is None:
            continue
        out.append({"start": el["startIndex"], "end": el["endIndex"],
                    "style": p.get("paragraphStyle", {}).get("namedStyleType", "NORMAL_TEXT"),
                    "text": _para_text(p)})
    return out


def parse_doc(paras: list[dict[str, Any]]) -> tuple[str, list[dict[str, Any]]]:
    """문단 목록 → (문서 제목, [{heading, heading_para, items: [para]}]). 빈 문단은 항목이 아니다."""
    title, sections = "", []
    for p in paras:
        if p["style"] == "TITLE" and not sections:
            title = title or p["text"]
        elif p["style"].startswith("HEADING"):
            sections.append({"heading": p["text"], "heading_para": p, "items": []})
        elif sections and p["text"].strip():
            sections[-1]["items"].append(p)
    return title, sections


def choice_file() -> Path:
    """화면에서 고른 문서 기록 (results/ → gitignore). 문서 ID라 출력·커밋하지 않는다."""
    return Path(os.getenv("EVENT_LOG_DIR", "results")) / "google_source_choice.json"


class SourceError(ValueError):
    """이 문서는 회의 원본으로 못 쓴다 (화면에 그대로 보여 줄 문구)."""


def chosen_ids() -> tuple[str, str]:
    """회의 원본 (sheet, doc) ID. 화면에서 고른 게 있으면 그것, 없으면 .env."""
    try:
        c = json.loads(choice_file().read_text(encoding="utf-8"))
        return c["sheet_id"], c["doc_id"]
    except (OSError, ValueError, KeyError):
        return google_auth.parse_id(os.environ["GOOGLE_SHEET_ID"]), google_auth.parse_id(os.environ["GOOGLE_DOC_ID"])


def save_choice(sheet_id: str, doc_id: str) -> None:
    choice_file().parent.mkdir(parents=True, exist_ok=True)
    choice_file().write_text(json.dumps({"sheet_id": sheet_id, "doc_id": doc_id}), encoding="utf-8")


def clear_choice() -> None:
    """개인 계정 문서를 고르면 지운다: 그 토큰은 메모리에만 있어 다시 켜면 못 연다 → .env 기본 원본으로 시작."""
    choice_file().unlink(missing_ok=True)


def pull_baseline() -> DocState:
    """원본 두 문서를 읽어 회의 시작 상태를 만든다 (서버 시작 때)."""
    global S
    S = load(*chosen_ids())
    return S.baseline.model_copy(deep=True)  # type: ignore[union-attr]


def load(sheet_id: str, doc_id: str) -> SourceState:
    """두 문서를 읽어 새 SourceState를 만든다. 지금 쓰는 S는 건드리지 않는다 (문서 바꾸기: 복원이 끝난 뒤 commit).
    못 쓰는 문서면 SourceError. Outbox 워커 안에서만 부른다 (Google 동시 호출 금지)."""
    global S
    prev, S = S, SourceState()
    try:
        _pull(sheet_id, doc_id)
        return S
    finally:
        S = prev


def commit(st: SourceState) -> None:
    global S
    S = st


def _pull(sheet_id: str, doc_id: str) -> None:
    S.sheet_id, S.doc_id = sheet_id, doc_id
    docs: dict[str, Any] = {}

    meta = _sheets().get(spreadsheetId=S.sheet_id, fields="properties.title,sheets.properties(sheetId,title)").execute()
    tab = meta["sheets"][0]["properties"]
    S.sheet_tab = (tab["title"], tab["sheetId"])
    values = _sheets().values().get(spreadsheetId=S.sheet_id, range=f"'{tab['title']}'",
                                    valueRenderOption="UNFORMATTED_VALUE").execute().get("values", [])
    header = [str(h) for h in (values[0] if values else [])]
    if not any(h.strip() for h in header):
        raise SourceError("시트 첫 줄(열 이름)이 비어 있어요. 첫 줄에 '작업, 담당, 상태' 같은 열 이름을 넣어 주세요.")
    if len(set(header)) != len(header) or any(not h.strip() for h in header):
        raise SourceError("시트 첫 줄 열 이름이 비었거나 겹쳐요. 열 이름을 하나씩 다르게 채워 주세요.")
    rows = []
    for i, line in enumerate(values[1:], start=2):
        if not any(str(v).strip() for v in line):
            continue
        rows.append(Row(row_id=f"r_g{i}", cells={c: line[j] for j, c in enumerate(header) if j < len(line) and line[j] != ""}))
    docs[SHEET_KEY] = Sheet(title=meta["properties"]["title"], columns=header, rows=rows)
    S.cols, S.rows = header, [r.row_id for r in rows]
    S.numeric_cols = {c for c in header if any(isinstance(r.cells.get(c), (int, float)) and not isinstance(r.cells.get(c), bool) for r in rows)}

    t = _first_doc_tab(S.doc_id)
    if any("table" in el for el in t["documentTab"]["body"]["content"]):
        raise SourceError("문서에 표가 있어요. 표가 있으면 위치 계산이 틀어질 수 있어 회의 원본으로 못 써요.")
    S.doc_tab = t["tabProperties"]["tabId"]
    title, parsed = parse_doc(_doc_paragraphs(t))
    sections, S.sections, S.prefix, used = [], [], {}, set()
    for n, ps in enumerate(parsed, start=1):
        sid, binding = BINDINGS.get(ps["heading"].strip(), (f"s_g{n}", None))
        if sid in used:
            sid, binding = f"s_g{n}", None
        used.add(sid)
        items = []
        for m, p in enumerate(ps["items"], start=1):
            iid = f"i_g{n}_{m}"
            mt = BULLET_RE.match(p["text"])
            S.prefix[iid] = mt.group(1) if mt else ""
            items.append(Item(item_id=iid, text=p["text"][mt.end():] if mt else p["text"]))
        sections.append(Section(section_id=sid, heading=ps["heading"], binding=binding, items=items))
        S.sections.append({"section_id": sid, "in_google": True, "created": False, "items": [i.item_id for i in items]})
    for sid, heading, binding in EXTRA_SECTIONS:
        if sid not in used:
            sections.append(Section(section_id=sid, heading=heading, binding=binding))
            S.sections.append({"section_id": sid, "in_google": False, "created": False, "items": []})
    docs[DOC_KEY] = Doc(title=title or "회의 노트", sections=sections)

    S.baseline = DocState(docs=docs)
    S.active = True
    S.hl_cells, S.hl_items = set(), set()


# ================================================================ 시트

def _cell_value(v: Any, col: str | None = None) -> dict[str, Any]:
    if isinstance(v, str) and col in S.numeric_cols and re.fullmatch(r"-?\d+(\.\d+)?", v.strip()):
        v = float(v) if "." in v else int(v)
    if v is None or v == "":
        return {}
    if isinstance(v, bool):
        return {"boolValue": v}
    if isinstance(v, (int, float)):
        return {"numberValue": v}
    return {"stringValue": str(v)}


def _cell_req(row_id: str, col: str, *, value: Any = None, set_value: bool = False,
              note: str | None = None, highlight: bool | None = None) -> dict[str, Any]:
    r, c = S.rows.index(row_id) + 1, S.cols.index(col)
    cell: dict[str, Any] = {}
    fields = []
    if set_value:
        cell["userEnteredValue"] = _cell_value(value, col)
        fields.append("userEnteredValue")
    if note is not None:
        cell["note"] = note
        fields.append("note")
    if highlight is not None:
        if highlight:
            cell["userEnteredFormat"] = {"backgroundColor": HIGHLIGHT_SHEET}
        fields.append("userEnteredFormat.backgroundColor")  # 값 없이 필드만 → 기본(채우기 없음)
    return {"updateCells": {"start": {"sheetId": S.sheet_tab[1], "rowIndex": r, "columnIndex": c},
                            "rows": [{"values": [cell]}], "fields": ",".join(fields)}}


def _note(change: dict[str, Any]) -> str:
    who, why = change.get("requested_by") or "?", change.get("reason") or ""
    if why.startswith(f"{who}: "):
        why = why[len(who) + 2:]
    return f"{who} · {why}".strip(" ·")


def sheet_requests(event_type: str, change: dict[str, Any]) -> list[dict[str, Any]]:
    """순서 모델을 갱신하면서 원본 시트 요청을 만든다 (순수 함수 + 모델 갱신)."""
    reqs: list[dict[str, Any]] = []
    # 직전 하이라이트 지우기 (아직 있는 행만)
    for row_id, col in sorted(S.hl_cells):
        if row_id in S.rows:
            reqs.append(_cell_req(row_id, col, highlight=False))
    S.hl_cells = set()
    reverted = event_type == "change.reverted"
    diffs = [d for d in change.get("diff") or [] if d["kind"] in ("cell", "row") and d["anchor"].startswith(SHEET_KEY + "/")]
    note = _note(change)
    for d in (reversed(diffs) if reverted else diffs):
        parts = d["anchor"].split("/")
        before, after = (d["after"], d["before"]) if reverted else (d["before"], d["after"])
        if d["kind"] == "cell":
            row_id, col = parts[1], parts[2]
            if col not in S.cols:
                raise RuntimeError(f"원본에 없는 열: {col}")
            reqs.append(_cell_req(row_id, col, value=after, set_value=True,
                                  note="" if reverted else note, highlight=not reverted))
            if not reverted:
                S.hl_cells.add((row_id, col))
        elif before is None:  # 행 생김
            idx = min(d.get("index", len(S.rows)), len(S.rows))
            S.rows.insert(idx, parts[1])
            reqs.append({"insertDimension": {"range": {"sheetId": S.sheet_tab[1], "dimension": "ROWS",
                                                        "startIndex": idx + 1, "endIndex": idx + 2},
                                              "inheritFromBefore": True}})
            for col, v in (after.get("cells") or {}).items():
                if col in S.cols:
                    reqs.append(_cell_req(parts[1], col, value=v, set_value=True,
                                          note="" if reverted else note, highlight=not reverted))
                    if not reverted:
                        S.hl_cells.add((parts[1], col))
        else:  # 행 없어짐
            idx = S.rows.index(parts[1])
            reqs.append({"deleteDimension": {"range": {"sheetId": S.sheet_tab[1], "dimension": "ROWS",
                                                        "startIndex": idx + 1, "endIndex": idx + 2}}})
            S.rows.pop(idx)
    return reqs


def push_sheet(event_type: str, change: dict[str, Any]) -> None:
    rows_before, hl_before = list(S.rows), set(S.hl_cells)
    try:
        reqs = sheet_requests(event_type, change)
        if reqs:
            _sheets().batchUpdate(spreadsheetId=S.sheet_id, body={"requests": reqs}).execute()
    except Exception:
        S.rows, S.hl_cells = rows_before, hl_before  # 재시도할 수 있게 모델을 되돌린다
        raise


# ================================================================ 문서

def _sec(section_id: str) -> dict[str, Any]:
    for s in S.sections:
        if s["section_id"] == section_id:
            return s
    raise RuntimeError(f"모르는 섹션: {section_id}")


def _locate(paras: list[dict[str, Any]]) -> dict[str, Any]:
    """현재 탭 문단 ↔ 순서 모델 연결. {section_id: {heading_para, items: {item_id: para}}, 'end': 본문 끝}"""
    _, parsed = parse_doc(paras)
    in_google = [s for s in S.sections if s["in_google"]]
    if len(parsed) != len(in_google) or any(len(p["items"]) != len(s["items"]) for p, s in zip(parsed, in_google)):
        raise RuntimeError("원본 Doc 구조가 회의 중 바뀜 (섹션·문단 수 불일치) → 리셋 또는 서버 재시작 필요")
    out: dict[str, Any] = {"end": paras[-1]["end"], "paras": paras}
    for p, s in zip(parsed, in_google):
        out[s["section_id"]] = {"heading_para": p["heading_para"], "items": dict(zip(s["items"], p["items"]))}
    return out


def _item_line(item: dict[str, Any], who: str | None) -> tuple[str, int]:
    """(문단 글, '· 누가'가 시작하는 위치(UTF-16) 또는 -1)."""
    prefix = S.prefix.get(item["item_id"], "- ")
    body = prefix + item["text"] + (f" — 담당 {item['meta']['owner']}" if (item.get("meta") or {}).get("owner") else "")
    if not who:
        return body, -1
    return body + f"  · {who}", _u16(body)


def _u16(s: str) -> int:
    return len(s.encode("utf-16-le")) // 2


def _prev_para(p_start: int, loc: dict[str, Any]) -> dict[str, Any]:
    return next(q for q in loc["paras"] if q["end"] == p_start)


def _del_range_to_end(start: int, loc: dict[str, Any]) -> list[dict[str, Any]]:
    """start(문단 시작)부터 탭 끝까지 지운다. 탭의 마지막 줄바꿈은 못 지우므로 앞 문단의 줄바꿈을 대신 지우는데,
    Docs는 문단 서식을 끝 줄바꿈에 붙여 두므로 앞 문단이 지운 문단의 서식을 받아 버린다 → 원래 서식을 다시 준다."""
    prev = _prev_para(start, loc)
    return [{"deleteContentRange": {"range": {"startIndex": start - 1, "endIndex": loc["end"] - 1, "tabId": S.doc_tab}}},
            {"updateParagraphStyle": {"range": {"startIndex": prev["start"], "endIndex": prev["end"], "tabId": S.doc_tab},
                                      "paragraphStyle": {"namedStyleType": prev["style"]}, "fields": "namedStyleType"}}]


def _del_para(p: dict[str, Any], loc: dict[str, Any]) -> list[dict[str, Any]]:
    """문단 하나 지우기 (마지막 문단이면 _del_range_to_end)."""
    if p["end"] >= loc["end"]:
        return _del_range_to_end(p["start"], loc)
    return [{"deleteContentRange": {"range": {"startIndex": p["start"], "endIndex": p["end"], "tabId": S.doc_tab}}}]


def _style_new_paragraph(start: int, text: str, who_at: int, highlight: bool) -> list[dict[str, Any]]:
    end = start + _u16(text)
    rng = {"startIndex": start, "endIndex": end + 1, "tabId": S.doc_tab}
    reqs = [{"updateParagraphStyle": {"range": rng, "paragraphStyle": {"namedStyleType": "NORMAL_TEXT"},
                                      "fields": "namedStyleType"}},
            {"updateTextStyle": {"range": {**rng, "endIndex": end}, "textStyle": {},
                                 "fields": "backgroundColor,foregroundColor,bold,italic"}}]
    if highlight and end > start:
        reqs.append({"updateTextStyle": {"range": {**rng, "endIndex": end}, "textStyle": {"backgroundColor": HIGHLIGHT_DOC},
                                         "fields": "backgroundColor"}})
    if who_at >= 0:
        reqs.append({"updateTextStyle": {"range": {**rng, "startIndex": start + who_at, "endIndex": end},
                                         "textStyle": {"foregroundColor": GRAY}, "fields": "foregroundColor"}})
    return reqs


def _one_doc_diff(loc: dict[str, Any], d: dict[str, Any], reverted: bool, who: str | None) -> list[dict[str, Any]]:
    parts = d["anchor"].split("/")
    before, after = (d["after"], d["before"]) if reverted else (d["before"], d["after"])
    tab, reqs = S.doc_tab, []
    if d["kind"] == "item":
        sec = _sec(parts[1])
        iid = parts[2]
        if before is None:  # 항목 생김
            if not sec["in_google"]:  # 원본에 없는 섹션 → 문서 끝에 제목 추가
                heading = next((h for sid, h, _ in EXTRA_SECTIONS if sid == sec["section_id"]), sec["section_id"])
                at = loc["end"] - 1
                reqs.append({"insertText": {"location": {"index": at, "tabId": tab}, "text": "\n" + heading}})
                h_start = at + 1
                reqs.append({"updateParagraphStyle": {"range": {"startIndex": h_start, "endIndex": h_start + _u16(heading) + 1, "tabId": tab},
                                                      "paragraphStyle": {"namedStyleType": "HEADING_2"}, "fields": "namedStyleType"}})
                reqs.append({"updateTextStyle": {"range": {"startIndex": h_start, "endIndex": h_start + _u16(heading), "tabId": tab},
                                                 "textStyle": {}, "fields": "backgroundColor,foregroundColor"}})
                sec["in_google"], sec["created"] = True, True
                loc[sec["section_id"]] = {"heading_para": {"start": h_start, "end": h_start + _u16(heading) + 1}, "items": {}}
                loc["end"] = h_start + _u16(heading) + 1
                # 섹션 순서 모델: in_google 섹션들 중 맨 끝으로 옮긴다
                S.sections.remove(sec)
                last = max((i for i, s in enumerate(S.sections) if s["in_google"]), default=-1)
                S.sections.insert(last + 1, sec)
            idx = min(d.get("index", len(sec["items"])), len(sec["items"]))
            items = loc[sec["section_id"]]["items"]
            if idx < len(sec["items"]):
                at = items[sec["items"][idx]]["start"]
            elif sec["items"]:
                at = items[sec["items"][-1]]["end"]
            else:
                at = loc[sec["section_id"]]["heading_para"]["end"]
            S.prefix.setdefault(iid, next((S.prefix[i] for i in sec["items"] if S.prefix.get(i)), "- "))
            line, who_at = _item_line(after, None if reverted else who)  # 되돌리기는 원래 글 그대로
            if at >= loc["end"]:  # 문서 맨 끝: 마지막 줄바꿈 앞에 "\n글"
                reqs.append({"insertText": {"location": {"index": loc["end"] - 1, "tabId": tab}, "text": "\n" + line}})
                start = loc["end"]
            else:
                reqs.append({"insertText": {"location": {"index": at, "tabId": tab}, "text": line + "\n"}})
                start = at
            reqs += _style_new_paragraph(start, line, who_at, highlight=not reverted)
            sec["items"].insert(idx, iid)
            if not reverted:
                S.hl_items.add(iid)
        elif after is None:  # 항목 없어짐
            p = loc[sec["section_id"]]["items"][iid]
            reqs += _del_para(p, loc)
            sec["items"].remove(iid)
            S.hl_items.discard(iid)
        else:  # 항목 바뀜: 글만 갈아 끼운다 (머리표 포함 한 줄)
            p = loc[sec["section_id"]]["items"][iid]
            line, who_at = _item_line(after, None if reverted else who)
            if p["end"] - 1 > p["start"]:
                reqs.append({"deleteContentRange": {"range": {"startIndex": p["start"], "endIndex": p["end"] - 1, "tabId": tab}}})
            reqs.append({"insertText": {"location": {"index": p["start"], "tabId": tab}, "text": line}})
            reqs += _style_new_paragraph(p["start"], line, who_at, highlight=not reverted)
            if not reverted:
                S.hl_items.add(iid)
    elif d["kind"] == "heading":
        hp = loc[parts[1]]["heading_para"]
        if hp["end"] - 1 > hp["start"]:
            reqs.append({"deleteContentRange": {"range": {"startIndex": hp["start"], "endIndex": hp["end"] - 1, "tabId": tab}}})
        reqs.append({"insertText": {"location": {"index": hp["start"], "tabId": tab}, "text": after}})
    elif d["kind"] == "section":
        sid = parts[1]
        if before is None:  # 섹션 생김 → 끝에 제목
            S.sections.append({"section_id": sid, "in_google": True, "created": True, "items": []})
            at = loc["end"] - 1
            reqs.append({"insertText": {"location": {"index": at, "tabId": tab}, "text": "\n" + after["heading"]}})
            reqs.append({"updateParagraphStyle": {"range": {"startIndex": at + 1, "endIndex": at + 2 + _u16(after["heading"]), "tabId": tab},
                                                  "paragraphStyle": {"namedStyleType": "HEADING_2"}, "fields": "namedStyleType"}})
        else:  # 섹션 없어짐 (항목은 이미 빠져 있다)
            reqs += _del_para(loc[sid]["heading_para"], loc)
            S.sections = [s for s in S.sections if s["section_id"] != sid]
    return reqs


def _clear_highlight_reqs(loc: dict[str, Any]) -> list[dict[str, Any]]:
    reqs = []
    for s in S.sections:
        if not s["in_google"]:
            continue
        for iid, p in loc.get(s["section_id"], {}).get("items", {}).items():
            if iid in S.hl_items and p["end"] - 1 > p["start"]:
                reqs.append({"updateTextStyle": {"range": {"startIndex": p["start"], "endIndex": p["end"] - 1, "tabId": S.doc_tab},
                                                 "textStyle": {}, "fields": "backgroundColor"}})
    S.hl_items = set()
    return reqs


def push_doc(event_type: str, change: dict[str, Any]) -> None:
    reverted = event_type == "change.reverted"
    diffs = [d for d in change.get("diff") or [] if d["kind"] in ("item", "section", "heading")
             and d["anchor"].startswith(DOC_KEY + "/")]
    if not diffs:
        return
    who = change.get("requested_by")
    saved = copy.deepcopy((S.sections, S.prefix, S.hl_items))
    try:
        first = True
        for d in (reversed(diffs) if reverted else diffs):
            loc = _locate(_doc_paragraphs(_first_doc_tab(S.doc_id)))  # 앞 diff가 위치를 바꿨으니 매번 다시
            reqs = _clear_highlight_reqs(loc) if first else []
            first = False
            reqs += _one_doc_diff(loc, d, reverted, who)
            if reqs:
                _docs().batchUpdate(documentId=S.doc_id, body={"requests": reqs}).execute()
    except Exception:
        S.sections, S.prefix, S.hl_items = saved
        raise


# ================================================================ 복원 (리셋)

def cleanup() -> None:
    """change 되돌리기가 끝난 뒤: 하이라이트 지우고, 우리가 추가한 빈 섹션 제목을 지운다."""
    if not S.active:
        return
    reqs = [_cell_req(r, c, highlight=False) for r, c in sorted(S.hl_cells) if r in S.rows]
    S.hl_cells = set()
    if reqs:
        _sheets().batchUpdate(spreadsheetId=S.sheet_id, body={"requests": reqs}).execute()
    loc = _locate(_doc_paragraphs(_first_doc_tab(S.doc_id)))
    dreqs = _clear_highlight_reqs(loc)
    created = [s for s in S.sections if s["created"] and s["in_google"] and not s["items"]]
    if created:
        # 추가한 섹션은 항상 문서 끝에 붙고 항목은 이미 되돌려졌다 → 첫 추가 제목 앞 줄바꿈부터 끝까지 한 번에 지운다
        first = min(loc[s["section_id"]]["heading_para"]["start"] for s in created)
        later = [s for s in S.sections if s["in_google"] and loc[s["section_id"]]["heading_para"]["start"] > first and s not in created]
        if later:
            raise RuntimeError("추가한 섹션 뒤에 다른 섹션이 있음 → 수동 정리 필요")
        dreqs += _del_range_to_end(first, loc)
        for s in created:
            s["in_google"], s["created"] = False, False
    if dreqs:
        _docs().batchUpdate(documentId=S.doc_id, body={"requests": dreqs}).execute()


def baseline_copy() -> DocState:
    assert S.baseline is not None
    return S.baseline.model_copy(deep=True)


def links() -> dict[str, str | None]:
    """원본 탭으로 바로 가는 주소 (Google 호출 없음)."""
    if not S.active:
        return {"sheet": None, "doc": None}
    return {"sheet": f"https://docs.google.com/spreadsheets/d/{S.sheet_id}/edit#gid={S.sheet_tab[1]}",
            "doc": f"https://docs.google.com/document/d/{S.doc_id}/edit?tab={S.doc_tab}"}
