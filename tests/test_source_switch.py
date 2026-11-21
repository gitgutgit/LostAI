"""문서 고르기 (각자 Google 로그인): 원본은 문서 주인 토큰으로만 읽고 쓴다 (가짜 Google, 사람마다 Drive). author: Mal-Mi-Jal

사람마다 가짜 Drive가 따로 있다. 지금 토큰(서버 계정 / 주인 / as_owner로 잠깐 쓰는 사람)의 Drive에 없는 파일을
부르면 실제 Google처럼 404 → 옛 원본 복원이 옛 주인 토큰으로, 새 원본 쓰기가 새 주인 토큰으로 됐는지를 이걸로 확인한다.
"""
import asyncio
from typing import NamedTuple

import pytest
from fastapi import HTTPException

from server import room as room_mod
from server.auth import challenge
from server.sync import google_auth, google_files, google_source as gsrc, source_api, user_auth
from server.sync.outbox import outbox
from tests.test_google_source import ORIGINAL_DOC, ORIGINAL_SHEET, FakeDocs, FakeSheets, Req, doc_view

DOC_B = [("TITLE", "디자인 리뷰"), ("HEADING_2", "리스크"), ("NORMAL_TEXT", "- 시안 확정 늦음"), ("NORMAL_TEXT", "")]


class NotFound(Exception):
    """googleapiclient HttpError처럼 resp.status를 가진다 → source_api._google_error가 400으로 바꾼다."""

    class resp:
        status = 404


class FakeCreds:
    def __init__(self, who):
        self.who, self.refresh_token, self.token, self.valid = who, "r", "a", True


DRIVES: dict[str, dict[str, dict]] = {}


def drive() -> str:
    """지금 Google을 부르는 계정 (google_auth의 주인 토큰, 없으면 서버 계정)."""
    return google_auth._owner.who if google_auth._owner is not None else "server"


class Multi:
    """지금 계정 Drive의 id별 가짜 문서로 보내 준다 (documentId / spreadsheetId)."""

    def __init__(self, kind, key):
        self.kind, self.key = kind, key

    def _file(self, fid):
        f = DRIVES[drive()][self.kind].get(fid)
        if f is None:
            raise NotFound(f"{drive()} 계정에 {fid} 없음")
        return f

    def __getattr__(self, name):
        def call(*a, **kw):
            fid = kw.pop(self.key)
            return getattr(self._file(fid), name)(fid, *a, **kw)
        return call

    def values(self):
        outer = self

        class V:
            def get(self, spreadsheetId, **kw):
                return outer._file(spreadsheetId).values().get(spreadsheetId, **kw)
        return V()


def fake_create_doc(title):
    d = FakeDocs([("NORMAL_TEXT", "")])
    d.batchUpdate(documentId="new", body={"requests": google_files.doc_template_requests(title)})
    fid = f"{drive()}-doc-{len(DRIVES[drive()]['doc'])}"
    DRIVES[drive()]["doc"][fid] = d
    return fid


def fake_create_sheet(title):
    s = FakeSheets([list(google_files.NEW_SHEET_COLUMNS)])
    s.title = title
    fid = f"{drive()}-sheet-{len(DRIVES[drive()]['sheet'])}"
    DRIVES[drive()]["sheet"][fid] = s
    return fid


@pytest.fixture
def g(monkeypatch, tmp_path):
    DRIVES.clear()
    DRIVES["server"] = {"doc": {"DA": FakeDocs(ORIGINAL_DOC)}, "sheet": {"SA": FakeSheets(ORIGINAL_SHEET)}}
    sb = FakeSheets([["항목", "담당"], ["로고", "민지"]])
    sb.title = "디자인 보드"
    DRIVES["ines"] = {"doc": {"DB": FakeDocs(DOC_B)}, "sheet": {"SB": sb}}
    DRIVES["owen"] = {"doc": {}, "sheet": {}}
    monkeypatch.setenv("GOOGLE_SHEET_ID", "SA")
    monkeypatch.setenv("GOOGLE_DOC_ID", "DA")
    monkeypatch.setenv("EVENT_LOG_DIR", str(tmp_path))
    monkeypatch.setattr(gsrc, "_docs", lambda: Multi("doc", "documentId"))
    monkeypatch.setattr(gsrc, "_sheets", lambda: Multi("sheet", "spreadsheetId"))
    monkeypatch.setattr(google_files, "create_doc", fake_create_doc)
    monkeypatch.setattr(google_files, "create_sheet", fake_create_sheet)
    monkeypatch.setattr(user_auth, "enabled", lambda: True)
    google_auth.set_owner(None, None)
    source_api._owner_gsid = None
    gsrc.S = gsrc.SourceState()
    gsrc.pull_baseline()  # 서버 시작: .env 기본 원본 (서버 계정)
    yield DRIVES
    gsrc.S = gsrc.SourceState()
    google_auth.set_owner(None, None)
    source_api._owner_gsid = None
    user_auth._sessions.clear()


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


class Person(NamedTuple):
    token: str   # 입장 토큰 (이름만으로 만들어진다)
    gsid: str    # 그 탭의 Google 로그인 열쇠 ("" = 로그인 안 함)


def join(name, who=None):
    """입장 + (who가 있으면) 그 Google 계정으로 로그인."""
    t = challenge.make_token(name)
    gsid = user_auth.login(name, user_auth.GoogleSession(creds=FakeCreds(who), email=f"{who}@example.com")) if who else ""
    return Person(t, gsid)


def sw(p: Person, **kw):
    return source_api.switch(source_api.SwitchReq(token=p.token, gsid=p.gsid, **kw))


def cur(p: Person):
    return source_api.current(p.token, p.gsid)


def no_sync_failed(room):
    return [e.payload for e in room.events if e.type == "sync.failed"]


def test_switch_to_my_doc_restores_old_with_old_owner_and_writes_with_mine(g):
    """서버 계정 원본으로 회의 → Ines가 자기 Doc만 고름 → 옛 원본은 서버 계정으로 복원, Sheet는 Ines Drive에 새로."""
    ines = join("Ines", "ines")

    async def steps(room):
        await room.changes.propose([{"op": "insert_item", "doc": "notes", "section": "s_risk", "text": "환불 지연"}], "Ines", "u1")
        await room.changes.propose([{"op": "set_cell", "doc": "board", "row": "r_g3", "column": "기간(일)", "value": "4"}], "Ines", "u2")
        await outbox.queue.join()
        assert doc_view(g["server"]["doc"]["DA"]) != ORIGINAL_DOC
        r = await sw(ines, doc="DB", title="디자인")
        await outbox.queue.join()
        assert r["doc"]["title"] == "디자인 리뷰" and r["sheet"]["title"] == "디자인 — 보드"
        assert list(g["ines"]["sheet"]) == ["SB", "ines-sheet-1"]  # 안 고른 Sheet는 Ines Drive에 새로
        assert google_auth.owner() == "ines@example.com"
        c = await cur(ines)
        assert c["mine"] and c["owner"] == "ines@example.com"
        assert not (await cur(join("Owen")))["mine"]
        # 새 원본 쓰기는 Ines 토큰으로
        await room.changes.propose([{"op": "add_decision", "text": "시안 금요일 확정"}], "Owen", "u1")
        await outbox.queue.join()
        assert ("NORMAL_TEXT", "- 시안 금요일 확정  · Owen") in doc_view(g["ines"]["doc"]["DB"])
        return room

    room = run_meeting(steps)
    assert doc_view(g["server"]["doc"]["DA"]) == ORIGINAL_DOC and g["server"]["sheet"]["SA"].view() == ORIGINAL_SHEET
    assert gsrc.chosen_ids() == ("SA", "DA")  # 개인 문서는 기록 안 함 → 다시 켜면 .env 기본 원본
    assert not no_sync_failed(room)


def test_owner_keeps_unpicked_side_and_next_person_restores_with_owner_token(g):
    """주인(Ines)이 Sheet만 바꾸면 Doc은 그대로. 그다음 Owen이 바꾸면 Ines 문서는 Ines 토큰으로 회의 전으로."""
    ines, owen = join("Ines", "ines"), join("Owen", "owen")

    async def steps(room):
        await sw(ines, sheet="SB", doc="DB")
        await outbox.queue.join()
        await sw(ines, sheet="new", title="2차")  # Doc 안 고름 → 내 거라 그대로
        await outbox.queue.join()
        assert gsrc.S.doc_id == "DB" and gsrc.S.sheet_id == "ines-sheet-1"
        await room.changes.propose([{"op": "insert_item", "doc": "notes", "section": "s_risk", "text": "폰트 라이선스"}], "Ines", "u1")
        await outbox.queue.join()
        assert doc_view(g["ines"]["doc"]["DB"]) != DOC_B
        r = await sw(owen, doc="new", title="주간")  # Sheet도 Owen Drive에 새로
        await outbox.queue.join()
        assert r["doc"]["title"] == "주간 — 회의 노트" and r["sheet"]["title"] == "주간 — 보드"
        assert sorted(g["owen"]["doc"]) == ["owen-doc-0"] and sorted(g["owen"]["sheet"]) == ["owen-sheet-0"]
        assert google_auth.owner() == "owen@example.com"
        return room

    room = run_meeting(steps)
    assert doc_view(g["ines"]["doc"]["DB"]) == DOC_B  # Owen 토큰으론 못 여는 문서 → Ines 토큰으로 복원됐다
    assert not no_sync_failed(room)


def test_cannot_open_a_file_outside_my_drive(g):
    """Owen이 서버 계정 문서 id를 직접 넣어도 Owen 토큰으로는 못 연다 → 400, 회의·주인 그대로."""
    owen = join("Owen", "owen")

    async def steps(room):
        await room.changes.propose([{"op": "insert_item", "doc": "notes", "section": "s_risk", "text": "환불 지연"}], "Ines", "u1")
        await outbox.queue.join()
        with pytest.raises(HTTPException) as e:
            await sw(owen, sheet="SA", doc="DA")
        assert e.value.status_code == 400 and "편집 권한" in e.value.detail
        assert len(room.changes.changes) == 1 and gsrc.S.doc_id == "DA" and google_auth.owner() is None

    run_meeting(steps)


def test_switch_needs_google_login(g, monkeypatch):
    async def steps(room):
        with pytest.raises(HTTPException) as e:
            await sw(join("Owen"), doc="new")
        assert e.value.status_code == 401
        monkeypatch.setattr(user_auth, "enabled", lambda: False)
        with pytest.raises(HTTPException) as e:
            await sw(join("Ines", "ines"), doc="DB")
        assert e.value.status_code == 409
        assert gsrc.S.doc_id == "DA"

    run_meeting(steps)


def test_same_name_without_my_login_key_gets_nothing(g):
    """입장 토큰은 이름만으로 만들어져 같은 이름이면 같다 → 내 Google 로그인은 그 탭의 gsid로만 쓸 수 있다."""
    ines = join("Ines", "ines")
    fake = join("Ines")  # 다른 사람이 같은 이름으로 입장
    assert fake.token == ines.token and fake.gsid == ""

    async def steps(room):
        await sw(ines, sheet="SB", doc="DB")
        await outbox.queue.join()
        for gsid in ("", "추측한-열쇠"):
            with pytest.raises(HTTPException) as e:
                await source_api.access(fake.token, gsid)  # 내 access token(→ 내 Drive Picker)
            assert e.value.status_code == 401
            with pytest.raises(HTTPException) as e:
                await sw(fake._replace(gsid=gsid), doc="new")
            assert e.value.status_code == 401
            assert (await source_api.config(fake.token, gsid))["me"] is None
            assert not (await cur(fake._replace(gsid=gsid)))["mine"]
        # 열쇠를 알아도 다른 이름으로는 못 쓴다
        with pytest.raises(HTTPException):
            await source_api.access(join("Owen").token, ines.gsid)
        assert (await source_api.access(ines.token, ines.gsid))["access_token"] == "a"
        assert gsrc.S.doc_id == "DB" and google_auth.owner() == "ines@example.com"

    run_meeting(steps)


def test_two_switches_at_once_only_one_runs(g):
    """둘이 동시에 바꾸기 → 먼저 온 쪽만, 나머지는 409. 회의 원본은 한 사람 것으로 깔끔하게."""
    ines, owen = join("Ines", "ines"), join("Owen", "owen")

    async def steps(room):
        res = await asyncio.gather(sw(ines, sheet="SB", doc="DB"), sw(owen, doc="new", title="주간"),
                                   return_exceptions=True)
        await outbox.queue.join()
        ok = [r for r in res if isinstance(r, dict)]
        busy = [r for r in res if isinstance(r, HTTPException)]
        assert len(ok) == 1 and len(busy) == 1 and busy[0].status_code == 409
        assert google_auth.owner() == "ines@example.com" and gsrc.S.doc_id == "DB"
        assert g["owen"]["doc"] == {} and g["owen"]["sheet"] == {}  # 진 쪽은 문서도 안 만든다
        return room

    room = run_meeting(steps)
    assert not no_sync_failed(room)


def test_server_drive_list_api_is_gone():
    from fastapi.testclient import TestClient
    from server.app import app
    c = TestClient(app)  # with 없이: 서버 시작(원본 불러오기) 안 돎
    t = join("Owen").token
    assert c.get("/api/google/files", params={"token": t, "kind": "doc"}).status_code == 404
    assert c.get("/api/google/config", params={"token": t}).status_code == 200
    assert c.get("/api/google/access", params={"token": t}).status_code in (401, 409)  # 로그인 전 / 설정 없음


def test_config_gives_only_public_values(monkeypatch):
    for k, v in {"GOOGLE_OAUTH_CLIENT_ID": "cid.apps.googleusercontent.com", "GOOGLE_OAUTH_CLIENT_SECRET": "SECRET-VALUE",
                 "GOOGLE_PICKER_API_KEY": "AIza-test", "GOOGLE_PROJECT_NUMBER": "123"}.items():
        monkeypatch.setenv(k, v)
    c = asyncio.run(source_api.config(join("Owen").token))
    assert c["enabled"] and c["me"] is None and c["app_id"] == "123"
    assert "SECRET-VALUE" not in repr(c)


def test_client_from_console_json_file(monkeypatch, tmp_path):
    """콘솔에서 받은 JSON 파일 경로만 줘도 된다 (파일이 ID·SECRET 변수보다 우선)."""
    f = tmp_path / "client_secret_web.json"
    f.write_text('{"web": {"client_id": "9-x.apps.googleusercontent.com", "client_secret": "GOCSPX-file"}}', encoding="utf-8")
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_SECRET", "client_secret_web")  # 파일 이름을 잘못 넣은 값은 무시된다
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_FILE", str(f))
    monkeypatch.delenv("GOOGLE_OAUTH_CLIENT_JSON", raising=False)
    assert user_auth.client() == ("9-x.apps.googleusercontent.com", "GOCSPX-file")
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_FILE", str(tmp_path / "없음.json"))
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_ID", "")
    assert not user_auth.enabled()  # 파일이 없으면 꺼짐 (409 안내)


@pytest.mark.parametrize("bad, msg", [
    ({"sheet": "SX", "doc": "DB"}, "첫 줄"),
    ({"doc": "DX"}, "표"),
])
def test_unusable_document_is_refused_and_meeting_kept(g, bad, msg):
    g["ines"]["sheet"]["SX"] = FakeSheets([["", ""], ["a", "b"]])
    dx = FakeDocs(DOC_B)
    orig_get = dx.get
    dx.get = lambda *a, **kw: Req({"tabs": [{**t, "documentTab": {"body": {"content": [{"table": {}}] + t["documentTab"]["body"]["content"]}}}
                                            for t in orig_get(*a, **kw).execute()["tabs"]]})
    g["ines"]["doc"]["DX"] = dx
    ines = join("Ines", "ines")

    async def steps(room):
        await room.changes.propose([{"op": "insert_item", "doc": "notes", "section": "s_risk", "text": "환불 지연"}], "Ines", "u1")
        await outbox.queue.join()
        with pytest.raises(HTTPException) as e:
            await sw(ines, **bad)
        assert e.value.status_code == 400 and msg in e.value.detail
        assert len(room.changes.changes) == 1 and gsrc.S.doc_id == "DA" and gsrc.S.sheet_id == "SA"  # 회의 그대로
        assert google_auth.owner() is None

    run_meeting(steps)


def test_new_doc_template_is_parsed_as_meeting_doc():
    d = FakeDocs([("NORMAL_TEXT", "")])  # 새로 만든 빈 문서
    d.batchUpdate(documentId="N", body={"requests": google_files.doc_template_requests("주간 회의 — 회의 노트")})
    assert doc_view(d) == [("TITLE", "주간 회의 — 회의 노트"), ("HEADING_2", "목표"), ("NORMAL_TEXT", ""),
                           ("HEADING_2", "메모"), ("NORMAL_TEXT", ""), ("HEADING_2", "리스크"), ("NORMAL_TEXT", ""),
                           ("NORMAL_TEXT", "")]
    title, sections = gsrc.parse_doc(gsrc._doc_paragraphs(d.get(documentId="N").execute()["tabs"][0]))
    assert title == "주간 회의 — 회의 노트" and [s["heading"] for s in sections] == ["목표", "메모", "리스크"]
