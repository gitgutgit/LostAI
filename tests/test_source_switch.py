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
    source_api._owner_gsid = source_api._owner_name = source_api._request = None
    gsrc.S = gsrc.SourceState()
    gsrc.pull_baseline()  # 서버 시작: .env 기본 원본 (서버 계정)
    yield DRIVES
    gsrc.S = gsrc.SourceState()
    google_auth.set_owner(None, None)
    source_api._owner_gsid = source_api._owner_name = source_api._request = None
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


def ans(p: Person, request_id: str, approve: bool, keep=None):
    return source_api.answer(source_api.AnswerReq(token=p.token, gsid=p.gsid, request_id=request_id, approve=approve, keep=keep))


class Tab:
    """회의 화면 탭 하나 (WebSocket 대신)."""

    async def send_text(self, data):
        pass


async def enter(room, name) -> Tab:
    tab = Tab()
    await room.connect(tab, name)
    return tab


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
    """주인(Ines)이 Sheet만 바꾸면 Doc은 그대로. 그다음 Owen이 요청 → Ines가 '되돌리기'로 승인 → Ines 문서는 Ines 토큰으로 회의 전으로."""
    ines, owen = join("Ines", "ines"), join("Owen", "owen")

    async def steps(room):
        await enter(room, "Ines")
        await sw(ines, sheet="SB", doc="DB")
        await outbox.queue.join()
        await sw(ines, sheet="new", title="2차")  # Doc 안 고름 → 내 거라 그대로
        await outbox.queue.join()
        assert gsrc.S.doc_id == "DB" and gsrc.S.sheet_id == "ines-sheet-1"
        await room.changes.propose([{"op": "insert_item", "doc": "notes", "section": "s_risk", "text": "폰트 라이선스"}], "Ines", "u1")
        await outbox.queue.join()
        assert doc_view(g["ines"]["doc"]["DB"]) != DOC_B
        req = await sw(owen, doc="new", title="주간")
        assert req["pending"] and gsrc.S.doc_id == "DB"  # Ines 문서 → 승인 전엔 그대로
        r = await ans(ines, req["request_id"], True, keep=False)  # Sheet도 Owen Drive에 새로
        await outbox.queue.join()
        assert r["status"] == "approved"
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


# ================================================================ 새 회의 = 기본 원본으로 (back_to_default)

@pytest.fixture
def default_google(monkeypatch):
    monkeypatch.setattr(source_api, "default_is_google", True)


def test_new_meeting_goes_back_to_default_doc_with_server_account(g, default_google):
    """Ines가 자기 문서로 바꿔 회의 → 새 회의(되돌리기) → Ines 문서는 Ines 토큰으로 회의 전으로, 회의는 기본 원본(서버 계정)으로."""
    ines = join("Ines", "ines")

    async def steps(room):
        await sw(ines, sheet="SB", doc="DB")
        await outbox.queue.join()
        await room.changes.propose([{"op": "insert_item", "doc": "notes", "section": "s_risk", "text": "폰트 라이선스"}], "Ines", "u1")
        await outbox.queue.join()
        assert doc_view(g["ines"]["doc"]["DB"]) != DOC_B
        assert await source_api.back_to_default(False) == "switched"
        await outbox.queue.join()
        assert (gsrc.S.sheet_id, gsrc.S.doc_id) == ("SA", "DA") and google_auth.owner() is None
        assert source_api._owner_gsid is None and not (await cur(ines))["mine"]
        assert len(room.changes.changes) == 0
        # 새 회의 쓰기는 서버 계정 기본 원본으로
        await room.changes.propose([{"op": "add_decision", "text": "다음 주 배포"}], "Owen", "u1")
        await outbox.queue.join()
        assert ("NORMAL_TEXT", "- 다음 주 배포  · Owen") in doc_view(g["server"]["doc"]["DA"])
        assert room.state.docs["notes"].title == gsrc.S.baseline.docs["notes"].title
        return room

    room = run_meeting(steps)
    assert doc_view(g["ines"]["doc"]["DB"]) == DOC_B  # Ines 문서는 Ines 토큰으로 회의 전으로
    assert not no_sync_failed(room)


def test_new_meeting_on_default_already_is_plain_reset(g, default_google):
    async def steps(room):
        assert await source_api.back_to_default() == "already"
        assert google_auth.owner() is None and gsrc.S.doc_id == "DA"

    run_meeting(steps)


def test_new_meeting_without_google_default_is_plain_reset(g):
    """SEED=sprint로 켠 서버(default_is_google False)는 기본 원본이 없다 → 고른 문서 그대로 보통 리셋."""
    ines = join("Ines", "ines")

    async def steps(room):
        await sw(ines, sheet="SB", doc="DB")
        await outbox.queue.join()
        assert await source_api.back_to_default(False) == "none"
        assert gsrc.S.doc_id == "DB" and google_auth.owner() == "ines@example.com"

    run_meeting(steps)


def test_new_meeting_when_default_cannot_open_keeps_current(g, default_google):
    """기본 원본을 서버 계정으로 못 열면(토큰 만료·권한 없음) "failed" → 회의·주인 그대로 (부르는 쪽이 보통 리셋)."""
    ines = join("Ines", "ines")

    async def steps(room):
        await sw(ines, sheet="SB", doc="DB")
        await outbox.queue.join()
        del g["server"]["doc"]["DA"]
        assert await source_api.back_to_default(False) == "failed"
        assert gsrc.S.doc_id == "DB" and google_auth.owner() == "ines@example.com"

    run_meeting(steps)


def test_new_meeting_endpoint_needs_join_token():
    from fastapi.testclient import TestClient
    from server.app import app
    c = TestClient(app)  # with 없이: 서버 시작 안 돎
    assert c.post("/api/meeting/new", json={"token": "fake"}).status_code == 401
    assert c.post("/api/meeting/new", json={}).status_code == 422


# ================================================================ 바꾸기 요청 → 주인 승인 (PR2)

async def ines_owns(room, g):
    """Ines가 회의에 들어와 자기 문서로 바꾸고, 회의 중 변경 하나."""
    ines = join("Ines", "ines")
    tab = await enter(room, "Ines")
    await sw(ines, sheet="SB", doc="DB")
    await outbox.queue.join()
    await room.changes.propose([{"op": "insert_item", "doc": "notes", "section": "s_risk", "text": "폰트 라이선스"}], "Ines", "u1")
    await outbox.queue.join()
    return ines, tab


def test_first_switch_from_server_doc_needs_no_approval(g):
    """기본 원본(서버 계정)은 주인이 없다 → 처음 바꾸는 사람은 바로."""
    async def steps(room):
        await enter(room, "Pat")
        r = await sw(join("Ines", "ines"), doc="DB")
        assert r["ok"] and gsrc.S.doc_id == "DB"

    run_meeting(steps)


def test_owner_rejects_and_nothing_changes(g):
    async def steps(room):
        ines, _ = await ines_owns(room, g)
        owen = join("Owen", "owen")
        req = await sw(owen, doc="new", title="주간", doc_name="")
        assert req["pending"]
        seen = await cur(ines)
        assert seen["request"]["by"] == "Owen" and seen["request"]["doc"] == "새로 만들기" and seen["request"]["sheet"] is None
        assert "request" not in await cur(owen)  # 요청 카드는 주인 탭에만
        assert (await cur(owen))["my_request"]["status"] == "waiting"
        assert (await ans(ines, req["request_id"], False))["status"] == "rejected"
        assert (await cur(owen))["my_request"]["status"] == "rejected"
        assert "request" not in await cur(ines)
        assert gsrc.S.doc_id == "DB" and google_auth.owner() == "ines@example.com" and len(room.changes.changes) == 1
        assert g["owen"]["doc"] == {} and g["owen"]["sheet"] == {}  # 거절되면 Owen Drive에 빈 문서도 안 남는다
        with pytest.raises(HTTPException) as e:  # 끝난 요청엔 다시 답 못 함
            await ans(ines, req["request_id"], True)
        assert e.value.status_code == 409

    run_meeting(steps)


def test_no_answer_in_time_is_auto_rejected(g, monkeypatch):
    monkeypatch.setattr(source_api, "REQUEST_SEC", 0.2)

    async def steps(room):
        ines, _ = await ines_owns(room, g)
        owen = join("Owen", "owen")
        req = await sw(owen, doc="new")
        await asyncio.sleep(0.3)
        mine = (await cur(owen))["my_request"]
        assert mine["status"] == "timeout" and "자동으로 거절" in mine["detail"]
        assert "request" not in await cur(ines)
        with pytest.raises(HTTPException) as e:  # 늦은 승인은 안 먹는다
            await ans(ines, req["request_id"], True)
        assert e.value.status_code == 409 and "자동으로 거절" in e.value.detail
        assert gsrc.S.doc_id == "DB"
        assert (await sw(owen, doc="new"))["pending"]  # 끝났으니 다시 요청할 수 있다

    run_meeting(steps)


def test_one_request_at_a_time(g):
    async def steps(room):
        ines, _ = await ines_owns(room, g)
        owen, pat = join("Owen", "owen"), join("Pat", "owen")  # Pat도 owen 계정으로 로그인 (탭이 달라 gsid는 다름)
        await sw(owen, doc="new")
        for p, msg in ((pat, "Owen님의 바꾸기 요청"), (owen, "보낸 요청")):
            with pytest.raises(HTTPException) as e:
                await sw(p, doc="new")
            assert e.value.status_code == 409 and msg in e.value.detail
        assert "my_request" not in await cur(pat)  # 같은 Google 계정이어도 요청한 탭만 결과를 본다

    run_meeting(steps)


def test_only_the_owner_tab_can_answer(g):
    """주인 확인은 gsid로만: 요청한 사람, 같은 이름의 다른 사람(열쇠 없음·다른 로그인)은 403."""
    async def steps(room):
        ines, _ = await ines_owns(room, g)
        owen = join("Owen", "owen")
        req = await sw(owen, doc="new")
        same_name = [join("Ines"), join("Ines", "owen")]  # 이름만 같은 사람 (입장 토큰도 같음)
        assert same_name[0].token == ines.token
        for p in [owen, *same_name, ines._replace(gsid="추측한-열쇠")]:
            assert "request" not in await cur(p)
            with pytest.raises(HTTPException) as e:
                await ans(p, req["request_id"], True)
            assert e.value.status_code == 403
        assert gsrc.S.doc_id == "DB" and (await cur(owen))["my_request"]["status"] == "waiting"

    run_meeting(steps)


def test_owner_left_by_button_then_requester_confirms(g):
    """주인이 🚪 회의 나가기 → 요청 대신 '주인 없음' → 요청한 사람이 확인(force, 되돌리기)하면 승인 없이. Ines 문서는 Ines 토큰으로 회의 전으로."""
    async def steps(room):
        ines, tab = await ines_owns(room, g)
        room.disconnect(tab, left_by_button=True)
        owen = join("Owen", "owen")
        r = await sw(owen, doc="new", title="주간")
        assert r == {"ok": False, "owner_absent": True, "owner": "ines@example.com"} and gsrc.S.doc_id == "DB"
        r = await sw(owen, doc="new", title="주간", force=True, keep=False)
        await outbox.queue.join()
        assert r["ok"] and google_auth.owner() == "owen@example.com"
        return room

    room = run_meeting(steps)
    assert doc_view(g["ines"]["doc"]["DB"]) == DOC_B
    assert not no_sync_failed(room)


def test_force_is_ignored_while_owner_is_here(g):
    async def steps(room):
        await ines_owns(room, g)
        r = await sw(join("Owen", "owen"), doc="new", force=True)
        assert r["pending"] and gsrc.S.doc_id == "DB"

    run_meeting(steps)


def test_owner_tab_closed_counts_as_absent_only_after_a_while(g, monkeypatch):
    """탭 닫기·끊김(🚪 아님)은 ABSENT_SEC 지나야 '주인 없음'. 잠깐 끊겼다 다시 붙으면 그대로 주인."""
    monkeypatch.setattr(source_api, "ABSENT_SEC", 0.2)

    async def steps(room):
        ines, tab = await ines_owns(room, g)
        owen = join("Owen", "owen")
        room.disconnect(tab)  # 탭 닫힘 (1001/1006)
        req = await sw(owen, doc="new")
        assert req["pending"]  # 방금 끊김 → 아직 회의에 있는 걸로
        await ans(ines, req["request_id"], False)
        await enter(room, "Ines")  # 다시 붙음
        await asyncio.sleep(0.3)
        assert (await sw(owen, doc="new"))["pending"]  # 붙어 있으니 시간이 지나도 주인
        await ans(ines, (await cur(ines))["request"]["id"], False)
        room.disconnect(next(t for t, n in room.sockets.items() if n == "Ines"))
        await asyncio.sleep(0.3)
        assert (await sw(owen, doc="new"))["owner_absent"]

    run_meeting(steps)


def test_owner_switching_own_doc_cancels_the_request(g):
    async def steps(room):
        ines, _ = await ines_owns(room, g)
        owen = join("Owen", "owen")
        req = await sw(owen, doc="new")
        await sw(ines, sheet="new", title="2차")  # 주인은 자기 문서를 바로 바꿀 수 있다
        await outbox.queue.join()
        mine = (await cur(owen))["my_request"]
        assert mine["status"] == "canceled" and "바뀌었" in mine["detail"]
        with pytest.raises(HTTPException) as e:
            await ans(ines, req["request_id"], True)
        assert e.value.status_code == 409

    run_meeting(steps)


def test_approved_but_unusable_file_keeps_meeting(g):
    """승인 뒤 파일 확인에서 못 쓰는 문서면 400 → 요청은 failed, 회의·주인 그대로."""
    async def steps(room):
        ines, _ = await ines_owns(room, g)
        owen = join("Owen", "owen")
        req = await sw(owen, doc="DA", doc_name="서버 문서")  # Owen 토큰으로는 못 여는 파일
        assert (await cur(ines))["request"]["doc"] == "서버 문서"
        with pytest.raises(HTTPException) as e:
            await ans(ines, req["request_id"], True)
        assert e.value.status_code == 400
        mine = (await cur(owen))["my_request"]
        assert mine["status"] == "failed" and "승인됐지만" in mine["detail"]
        assert gsrc.S.doc_id == "DB" and google_auth.owner() == "ines@example.com" and len(room.changes.changes) == 1

    run_meeting(steps)


def test_new_meeting_needs_no_approval_and_cancels_request(g, default_google):
    """새 회의(회의 끝 화면)는 승인 없이 기본 원본으로. 걸려 있던 요청은 취소."""
    async def steps(room):
        ines, _ = await ines_owns(room, g)
        owen = join("Owen", "owen")
        await sw(owen, doc="new")
        assert await source_api.back_to_default() == "switched"
        await outbox.queue.join()
        assert (await cur(owen))["my_request"]["status"] == "canceled"
        assert (await sw(owen, doc="new"))["ok"]  # 다시 서버 계정 원본 → 바로

    run_meeting(steps)


def test_answer_endpoint_needs_join_token():
    from fastapi.testclient import TestClient
    from server.app import app
    c = TestClient(app)
    assert c.post("/api/google/source/answer", json={"token": "fake", "request_id": "x", "approve": True}).status_code == 401
    assert c.post("/api/google/source/answer", json={"token": join("Owen").token, "request_id": "x", "approve": True}).status_code == 403


# ================================================================ 옛 문서에 남기기 / 되돌리기 (PR3)

def kept_in_ines_doc(g) -> bool:
    """ines_owns가 Ines 문서 리스크에 넣은 항목이 Google 문서에 남아 있나."""
    return any("폰트 라이선스" in t for _, t in doc_view(g["ines"]["doc"]["DB"]))


def test_keep_default_is_restore_for_server_doc_and_keep_for_personal_doc(g):
    async def steps(room):
        pat = join("Pat", "pat")
        assert (await cur(pat))["keep_default"] is False  # 기본 WBS (서버 계정) = 되돌리기
        await ines_owns(room, g)
        assert (await cur(pat))["keep_default"] is True   # 각자 문서 = 남기기

    run_meeting(steps)


def test_owner_approves_with_keep_and_old_doc_keeps_meeting_result(g):
    """Owen이 '되돌리기'를 골라 요청해도 남길지는 주인이 정한다 → Ines가 남기기로 승인 → Ines 문서에 회의 결과가 그대로."""
    async def steps(room):
        ines, _ = await ines_owns(room, g)
        req = await sw(join("Owen", "owen"), doc="new", title="주간", keep=False)
        r = await ans(ines, req["request_id"], True, keep=True)
        await outbox.queue.join()
        assert r["status"] == "approved" and google_auth.owner() == "owen@example.com"
        return room

    room = run_meeting(steps)
    assert kept_in_ines_doc(g)
    assert not no_sync_failed(room)


def test_owner_approves_without_choice_keeps_by_default(g):
    async def steps(room):
        ines, _ = await ines_owns(room, g)
        req = await sw(join("Owen", "owen"), doc="new", title="주간")
        await ans(ines, req["request_id"], True)
        await outbox.queue.join()
        return room

    room = run_meeting(steps)
    assert kept_in_ines_doc(g)
    assert not no_sync_failed(room)


def test_owner_absent_force_keeps_by_default(g):
    """주인이 없을 때 요청한 사람이 안 고르면 남기기 (남의 문서를 마음대로 되돌리지 않게)."""
    async def steps(room):
        _, tab = await ines_owns(room, g)
        room.disconnect(tab, left_by_button=True)
        r = await sw(join("Owen", "owen"), doc="new", title="주간", force=True)
        await outbox.queue.join()
        assert r["ok"]
        return room

    room = run_meeting(steps)
    assert kept_in_ines_doc(g)
    assert not no_sync_failed(room)


def test_switch_from_server_doc_with_keep_leaves_value_and_clears_highlight(g):
    """기본 WBS에서 남기기를 고르면 바뀐 칸 값은 남고 하이라이트만 지워진다."""
    async def steps(room):
        await room.changes.propose([{"op": "set_cell", "doc": "board", "row": "r_g3", "column": "기간(일)", "value": "4"}], "Pat", "u1")
        await outbox.queue.join()
        assert any(c.get("bg") for row in g["server"]["sheet"]["SA"].grid for c in row)
        await sw(join("Ines", "ines"), doc="DB", keep=True)
        await outbox.queue.join()
        return room

    room = run_meeting(steps)
    sheet = g["server"]["sheet"]["SA"]
    assert sheet.view() != ORIGINAL_SHEET  # 4가 남음
    assert not any(c.get("bg") for row in sheet.grid for c in row)
    assert not no_sync_failed(room)


def test_new_meeting_keep_on_same_doc_rereads_it_so_screen_matches_doc(g, default_google):
    """기본 WBS에서 남기기로 새 회의 → 같은 문서를 다시 읽어 화면 시작점 = 남은 내용.
    그다음 회의를 되돌리기로 끝내면 두 번째 회의 것만 빠지고 첫 회의 결과는 남는다."""
    from server import app as app_mod

    async def steps(room):
        await room.changes.propose([{"op": "insert_item", "doc": "notes", "section": "s_risk", "text": "환불 지연"}], "Pat", "u1")
        await outbox.queue.join()
        assert await source_api.back_to_default(True) == "kept"
        await outbox.queue.join()
        assert len(room.changes.changes) == 0
        assert "환불 지연" in room.state.docs["notes"].model_dump_json()  # 옛 시작점 사본이면 여기 없다
        await room.changes.propose([{"op": "insert_item", "doc": "notes", "section": "s_risk", "text": "QA 인력 부족"}], "Pat", "u2")
        await outbox.queue.join()
        assert await source_api.back_to_default() == "already"  # 기본 WBS + 안 고름 = 되돌리기 → 보통 리셋
        await app_mod.reset()
        await outbox.queue.join()
        return room

    room = run_meeting(steps)
    texts = [t for _, t in doc_view(g["server"]["doc"]["DA"])]
    assert any("환불 지연" in t for t in texts) and not any("QA 인력 부족" in t for t in texts)
    assert not no_sync_failed(room)


def test_new_meeting_keep_on_personal_doc_then_default(g, default_google):
    """Ines 문서로 회의 → 새 회의(안 고름 = 남기기) → Ines 문서에 결과가 남고 회의는 기본 WBS로."""
    async def steps(room):
        await ines_owns(room, g)
        assert await source_api.back_to_default() == "switched"
        await outbox.queue.join()
        assert (gsrc.S.sheet_id, gsrc.S.doc_id) == ("SA", "DA") and google_auth.owner() is None
        return room

    room = run_meeting(steps)
    assert kept_in_ines_doc(g)
    assert not no_sync_failed(room)


def test_new_meeting_keep_when_default_cannot_open_rereads_current(g, default_google):
    async def steps(room):
        await ines_owns(room, g)
        del g["server"]["doc"]["DA"]
        assert await source_api.back_to_default() == "failed_kept"
        await outbox.queue.join()
        assert gsrc.S.doc_id == "DB" and google_auth.owner() == "ines@example.com"
        assert "폰트 라이선스" in room.state.docs["notes"].model_dump_json()
        return room

    room = run_meeting(steps)
    assert kept_in_ines_doc(g)
    assert not no_sync_failed(room)
