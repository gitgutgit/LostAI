"""Google Sheets 동기화. author: Mal-Mi-Jal

방식: 변경이 닿은 시트(doc_key)마다 **탭 하나를 통째로 미러링**한다 (batchUpdate 1회 = 지우기 + 쓰기).
- Outbox가 늦게 돌아도 `state`는 push 시점의 최신 상태라, 행 추가·삭제·되돌림 순서가 꼬이지 않는다.
- 셀 메모 = 출처 "<누가> · <무슨 말>", 이번 change가 바꾼 칸은 노란색.
- 탭 이름 = Sheet.title. 없으면 만든다. 시트당 요청 1회 (+탭 생성 시 1회, 메타 조회는 캐시).

호출은 Outbox 워커 하나에서만 온다 (동시 호출 금지, docs/ARCHITECTURE.md 3-5).
확인: `uv run python -m server.sync.google_sheets --seed sprint` (.env GOOGLE_SHEET_ID 문서에 시드를 미러링)
"""
from __future__ import annotations

import os
from typing import Any

from server.model.docs import DocState, Sheet
from server.sync import google_auth

HIGHLIGHT = {"red": 1.0, "green": 0.95, "blue": 0.6}
HEADER_BG = {"red": 0.93, "green": 0.93, "blue": 0.93}
WHITE = {"red": 1.0, "green": 1.0, "blue": 1.0}
FIELDS = "userEnteredValue,note,userEnteredFormat.backgroundColor,userEnteredFormat.textFormat.bold"

# 셀 앵커("board/r_pay423/추정") → 메모 문장. applied에서 넣고 reverted에서 뺀다.
_cell_notes: dict[str, str] = {}
# 탭 제목 → sheetId (스프레드시트별)
_tabs: dict[str, dict[str, int]] = {}


def enabled() -> bool:
    return bool(os.getenv("GOOGLE_SHEET_ID"))


def spreadsheet_id() -> str:
    return google_auth.parse_id(os.environ["GOOGLE_SHEET_ID"])


# ---------------------------------------------------------------- 순수 변환 (네트워크 없음)

def _value(v: Any) -> dict[str, Any]:
    if v is None or v == "":
        return {}
    if isinstance(v, bool):
        return {"boolValue": v}
    if isinstance(v, (int, float)):
        return {"numberValue": v}
    return {"stringValue": str(v)}


def provenance_note(change: dict[str, Any]) -> str:
    who = change.get("requested_by") or "?"
    why = change.get("reason") or ""
    # reason은 "<speaker>: <발화>" 형식 → 화자 중복 제거
    if why.startswith(f"{who}: "):
        why = why[len(who) + 2:]
    return f"{who} · {why}".strip(" ·") + f"\n({change.get('change_id', '')})"


def sheet_keys_in(change: dict[str, Any]) -> list[str]:
    """change diff가 닿은 시트 doc_key들 (순서 유지)."""
    keys: list[str] = []
    for d in change.get("diff") or []:
        if d.get("kind") in ("cell", "row"):
            k = d["anchor"].split("/")[0]
            if k not in keys:
                keys.append(k)
    return keys


def changed_cells(change: dict[str, Any], sheet: Sheet, key: str) -> set[str]:
    """이번 change가 바꾼 칸 앵커. 새 행은 값이 있는 칸 전부."""
    out: set[str] = set()
    for d in change.get("diff") or []:
        parts = d["anchor"].split("/")
        if parts[0] != key:
            continue
        if d["kind"] == "cell":
            out.add(d["anchor"])
        elif d["kind"] == "row" and d.get("after"):
            for c in sheet.columns:
                if (d["after"].get("cells") or {}).get(c) not in (None, ""):
                    out.add(f"{key}/{parts[1]}/{c}")
    return out


def record_notes(event_type: str, change: dict[str, Any]) -> None:
    cells = [d["anchor"] for d in change.get("diff") or [] if d.get("kind") == "cell"]
    for d in change.get("diff") or []:
        if d.get("kind") == "row" and d.get("after"):
            key, row_id = d["anchor"].split("/")[:2]
            cells += [f"{key}/{row_id}/{c}" for c in (d["after"].get("cells") or {})]
    if event_type == "change.reverted":
        cid = change.get("change_id", "")
        for a in cells:
            if _cell_notes.get(a, "").endswith(f"({cid})"):
                _cell_notes.pop(a, None)
    else:
        note = provenance_note(change)
        for a in cells:
            _cell_notes[a] = note


def mirror_requests(sheet: Sheet, key: str, tab_id: int, highlight: set[str],
                    notes: dict[str, str]) -> list[dict[str, Any]]:
    """탭을 sheet와 똑같이 만드는 batchUpdate 요청 2개: 전체 지우기 → A1부터 쓰기."""
    header = [{"userEnteredValue": {"stringValue": c},
               "userEnteredFormat": {"backgroundColor": HEADER_BG, "textFormat": {"bold": True}}}
              for c in sheet.columns]
    rows = [{"values": header}]
    for r in sheet.rows:
        cells = []
        for c in sheet.columns:
            anchor = f"{key}/{r.row_id}/{c}"
            cell: dict[str, Any] = {
                "userEnteredValue": _value(r.cells.get(c)),
                "userEnteredFormat": {"backgroundColor": HIGHLIGHT if anchor in highlight else WHITE,
                                      "textFormat": {"bold": False}},
            }
            if anchor in notes:
                cell["note"] = notes[anchor]
            cells.append(cell)
        rows.append({"values": cells})
    return [
        {"updateCells": {"range": {"sheetId": tab_id}, "fields": FIELDS}},  # 값·메모·색 전부 지움
        {"updateCells": {"start": {"sheetId": tab_id, "rowIndex": 0, "columnIndex": 0},
                         "rows": rows, "fields": FIELDS}},
    ]


# ---------------------------------------------------------------- Google 호출

def _api():
    return google_auth.service("sheets", "v4").spreadsheets()


def _tab_id(sid: str, title: str) -> int:
    tabs = _tabs.get(sid)
    if tabs is None or title not in tabs:
        meta = _api().get(spreadsheetId=sid, fields="sheets.properties(sheetId,title)").execute()
        tabs = _tabs[sid] = {s["properties"]["title"]: s["properties"]["sheetId"] for s in meta["sheets"]}
    if title not in tabs:
        res = _api().batchUpdate(spreadsheetId=sid, body={"requests": [
            {"addSheet": {"properties": {"title": title}}}]}).execute()
        tabs[title] = res["replies"][0]["addSheet"]["properties"]["sheetId"]
    return tabs[title]


def mirror(state: DocState, key: str, highlight: set[str] | None = None) -> None:
    sheet = state.sheet(key)
    sid = spreadsheet_id()
    tab = _tab_id(sid, sheet.title)
    _api().batchUpdate(spreadsheetId=sid, body={
        "requests": mirror_requests(sheet, key, tab, highlight or set(), _cell_notes)}).execute()


def push(state: DocState, event_type: str, change: dict[str, Any]) -> None:
    """event_type: change.applied | change.reverted. 실패하면 예외를 올린다 (Outbox가 재시도)."""
    record_notes(event_type, change)
    for key in sheet_keys_in(change):
        if key not in state.docs:
            continue
        sheet = state.sheet(key)
        hl = changed_cells(change, sheet, key) if event_type == "change.applied" else set()
        mirror(state, key, hl)


def push_all(state: DocState) -> list[str]:
    """모든 시트를 미러링 (서버 시작·리셋 때). 새 방이므로 이전 출처 메모도 지운다. 미러링한 doc_key 목록."""
    _cell_notes.clear()
    keys = [k for k, d in state.docs.items() if isinstance(d, Sheet)]
    for k in keys:
        mirror(state, k)
    return keys


if __name__ == "__main__":
    import argparse
    import sys

    from dotenv import load_dotenv

    from server.model.docs import load_seed
    from server.ops.engine import apply_op

    load_dotenv(google_auth.ROOT / ".env")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(description="시드를 GOOGLE_SHEET_ID 문서에 미러링")
    p.add_argument("--seed", default=os.getenv("SEED", "sprint"))
    p.add_argument("--demo-change", action="store_true", help="set_cell 하나를 적용해 하이라이트·메모까지 확인")
    a = p.parse_args()
    if not enabled():
        sys.exit("GOOGLE_SHEET_ID 없음 → `python -m server.sync.google_auth --sheet <URL> --save`")
    st = load_seed(a.seed)
    print("미러링:", push_all(st))
    if a.demo_change:
        sheet_key = next(k for k, d in st.docs.items() if isinstance(d, Sheet))
        sh = st.sheet(sheet_key)
        op = {"op": "set_cell", "doc": sheet_key, "row": sh.rows[0].row_id, "column": sh.columns[-1], "value": "동기화 테스트"}
        ch = {"change_id": "ch_demo", "requested_by": "Mal-Mi-Jal", "reason": "Mal-Mi-Jal: 동기화 테스트",
              "ops": [op], "diff": apply_op(st, op)}
        push(st, "change.applied", ch)
        print("demo change applied:", ch["diff"][0]["anchor"])
