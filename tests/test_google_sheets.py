"""google_sheets.push 변환 테스트 (네트워크 없음, 가짜 API). author: Mal-Mi-Jal"""
import pytest

from server.model.docs import load_seed
from server.ops.engine import apply_op, revert_diff
from server.sync import google_sheets as gs


class FakeReq:
    def __init__(self, result):
        self.result = result

    def execute(self):
        return self.result


class FakeSheetsApi:
    def __init__(self):
        self.tabs = {"Sheet1": 0}
        self.batches: list[list[dict]] = []

    def get(self, spreadsheetId, fields=None):
        return FakeReq({"sheets": [{"properties": {"title": t, "sheetId": i}} for t, i in self.tabs.items()]})

    def batchUpdate(self, spreadsheetId, body):
        reqs = body["requests"]
        replies = []
        for r in reqs:
            if "addSheet" in r:
                sid = len(self.tabs) + 10
                self.tabs[r["addSheet"]["properties"]["title"]] = sid
                replies.append({"addSheet": {"properties": {"sheetId": sid}}})
        if not any("addSheet" in r for r in reqs):
            self.batches.append(reqs)
        return FakeReq({"replies": replies})


@pytest.fixture
def api(monkeypatch):
    fake = FakeSheetsApi()
    monkeypatch.setenv("GOOGLE_SHEET_ID", "https://docs.google.com/spreadsheets/d/FAKE_ID/edit")
    monkeypatch.setattr(gs, "_api", lambda: fake)
    gs._tabs.clear()
    gs._cell_notes.clear()
    return fake


def _written(fake):
    """마지막 batch의 쓰기 요청 → (값 표, 메모 dict, 하이라이트 좌표 set)"""
    rows = fake.batches[-1][1]["updateCells"]["rows"]
    table, notes, hl = [], {}, set()
    for i, r in enumerate(rows):
        line = []
        for j, c in enumerate(r["values"]):
            v = c["userEnteredValue"]
            line.append(next(iter(v.values()), None) if v else None)
            if "note" in c:
                notes[(i, j)] = c["note"]
            if i and c["userEnteredFormat"]["backgroundColor"] == gs.HIGHLIGHT:
                hl.add((i, j))
        table.append(line)
    return table, notes, hl


def _change(state, ops, cid="ch_1", who="Ines", text="추정 3으로"):
    diff = []
    for op in ops:
        diff += apply_op(state, op)
    return {"change_id": cid, "requested_by": who, "reason": f"{who}: {text}", "ops": ops, "diff": diff}


def test_set_cell_applied_then_reverted(api):
    s = load_seed("sprint")
    ch = _change(s, [{"op": "set_cell", "doc": "board", "row": "r_pay423", "column": "추정", "value": 3}])
    gs.push(s, "change.applied", ch)

    assert "스프린트 24 보드" in api.tabs  # 탭 자동 생성
    table, notes, hl = _written(api)
    assert table[0] == ["티켓", "제목", "추정", "담당", "상태"]
    assert table[1][2] == 3
    assert hl == {(1, 2)}
    assert notes[(1, 2)].startswith("Ines · 추정 3으로")
    assert api.batches[-1][0]["updateCells"]["fields"] == gs.FIELDS  # 먼저 전체 지우기

    revert_diff(s, ch["diff"])
    gs.push(s, "change.reverted", ch)
    table, notes, hl = _written(api)
    assert table[1][2] == 5 and not notes and not hl


def test_add_and_delete_row(api):
    s = load_seed("sprint")
    gs.push(s, "change.applied", _change(s, [{"op": "add_row", "doc": "board", "values": {"제목": "캐시", "추정": 2}}]))
    table, _, hl = _written(api)
    assert len(table) == 4 and table[3][1] == "캐시"
    assert hl == {(3, 1), (3, 2)}

    gs.push(s, "change.applied", _change(s, [{"op": "delete_row", "doc": "board", "row": "r_pay423"}], cid="ch_2"))
    table, _, _ = _written(api)
    assert [r[0] for r in table] == ["티켓", "AUTH-118", None]


def test_doc_only_change_skips_sheets(api):
    s = load_seed("sprint")
    gs.push(s, "change.applied", _change(s, [{"op": "add_decision", "text": "출시 연기"}]))
    assert api.batches == []


def test_parse_id_from_url(api):
    assert gs.spreadsheet_id() == "FAKE_ID"


def test_outbox_full_sync_goes_through_worker(api):
    import asyncio

    from server.sync.outbox import Outbox

    class FakeRoom:
        state = load_seed("sprint")
        emitted: list = []

        async def emit(self, type_, actor, refs, payload):
            self.emitted.append((type_, payload))

    async def run():
        ob, room = Outbox(), FakeRoom()
        gs._cell_notes["board/r_pay423/추정"] = "old"
        ob.start()
        ob.enqueue_full_sync(room)
        await asyncio.wait_for(ob.queue.join(), 2)
        ob._worker.cancel()
        return room.emitted

    emitted = asyncio.run(run())
    assert emitted == [("sync.ok", {"target": "google_sheets", "ms": emitted[0][1]["ms"]})]
    assert gs._cell_notes == {}  # 새 방이면 이전 출처 메모 지움
    table, notes, _ = _written(api)
    assert len(table) == 3 and not notes
