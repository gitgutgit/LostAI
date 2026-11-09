"""원본 문서 모드: 원본 읽기 → 칸·문단 단위 쓰기 → 되돌리기 → 리셋 복원 (가짜 Google). author: Mal-Mi-Jal

가짜 Docs는 문단 목록을 실제 Docs처럼 한 줄 문자열(인덱스 1부터)로 다루며 insertText·deleteContentRange·
updateParagraphStyle만 흉내 낸다. 리셋 복원 뒤 문단(서식·글)이 원본과 똑같은지 본다.
"""
import copy

import pytest

from server.ops.engine import apply_op, revert_diff
from server.sync import google_source as gsrc


# ---------------------------------------------------------------- 가짜 Google

class Req:
    def __init__(self, r):
        self.r = r

    def execute(self):
        return self.r


class FakeDocs:
    """실제 Docs처럼 문단 서식을 그 문단 끝 줄바꿈에 붙여 둔다.
    - 글을 넣으면 새 줄바꿈은 넣은 자리 문단의 서식을 받는다
    - 줄바꿈을 지우면 그 서식도 사라지고, 합쳐진 문단은 살아남은 (뒤) 줄바꿈의 서식을 갖는다"""

    def __init__(self, paras):
        self.flat = "".join(t + "\n" for _, t in paras)  # 인덱스 1 = flat[0]
        self.styles = [st for st, _ in paras]           # 줄바꿈 순서대로

    @property
    def paras(self):
        return [[st, t] for st, t in zip(self.styles, self.flat.split("\n")[:-1])]

    def _nl_index(self, flat_i):
        """flat_i 위치 글자가 속한 문단 번호 (= 그 뒤 첫 줄바꿈의 번호)."""
        return self.flat[:flat_i].count("\n")

    def get(self, documentId, includeTabsContent=False, fields=None):
        content, pos = [], 1
        for style, text in self.paras:
            end = pos + len(text) + 1
            content.append({"startIndex": pos, "endIndex": end, "paragraph": {
                "paragraphStyle": {"namedStyleType": style},
                "elements": [{"textRun": {"content": text + "\n"}}]}})
            pos = end
        return Req({"tabs": [{"tabProperties": {"tabId": "t.0", "title": "Tab 1"},
                              "documentTab": {"body": {"content": content}}}]})

    def batchUpdate(self, documentId, body):
        for r in body["requests"]:
            (kind, b), = r.items()
            if kind == "insertText":
                i, text = b["location"]["index"] - 1, b["text"]
                assert 0 <= i <= len(self.flat) - 1, "마지막 줄바꿈 뒤에는 못 넣는다"
                k = self._nl_index(i)
                self.styles[k:k] = [self.styles[k]] * text.count("\n")
                self.flat = self.flat[:i] + text + self.flat[i:]
            elif kind == "deleteContentRange":
                s, e = b["range"]["startIndex"] - 1, b["range"]["endIndex"] - 1
                assert 0 <= s <= e <= len(self.flat) - 1, "마지막 줄바꿈은 지울 수 없다"
                k = self._nl_index(s)
                del self.styles[k:k + self.flat[s:e].count("\n")]
                self.flat = self.flat[:s] + self.flat[e:]
            elif kind == "updateParagraphStyle":
                s, e = b["range"]["startIndex"] - 1, b["range"]["endIndex"] - 1
                for k in range(self._nl_index(s), self._nl_index(max(s, e - 1)) + 1):
                    self.styles[k] = b["paragraphStyle"]["namedStyleType"]
            elif kind == "updateTextStyle":
                s, e = b["range"]["startIndex"], b["range"]["endIndex"]
                assert 1 <= s <= e <= len(self.flat) + 1
        return Req({})


class FakeSheets:
    def __init__(self, grid):
        self.grid = [[{"v": v} for v in row] for row in grid]
        self.title = "WBS 원본"

    def get(self, spreadsheetId, fields=None):
        return Req({"properties": {"title": self.title}, "sheets": [{"properties": {"title": "시트1", "sheetId": 0}}]})

    def values(self):
        outer = self

        class V:
            def get(self, spreadsheetId, range, valueRenderOption=None):
                return Req({"values": [[c["v"] for c in row] for row in outer.grid]})
        return V()

    def batchUpdate(self, spreadsheetId, body):
        for r in body["requests"]:
            (kind, b), = r.items()
            if kind == "insertDimension":
                self.grid.insert(b["range"]["startIndex"], [{"v": ""} for _ in self.grid[0]])
            elif kind == "deleteDimension":
                del self.grid[b["range"]["startIndex"]]
            elif kind == "updateCells":
                r0, c0 = b["start"]["rowIndex"], b["start"]["columnIndex"]
                cell, fields = b["rows"][0]["values"][0], b["fields"].split(",")
                tgt = self.grid[r0][c0]
                if "userEnteredValue" in fields:
                    v = cell.get("userEnteredValue", {})
                    tgt["v"] = next(iter(v.values())) if v else ""
                if "note" in fields:
                    tgt["note"] = cell.get("note", "")
                if "userEnteredFormat.backgroundColor" in fields:
                    tgt["bg"] = bool(cell.get("userEnteredFormat", {}).get("backgroundColor"))
        return Req({})

    def view(self):
        return [[c["v"] for c in row] for row in self.grid]


ORIGINAL_DOC = [
    ("TITLE", "모바일 주문 앱 v1.0 — 프로젝트 계획"),
    ("HEADING_2", "목표"), ("NORMAL_TEXT", "1월 14일 출시"),
    ("HEADING_2", "범위"), ("NORMAL_TEXT", "- 메뉴 조회·주문·결제"), ("NORMAL_TEXT", "- 소셜 로그인"),
    ("HEADING_2", "리스크"), ("NORMAL_TEXT", "- PG 연동 일정이 계약에 달려 있음"), ("NORMAL_TEXT", ""),
]
ORIGINAL_SHEET = [["작업", "WBS", "담당", "기간(일)", "상태"],
                  ["요구사항 인터뷰", "1.1", "지원", 5, "완료"],
                  ["경쟁 서비스 분석", "1.2", "서연", 3, "진행"]]


@pytest.fixture
def g(monkeypatch):
    docs, sheets = FakeDocs(ORIGINAL_DOC), FakeSheets(ORIGINAL_SHEET)
    monkeypatch.setenv("GOOGLE_SHEET_ID", "S")
    monkeypatch.setenv("GOOGLE_DOC_ID", "D")
    monkeypatch.setattr(gsrc, "_docs", lambda: docs)
    monkeypatch.setattr(gsrc, "_sheets", lambda: sheets)
    gsrc.S = gsrc.SourceState()
    state = gsrc.pull_baseline()
    yield docs, sheets, state
    gsrc.S = gsrc.SourceState()


def change(state, ops, cid, who="Ines", text="..."):
    diff = []
    for op in ops:
        diff += apply_op(state, op)
    return {"change_id": cid, "requested_by": who, "reason": f"{who}: {text}", "ops": ops, "diff": diff}


def doc_view(docs):
    return [tuple(p) for p in docs.paras]


# ---------------------------------------------------------------- 테스트

def test_pull_baseline(g):
    _, _, st = g
    board, notes = st.docs["board"], st.docs["notes"]
    assert board.title == "WBS 원본" and board.columns == ["작업", "WBS", "담당", "기간(일)", "상태"]
    assert [r.row_id for r in board.rows] == ["r_g2", "r_g3"] and board.rows[0].cells["기간(일)"] == 5
    assert notes.title == "모바일 주문 앱 v1.0 — 프로젝트 계획"
    assert [s.heading for s in notes.sections] == ["목표", "범위", "리스크", "결정 사항", "액션"]
    risk = notes.sections[2]
    assert risk.section_id == "s_risk" and risk.binding == "risks"
    assert [i.text for i in risk.items] == ["PG 연동 일정이 계약에 달려 있음"]  # '- ' 떼고, 빈 문단은 항목 아님
    assert gsrc.S.numeric_cols == {"기간(일)"}


def test_sheet_set_cell_then_revert(g):
    _, sheets, st = g
    ch = change(st, [{"op": "set_cell", "doc": "board", "row": "r_g3", "column": "기간(일)", "value": "4"}], "c1")
    gsrc.push_sheet("change.applied", ch)
    cell = sheets.grid[2][3]
    assert cell["v"] == 4 and cell["bg"] and cell["note"].startswith("Ines")  # 숫자 열이라 "4" → 4
    revert_diff(st, ch["diff"])
    gsrc.push_sheet("change.reverted", ch)
    assert sheets.view() == ORIGINAL_SHEET and not sheets.grid[2][3]["bg"] and sheets.grid[2][3]["note"] == ""


def test_sheet_add_delete_rows_and_restore(g):
    _, sheets, st = g
    c1 = change(st, [{"op": "add_row", "doc": "board", "values": {"작업": "결제 테스트", "담당": "Owen"}}], "c1")
    gsrc.push_sheet("change.applied", c1)
    assert sheets.view()[3][:3] == ["결제 테스트", "", "Owen"]
    c2 = change(st, [{"op": "delete_row", "doc": "board", "row": "r_g2"}], "c2")
    gsrc.push_sheet("change.applied", c2)
    assert [r[0] for r in sheets.view()] == ["작업", "경쟁 서비스 분석", "결제 테스트"]
    # 리셋: 역순 되돌리기 + 정리
    for ch in (c2, c1):
        revert_diff(st, ch["diff"])
        gsrc.push_sheet("change.reverted", ch)
    assert sheets.view() == ORIGINAL_SHEET


def test_doc_insert_into_existing_section(g):
    docs, _, st = g
    ch = change(st, [{"op": "insert_item", "doc": "notes", "section": "s_risk", "text": "결제 테스트가 불안정함"}], "c1", who="Owen")
    gsrc.push_doc("change.applied", ch)
    v = doc_view(docs)
    i = v.index(("NORMAL_TEXT", "- PG 연동 일정이 계약에 달려 있음"))
    assert v[i + 1] == ("NORMAL_TEXT", "- 결제 테스트가 불안정함  · Owen")  # 기존 마지막 항목 바로 뒤, 같은 머리표
    assert v[-1] == ("NORMAL_TEXT", "")  # 원래 있던 빈 문단은 그대로 끝에


def test_doc_decisions_section_created_then_restored(g):
    docs, _, st = g
    c1 = change(st, [{"op": "add_decision", "text": "출시를 1주 미룬다"}], "c1", who="Ines")
    gsrc.push_doc("change.applied", c1)
    c2 = change(st, [{"op": "add_action", "text": "PG사 계약 확인", "owner": "Ravi"}], "c2", who="Ravi")
    gsrc.push_doc("change.applied", c2)
    c3 = change(st, [{"op": "add_decision", "text": "QA 1명 추가"}], "c3", who="Owen")
    gsrc.push_doc("change.applied", c3)
    v = doc_view(docs)
    assert v[: len(ORIGINAL_DOC)] == ORIGINAL_DOC  # 원본 부분은 그대로
    assert v[len(ORIGINAL_DOC):] == [
        ("HEADING_2", "결정 사항"), ("NORMAL_TEXT", "- 출시를 1주 미룬다  · Ines"), ("NORMAL_TEXT", "- QA 1명 추가  · Owen"),
        ("HEADING_2", "액션"), ("NORMAL_TEXT", "- PG사 계약 확인 — 담당 Ravi  · Ravi"),
    ]
    # 리셋: 역순 되돌리기 → 정리 → 원본과 똑같아야 한다
    for ch in (c3, c2, c1):
        revert_diff(st, ch["diff"])
        gsrc.push_doc("change.reverted", ch)
    gsrc.cleanup()
    assert doc_view(docs) == ORIGINAL_DOC


def test_doc_update_and_delete_middle_item_then_revert(g):
    docs, _, st = g
    c1 = change(st, [{"op": "update_item", "doc": "notes", "item": "i_g2_1", "text": "메뉴 조회·주문"}], "c1")
    gsrc.push_doc("change.applied", c1)
    assert ("NORMAL_TEXT", "- 메뉴 조회·주문  · Ines") in doc_view(docs)
    c2 = change(st, [{"op": "delete_item", "doc": "notes", "item": "i_g2_2"}], "c2")
    gsrc.push_doc("change.applied", c2)
    assert all("소셜 로그인" not in t for _, t in doc_view(docs))
    for ch in (c2, c1):
        revert_diff(st, ch["diff"])
        gsrc.push_doc("change.reverted", ch)
    gsrc.cleanup()
    assert doc_view(docs) == ORIGINAL_DOC


def test_structure_change_is_detected(g):
    docs, _, st = g
    docs.batchUpdate("D", {"requests": [{"insertText": {"location": {"index": 1}, "text": "끼어든 제목\n"}},
                                         {"updateParagraphStyle": {"range": {"startIndex": 1, "endIndex": 2},
                                                                   "paragraphStyle": {"namedStyleType": "HEADING_2"}}}]})
    ch = change(st, [{"op": "insert_item", "doc": "notes", "section": "s_risk", "text": "x"}], "c1")
    before = copy.deepcopy(gsrc.S.sections)
    with pytest.raises(RuntimeError, match="구조"):
        gsrc.push_doc("change.applied", ch)
    assert gsrc.S.sections == before  # 실패하면 모델 그대로 (재시도 가능)


def test_reset_same_room_restores_original(g, tmp_path, monkeypatch):
    """main의 room.reset()은 방 객체를 그대로 쓴다 → 같은 객체로 되돌리기 → 정리 → 원본과 똑같아야 한다."""
    import asyncio

    from server import app as app_mod
    from server import room as room_mod
    from server.sync.outbox import outbox

    docs, sheets, _ = g
    monkeypatch.setenv("EVENT_LOG_DIR", str(tmp_path))

    async def run():
        room = room_mod.Room("main", seed="google")
        monkeypatch.setitem(room_mod.rooms, "main", room)
        room.start()
        outbox.start()
        await room.changes.propose([{"op": "set_cell", "doc": "board", "row": "r_g3", "column": "기간(일)", "value": "4"}],
                                   "Ines", utt_id="u1")
        await room.changes.propose([{"op": "add_decision", "text": "출시를 1주 미룬다"}], "Owen", utt_id="u2")
        await room.changes.propose([{"op": "insert_item", "doc": "notes", "section": "s_risk", "text": "환불 지연"}],
                                   "Owen", utt_id="u3")
        await outbox.queue.join()
        assert sheets.view() != ORIGINAL_SHEET and doc_view(docs) != ORIGINAL_DOC
        same = room
        await app_mod.reset()
        assert room_mod.rooms["main"] is same and not room.changes.changes  # 같은 객체, 새 회의
        await outbox.queue.join()
        return room

    room = asyncio.run(run())
    assert sheets.view() == ORIGINAL_SHEET and not any(c.get("bg") for row in sheets.grid for c in row)
    assert doc_view(docs) == ORIGINAL_DOC
    syncs = [e for e in room.events if e.type.startswith("sync.")]
    assert syncs and all(e.type == "sync.ok" for e in syncs)
    assert all(e.refs.utt_id is None for e in syncs)  # 옛 회의 u1~u3이 새 회의 지연 집계에 섞이지 않는다


def test_shutdown_restores_original(g, tmp_path, monkeypatch):
    """서버 종료(Railway 재배포 SIGTERM) 때 회의 중 변경을 되돌려 원본을 회의 전으로."""
    import asyncio

    from server import app as app_mod
    from server import room as room_mod
    from server.sync.outbox import outbox

    docs, sheets, _ = g
    monkeypatch.setenv("EVENT_LOG_DIR", str(tmp_path))

    async def run():
        room = room_mod.Room("main", seed="google")
        monkeypatch.setitem(room_mod.rooms, "main", room)
        room.start()
        outbox.start()
        await room.changes.propose([{"op": "add_decision", "text": "출시를 1주 미룬다"}], "Owen", utt_id="u1")
        await room.changes.propose([{"op": "set_cell", "doc": "board", "row": "r_g2", "column": "상태", "value": "보류"}],
                                   "Ines", utt_id="u2")
        await outbox.queue.join()
        assert doc_view(docs) != ORIGINAL_DOC and sheets.view() != ORIGINAL_SHEET
        await app_mod.restore_on_shutdown(timeout=5)

    asyncio.run(run())
    assert doc_view(docs) == ORIGINAL_DOC and sheets.view() == ORIGINAL_SHEET
