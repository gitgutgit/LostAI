"""문서 고르기 API: 각자 Google 로그인 → 자기 Sheet/Doc을 골라(Google Picker) 회의 원본으로. author: Mal-Mi-Jal

    GET  /api/google/config?token=&gsid=              로그인·Picker 설정 + 내 로그인 상태
    POST /api/google/login   {token, code, prev_gsid} 팝업에서 받은 code → 내 토큰 (메모리에만) + 새 gsid
    POST /api/google/logout  {token, gsid}
    GET  /api/google/access?token=&gsid=              Picker용 내 access token (그 탭에만)
    GET  /api/google/source?token=&gsid=              지금 회의 원본 (id·제목·주인)
    POST /api/google/source  {token, gsid, sheet, doc, title} sheet·doc: 파일 id | "new" | null

gsid = Google 로그인 때 서버가 만든 무작위 열쇠 (user_auth). 입장 토큰은 이름만으로 만들어져 같은 이름이면 같으므로,
내 Google 로그인·주인 여부는 입장 토큰이 아니라 gsid로 판단한다.

다른 사람 Drive가 보이지 않게: 예전의 서버 계정 Drive 목록(/api/google/files)은 없앴다. 파일 목록은 Picker가
그 사람 브라우저에서 Google과 직접 주고받고, 서버는 고른 파일 id만 받는다. 권한은 drive.file (고른 파일·만든 파일만).

원본 Sheet와 Doc은 항상 **한 사람(문서 주인) 것**이다. 회의 중 Google 쓰기는 주인 토큰으로 한다 (google_auth.set_owner).
null(안 고른 쪽): 내가 지금 주인이면 그대로, 아니면 내 Drive에 새로 만든다 ("new").

바꾸는 순서 (Google 호출은 전부 Outbox 줄 안에서, 동시 호출 없음):
  1. 내 토큰으로 새 문서 만들기 + 고른 문서 미리 읽어 구조 확인 → 못 쓰면 400, 회의는 그대로
  2. 회의 리셋 → 지금 원본은 **지금 주인 토큰으로** 회의 중 변경을 역순으로 되돌려 회의 전 상태로
  3. 되돌리기가 끝난 뒤 주인을 나로 바꾸고 새 문서를 다시 읽어 commit
  4. 한 번 더 리셋 → 새 원본으로 회의 시작, 화면에 새 스냅샷. 2~4 사이에 생긴 변경은 Google에 안 쓰고 버린다
개인 토큰은 메모리에만 있어서 서버를 다시 켜면 .env의 기본 원본(서버 계정)으로 시작한다 → 고른 기록은 지운다.
"""
from __future__ import annotations

import asyncio
import logging
import os
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from server.auth import challenge
from server.sync import google_auth, google_files, google_source, user_auth
from server.sync.outbox import outbox

router = APIRouter()
log = logging.getLogger("uvicorn.error")
_switch_lock = asyncio.Lock()
_owner_gsid: str | None = None  # 지금 원본 주인의 Google 로그인 열쇠 (None = 서버 계정)


def _auth(token: str) -> str:
    name = challenge.verify_token(token)
    if name is None:
        raise HTTPException(401, "invalid token")
    return name


def _google_error(e: Exception) -> HTTPException:
    status = getattr(getattr(e, "resp", None), "status", None)
    if status == 403 and ("has not been used" in str(e) or "SERVICE_DISABLED" in str(e)):
        return HTTPException(409, "Google Cloud 프로젝트에서 Google Drive API가 꺼져 있어요. "
                                  "콘솔 → API 및 서비스 → 라이브러리 → Google Drive API → 사용 (server/sync/GOOGLE_SETUP.md)")
    if status in (403, 404):
        return HTTPException(400, "문서를 열 수 없어요. 그 문서의 편집 권한이 내 Google 계정에 있는지 확인해 주세요.")
    log.warning("google source error: %s", str(e)[:200])
    return HTTPException(502, "Google 호출이 실패했어요. 잠시 뒤 다시 시도해 주세요.")


def _session(name: str, gsid: str | None) -> user_auth.GoogleSession:
    if not user_auth.enabled():
        raise HTTPException(409, "각자 Google 로그인이 설정되지 않았어요 (server/sync/GOOGLE_SETUP.md 6절).")
    sess = user_auth.get(name, gsid)
    if sess is None:
        raise HTTPException(401, "먼저 Google 로그인을 해 주세요.")
    return sess


@router.get("/api/google/config")
async def config(token: str, gsid: str = ""):
    sess = user_auth.get(_auth(token), gsid)
    return {**user_auth.public_config(), "me": {"email": sess.email} if sess else None}


class LoginReq(BaseModel):
    token: str
    code: str
    prev_gsid: str = ""  # 같은 탭에서 다시 로그인할 때 예전 열쇠 (주인이면 주인을 새 열쇠로 넘긴다)


@router.post("/api/google/login")
async def login(req: LoginReq):
    global _owner_gsid
    name = _auth(req.token)
    if not user_auth.enabled():
        raise HTTPException(409, "각자 Google 로그인이 설정되지 않았어요 (server/sync/GOOGLE_SETUP.md 6절).")
    try:
        sess = await asyncio.to_thread(user_auth.exchange, req.code)
    except user_auth.LoginError as e:
        raise HTTPException(400, str(e))
    prev = user_auth.get(name, req.prev_gsid)
    gsid = user_auth.login(name, sess)
    if prev is not None:
        user_auth.logout(req.prev_gsid)
        if req.prev_gsid == _owner_gsid and google_source.active():  # 주인이 다시 로그인 → 회의 쓰기도 새 토큰으로
            await outbox.run_exclusive(lambda: google_auth.set_owner(sess.creds, sess.email))
            _owner_gsid = gsid
    return {"gsid": gsid, "email": sess.email, "refresh": bool(sess.creds.refresh_token)}


class LogoutReq(BaseModel):
    token: str
    gsid: str = ""


@router.post("/api/google/logout")
async def logout(req: LogoutReq):
    if user_auth.get(_auth(req.token), req.gsid) is not None:
        user_auth.logout(req.gsid)  # 내가 지금 주인이어도 회의 쓰기는 이어간다 (주인 토큰은 google_auth가 들고 있음)
    return {"ok": True}


@router.get("/api/google/access")
async def access(token: str, gsid: str = ""):
    sess = _session(_auth(token), gsid)
    try:  # 갱신은 회의 쓰기와 같은 토큰 객체를 건드릴 수 있어 Outbox 줄에서
        return {"access_token": await outbox.run_exclusive(lambda: user_auth.access_token(sess))}
    except user_auth.LoginError as e:
        user_auth.logout(gsid)
        raise HTTPException(401, str(e))
    except Exception as e:
        raise _google_error(e)


@router.get("/api/google/source")
async def current(token: str, gsid: str = ""):
    _auth(token)
    S = google_source.S
    if not S.active:
        return {"active": False}
    b = S.baseline
    return {"active": True, "busy": _switch_lock.locked(),
            "owner": google_auth.owner(), "mine": bool(gsid) and gsid == _owner_gsid,
            "sheet": {"id": S.sheet_id, "title": b.docs["board"].title if b else None},
            "doc": {"id": S.doc_id, "title": b.docs["notes"].title if b else None}}


class SwitchReq(BaseModel):
    token: str
    gsid: str = ""             # 내 Google 로그인 열쇠
    sheet: str | None = None   # 파일 id 또는 "new", None이면 지금 것 그대로
    doc: str | None = None
    title: str = ""            # 새로 만들 때 문서 제목


@router.post("/api/google/source")
async def switch(req: SwitchReq):
    who = _auth(req.token)
    _session(who, req.gsid)
    if not req.sheet and not req.doc:
        raise HTTPException(400, "바꿀 Sheet나 Doc을 골라 주세요.")
    if _switch_lock.locked():
        raise HTTPException(409, "다른 사람이 문서를 바꾸는 중이에요.")
    async with _switch_lock:
        return await _switch(req, who)


async def _switch(req: SwitchReq, who: str) -> dict:
    from server.common.warmup import schedule_warmup
    from server.room import get_room

    global _owner_gsid
    S = google_source.S
    sess = _session(who, req.gsid)
    mine = google_source.active() and req.gsid == _owner_gsid
    # 안 고른 쪽: 내가 주인이면 그대로, 아니면 내 Drive에 새로 (Sheet와 Doc은 항상 한 사람 것)
    sheet = req.sheet or (None if mine else "new")
    doc = req.doc or (None if mine else "new")
    title = req.title.strip() or "회의"

    def prepare() -> tuple[str, str]:
        # 1. 내 토큰으로 만들기 + 구조 확인 (회의와 지금 주인은 그대로)
        with google_auth.as_owner(sess.creds, sess.email):
            sid = (google_files.create_sheet(f"{title} — 보드") if sheet == "new"
                   else google_auth.parse_id(sheet) if sheet else S.sheet_id)
            did = (google_files.create_doc(f"{title} — 회의 노트") if doc == "new"
                   else google_auth.parse_id(doc) if doc else S.doc_id)
            google_source.load(sid, did)  # 못 쓰는 문서면 SourceError
        return sid, did  # type: ignore[return-value]

    try:
        sid, did = await outbox.run_exclusive(prepare)
    except google_source.SourceError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise _google_error(e)

    room = get_room()
    # 2. 리셋 + 지금 원본 복원 (줄 맨 뒤에 서므로 앞서 들어온 변경이 다 쓰인 다음)
    old_changes = await room.reset()
    if google_source.active():
        outbox.enqueue_restore(room, [c.model_dump() for c in old_changes if c.status in ("applied", "approved")])
    outbox.hold = True
    try:
        # 3. 복원이 끝난 원본을 다시 읽어 commit
        def load_and_commit() -> None:
            prev = google_auth.set_owner(sess.creds, sess.email)  # 옛 원본 복원(앞선 줄)은 옛 주인 토큰으로 끝났다
            try:
                google_source.commit(google_source.load(sid, did))
            except Exception:
                google_auth.set_owner(*prev)
                raise
            google_source.clear_choice()  # 개인 토큰은 메모리에만 → 다시 켜면 .env 기본 원본으로
        try:
            await outbox.run_exclusive(load_and_commit)
        except Exception as e:  # 드묾: 확인 뒤 문서가 바뀜. 옛 원본은 이미 복원됐고 S도 그대로 → 옛 원본으로 회의 계속
            await room.emit("room.reset", "server", {}, {})
            await room.broadcast(room.snapshot())
            raise _google_error(e) if not isinstance(e, google_source.SourceError) else HTTPException(400, str(e))
        _owner_gsid = req.gsid
        room.seed_name = "google"
        os.environ["SEED"] = "google"
        # 4. 새 원본으로 회의 시작
        await room.reset()
    finally:
        outbox.hold = False
    await room.emit("room.reset", "server", {}, {})
    await room.broadcast(room.snapshot())
    outbox.enqueue_full_sync(room)
    schedule_warmup(room.state)
    st = room.state.docs
    log.info("회의 원본을 바꿈 (%s, 자기 Google 계정): 시트 %d행, 문서 섹션 %d개", who, len(st["board"].rows), len(st["notes"].sections))
    return {"ok": True, "sheet": {"id": sid, "title": st["board"].title}, "doc": {"id": did, "title": st["notes"].title}}
