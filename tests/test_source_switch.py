"""문서 고르기: 회의 중 원본 바꾸기 → 옛 원본 복원, 새 원본으로 회의, 못 쓰는 문서 거절 (가짜 Google). author: Mal-Mi-Jal"""
import asyncio

import pytest
from fastapi import HTTPException

from server import room as room_mod
from server.auth import challenge
from server.sync import google_files, google_source as gsrc, source_api
from server.sync.outbox import outbox
from tests.test_google_source import ORIGINAL_DOC, ORIGINAL_SHEET, FakeDocs, FakeSheets, Req, doc_view

DOC_B = [("TITLE", "디자인 리뷰"), ("HEADING_2", "리스크"), ("NORMAL_TEXT", "- 시안 확정 늦음"), ("NORMAL_TEXT", "")]


class Multi:
    """id별 가짜 문서로 보내 준다 (documentId / spreadsheetId)."""

    def __init__(self, files, key):
        self.files, self.key = files, key

    def __getattr__(self, name):
        def call(*a, **kw):
            fid = kw.pop(self.key)
            return getattr(self.files[fid], name)(fid, *a, **kw)
        return call

    def values(self):
        outer = self

        class V:
            def get(self, spreadsheetId, **kw):
                return outer.files[spreadsheetId].values().get(spreadsheetId, **kw)
        return V()


@pytest.fixture
def g(monkeypatch, tmp_path):
    docs = {"DA": FakeDocs(ORIGINAL_DOC), "DB": FakeDocs(DOC_B)}
    sheets = {"SA": FakeSheets(ORIGINAL_SHEET), "SB": FakeSheets([["항목", "담당"], ["로고", "민지"]])}
    sheets["SB"].title = "디자인 보드"
    monkeypatch.setenv("GOOGLE_SHEET_ID", "SA")
    monkeypatch.setenv("GOOGLE_DOC_ID", "DA")
    monkeypatch.setenv("EVENT_LOG_DIR", str(tmp_path))
    monkeypatch.setattr(gsrc, "_docs", lambda: Multi(docs, "documentId"))
    monkeypatch.setattr(gsrc, "_sheets", lambda: Multi(sheets, "spreadsheetId"))
    gsrc.S = gsrc.SourceState()
    gsrc.pull_baseline()
    yield docs, sheets
    gsrc.S = gsrc.SourceState()


def run_meeting(steps):
    async def main():
        room = room_mod.Room("main", seed="google")
        room_mod.rooms["main"] = room
        room.start()
        outbox.start()
        try:
            return await steps(room)
        finally:
            room_mod.rooms.pop("main", None)
    return asyncio.run(main())


def tok():
    return challenge.make_token("Ines")


def test_switch_doc_restores_old_and_opens_new(g):
    docs, sheets = g

    async def steps(room):
        await room.changes.propose([{"op": "insert_item", "doc": "notes", "section": "s_risk", "text": "환불 지연"}], "Ines", "u1")
        await room.changes.propose([{"op": "set_cell", "doc": "board", "row": "r_g3", "column": "기간(일)", "value": "4"}], "Ines", "u2")
        await outbox.queue.join()
        assert doc_view(docs["DA"]) != ORIGINAL_DOC and sheets["SA"].view() != ORIGINAL_SHEET
        r = await source_api.switch(source_api.SwitchReq(token=tok(), doc="DB"))  # 시트는 그대로
        await outbox.queue.join()
        assert r["doc"]["title"] == "디자인 리뷰" and r["sheet"]["title"] == "WBS 원본"
        assert not room.changes.changes and room.state.docs["notes"].title == "디자인 리뷰"
        assert [s.heading for s in room.state.docs["notes"].sections] == ["리스크", "결정 사항", "액션"]
        # 새 원본에 바로 쓰인다
        await room.changes.propose([{"op": "add_decision", "text": "시안 금요일 확정"}], "Owen", "u1")
        await outbox.queue.join()
        assert ("NORMAL_TEXT", "- 시안 금요일 확정  · Owen") in doc_view(docs["DB"])
        # 다시 원래 문서로 → 디자인 리뷰도 회의 전으로
        await source_api.switch(source_api.SwitchReq(token=tok(), doc="DA"))
        await outbox.queue.join()
        return room

    room = run_meeting(steps)
    assert doc_view(docs["DA"]) == ORIGINAL_DOC and sheets["SA"].view() == ORIGINAL_SHEET  # 옛 원본은 회의 전 그대로
    assert doc_view(docs["DB"]) == DOC_B
    assert gsrc.chosen_ids() == ("SA", "DA")  # 고른 문서 기록 (서버를 다시 켜도 그대로)
    assert all(e.type != "sync.failed" for e in room.events)


@pytest.mark.parametrize("bad, msg", [
    ({"sheet": "SX"}, "첫 줄"),
    ({"doc": "DX"}, "표"),
])
def test_unusable_document_is_refused_and_meeting_kept(g, bad, msg):
    docs, sheets = g
    sheets["SX"] = FakeSheets([["", ""], ["a", "b"]])
    docs["DX"] = FakeDocs(DOC_B)
    orig_get = docs["DX"].get
    docs["DX"].get = lambda *a, **kw: Req({"tabs": [{**t, "documentTab": {"body": {"content": [{"table": {}}] + t["documentTab"]["body"]["content"]}}}
                                                    for t in orig_get(*a, **kw).execute()["tabs"]]})

    async def steps(room):
        await room.changes.propose([{"op": "insert_item", "doc": "notes", "section": "s_risk", "text": "환불 지연"}], "Ines", "u1")
        await outbox.queue.join()
        with pytest.raises(HTTPException) as e:
            await source_api.switch(source_api.SwitchReq(token=tok(), **bad))
        assert e.value.status_code == 400 and msg in e.value.detail
        assert len(room.changes.changes) == 1 and gsrc.S.doc_id == "DA" and gsrc.S.sheet_id == "SA"  # 회의 그대로

    run_meeting(steps)


def test_new_doc_template_is_parsed_as_meeting_doc():
    d = FakeDocs([("NORMAL_TEXT", "")])  # 새로 만든 빈 문서
    d.batchUpdate(documentId="N", body={"requests": google_files.doc_template_requests("주간 회의 — 회의 노트")})
    assert doc_view(d) == [("TITLE", "주간 회의 — 회의 노트"), ("HEADING_2", "목표"), ("NORMAL_TEXT", ""),
                           ("HEADING_2", "메모"), ("NORMAL_TEXT", ""), ("HEADING_2", "리스크"), ("NORMAL_TEXT", ""),
                           ("NORMAL_TEXT", "")]
    title, sections = gsrc.parse_doc(gsrc._doc_paragraphs(d.get(documentId="N").execute()["tabs"][0]))
    assert title == "주간 회의 — 회의 노트" and [s["heading"] for s in sections] == ["목표", "메모", "리스크"]


def test_list_needs_relogin_without_drive_scope(monkeypatch):
    monkeypatch.setattr(google_files.google_auth, "has_scope", lambda s: False)
    with pytest.raises(google_files.NeedsRelogin):
        google_files.list_files("doc")
