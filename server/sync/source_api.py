"""문서 고르기 API: 각자 Google 로그인 → 자기 Sheet/Doc을 골라(Google Picker) 회의 원본으로. author: Mal-Mi-Jal

    GET  /api/google/config?token=&gsid=              로그인·Picker 설정 + 내 로그인 상태
    POST /api/google/login   {token, code, prev_gsid} 팝업에서 받은 code → 내 토큰 (메모리에만) + 새 gsid
    POST /api/google/logout  {token, gsid}
    GET  /api/google/access?token=&gsid=              Picker용 내 access token (그 탭에만)
    GET  /api/google/source?token=&gsid=              지금 회의 원본 (id·제목·주인)
    POST /api/google/source  {token, gsid, sheet, doc, title, force, keep} sheet·doc: 파일 id | "new" | null
    POST /api/google/source/answer {token, gsid, request_id, approve, keep}  문서 주인이 바꾸기 요청에 답함
    (새 회의 = back_to_default, 엔드포인트는 app.py POST /api/meeting/new)

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
누가 바꿀 수 있나 (PR2, Mal-Mi-Jal 11-21):
  - 지금 원본이 서버 계정 것(기본 WBS)이거나 내가 주인이면 바로 바꾼다.
  - 아니면 '요청'이 된다 → 주인 탭에만 승인/거절 (그 탭이 2초마다 GET /api/google/source로 본다). 30초 안에 답이 없으면
    자동 거절. 요청은 한 번에 하나. 주인 확인은 gsid로만 (같은 이름의 다른 사람은 승인 못 함).
  - 주인이 회의에 없으면(🚪 회의 나가기, 또는 30초 넘게 접속 없음) 요청 대신 {owner_absent} → 요청한 사람이 확인하고
    force로 다시 보내면 승인 없이 바꾼다.
  - 파일 확인·새 문서 만들기는 승인된 뒤에 한다 (거절되면 요청한 사람 Drive에 빈 문서가 안 남게).
  - 새 회의(back_to_default)는 승인 없이 (회의가 이미 끝난 뒤라서). 원본이 바뀌면 걸려 있던 요청은 취소된다.
  - 요청·승인은 이벤트 로그에 안 남긴다 (계약 안 바꿈, 기록 = 서버 로그 한 줄).
옛 문서에 회의 결과를 남기나 (keep, PR3, Mal-Mi-Jal 11-21):
  - 남기기 = 2단계의 역순 되돌리기를 건너뛰고 하이라이트·빈 섹션 정리만 한다. 되돌리기 = 위 2단계 그대로.
  - 고르는 사람: 주인 승인이면 주인(승인 카드), 그 밖(내 문서·기본 WBS·주인 없음·새 회의)은 바꾸는 사람.
  - 안 고르면(None) 기본값: 서버 계정 문서(기본 WBS, 팀 시연 문서) = 되돌리기, 각자 문서 = 남기기 (남의 문서를 마음대로 안 되돌린다).
  - 같은 문서로 새 회의를 열 때 남기면 문서를 다시 읽어 그 내용을 새 회의 시작점으로 (옛 시작점 사본을 쓰면 화면과 문서가 어긋난다).
  - 서버 꺼짐·/api/reset(테스트 대본)은 지금처럼 되돌리기.
개인 토큰은 메모리에만 있어서 서버를 다시 켜면 .env의 기본 원본(서버 계정)으로 시작한다 → 고른 기록은 지운다.
"""
from __future__ import annotations

import asyncio
import logging
import os
import secrets
import time
from dataclasses import dataclass, field
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
_owner_name: str | None = None  # 지금 원본 주인의 입장 이름 ('회의에 있나'를 볼 때만)
REQUEST_SEC = 30.0  # 주인이 이 안에 답이 없으면 자동 거절
ABSENT_SEC = 30.0   # 주인 탭이 이만큼 하나도 안 붙어 있으면 '회의에 없음' (🚪는 바로)


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
    name = _auth(token)
    S = google_source.S
    if not S.active:
        return {"active": False}
    b = S.baseline
    out = {"active": True, "busy": _switch_lock.locked(), "keep_default": keep_default(),
           "owner": google_auth.owner(), "mine": bool(gsid) and gsid == _owner_gsid,
           "sheet": {"id": S.sheet_id, "title": b.docs["board"].title if b else None},
           "doc": {"id": S.doc_id, "title": b.docs["notes"].title if b else None}}
    r = _live_request()
    if r is not None and gsid and user_auth.get(name, gsid) is not None:
        if gsid == _owner_gsid and r.status == "waiting":
            out["request"] = r.for_owner()  # 주인 탭에만
        if gsid == r.gsid:
            out["my_request"] = r.for_requester()  # 요청한 탭에만 (끝난 결과도 한동안)
    return out


class SwitchReq(BaseModel):
    token: str
    gsid: str = ""             # 내 Google 로그인 열쇠
    sheet: str | None = None   # 파일 id 또는 "new", None이면 지금 것 그대로
    doc: str | None = None
    title: str = ""            # 새로 만들 때 문서 제목
    sheet_name: str = ""       # 주인 승인 카드에 보일 이름 (Picker가 준 파일 이름)
    doc_name: str = ""
    force: bool = False        # '주인이 회의에 없어요' 안내를 보고 승인 없이 바꾸기
    keep: bool | None = None   # 지금 문서에 회의 결과를 남기나 (None = 기본값, keep_default). 주인 승인이면 주인 답이 정한다


@router.post("/api/google/source")
async def switch(req: SwitchReq):
    who = _auth(req.token)
    _session(who, req.gsid)
    if not req.sheet and not req.doc:
        raise HTTPException(400, "바꿀 Sheet나 Doc을 골라 주세요.")
    if _switch_lock.locked():
        raise HTTPException(409, "다른 사람이 문서를 바꾸는 중이에요.")
    if _needs_approval(req.gsid):
        r = _live_request()
        if r is not None and r.status in ("waiting", "running"):
            if r.gsid == req.gsid:
                raise HTTPException(409, "보낸 요청이 아직 주인 답을 기다리는 중이에요.")
            raise HTTPException(409, f"{r.by}님의 바꾸기 요청이 주인 답을 기다리는 중이에요 ({r.left()}초 남음).")
        if not _owner_absent():
            return _open_request(req, who)
        if not req.force:
            return {"ok": False, "owner_absent": True, "owner": google_auth.owner()}
        log.info("문서 주인이 회의에 없어 %s가 승인 없이 바꿈", who)
    async with _switch_lock:
        return await _switch(req, who)


async def _switch(req: SwitchReq, who: str) -> dict:
    from server.room import get_room

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
    st = await _reset_onto(room, sid, did, sess.creds, sess.email, req.gsid, who, keep=_keep(req.keep))
    log.info("회의 원본을 바꿈 (%s, 자기 Google 계정): 시트 %d행, 문서 섹션 %d개", who, len(st["board"].rows), len(st["notes"].sections))
    return {"ok": True, "sheet": {"id": sid, "title": st["board"].title}, "doc": {"id": did, "title": st["notes"].title}}


async def _reset_onto(room, sid: str, did: str, creds, label: str | None, gsid: str | None, name: str | None,
                     keep: bool = False):
    """바꾸는 순서 2~4: 리셋 + 지금 원본을 지금 주인 토큰으로 복원 → 주인을 creds로 바꾸고 (sid, did) commit → 새 회의.
    creds=None이면 서버 계정(.env 기본 원본). 구조 확인(1)은 부르는 쪽이 끝낸 다음. _switch_lock 안에서만 부른다.
    keep=True면 지금 원본은 되돌리지 않고 정리(하이라이트·빈 섹션)만. (sid, did)가 지금 원본과 같아도 다시 읽으므로
    남긴 내용이 새 회의 시작점이 된다."""
    from server.common.warmup import schedule_warmup

    global _owner_gsid, _owner_name
    # 2. 리셋 + 지금 원본 복원 (줄 맨 뒤에 서므로 앞서 들어온 변경이 다 쓰인 다음)
    old_changes = await room.reset()
    if google_source.active():
        done = [c.model_dump() for c in old_changes if c.status in ("applied", "approved")]
        outbox.enqueue_restore(room, [] if keep else done)  # 남기기 = 되돌리기 없이 정리만 (같은 줄, 같은 주인 토큰)
        if keep and done:
            log.info("옛 원본에 회의 중 변경 %d개를 남김", len(done))
    outbox.hold = True
    try:
        # 3. 복원이 끝난 원본을 다시 읽어 commit
        def load_and_commit() -> None:
            prev = google_auth.set_owner(creds, label)  # 옛 원본 복원(앞선 줄)은 옛 주인 토큰으로 끝났다
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
        _owner_gsid, _owner_name = gsid, name
        _cancel_request("그사이 회의 문서가 바뀌었어요.")
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
    return room.state.docs


# ================================================================ 바꾸기 요청 → 주인 승인

@dataclass
class SwitchRequest:
    id: str
    by: str          # 요청한 사람 입장 이름
    gsid: str        # 요청한 탭의 Google 로그인 열쇠
    req: SwitchReq
    t0: float = field(default_factory=time.monotonic)
    status: Literal["waiting", "running", "approved", "rejected", "timeout", "failed", "canceled"] = "waiting"
    detail: str = ""
    done_at: float = 0.0

    def left(self) -> int:
        return max(0, int(REQUEST_SEC - (time.monotonic() - self.t0) + 0.999))

    def _what(self) -> dict:
        def one(fid: str | None, fname: str) -> str | None:
            return None if not fid else "새로 만들기" if fid == "new" else (fname.strip() or "고른 파일")
        return {"sheet": one(self.req.sheet, self.req.sheet_name), "doc": one(self.req.doc, self.req.doc_name)}

    def for_owner(self) -> dict:
        return {"id": self.id, "by": self.by, **self._what(), "left": self.left()}

    def for_requester(self) -> dict:
        return {"id": self.id, "status": self.status, "detail": self.detail, "left": self.left()}

    def finish(self, status, detail: str = "") -> None:
        self.status, self.detail, self.done_at = status, detail, time.monotonic()


_request: SwitchRequest | None = None
RESULT_KEEP_SEC = 60.0  # 끝난 요청 결과를 요청한 탭이 볼 수 있는 시간


def _needs_approval(gsid: str) -> bool:
    """서버 계정 원본(주인 없음)이거나 내가 주인이면 승인 없이."""
    return google_source.active() and _owner_gsid is not None and gsid != _owner_gsid


def keep_default() -> bool:
    """안 고를 때 지금 문서에 회의 결과를 남기나: 서버 계정 문서(기본 WBS) = 되돌리기, 각자 문서 = 남기기."""
    return google_source.active() and _owner_gsid is not None


def _keep(keep: bool | None) -> bool:
    return keep_default() if keep is None else keep


def _owner_absent() -> bool:
    """주인이 회의에 없나: 🚪 회의 나가기, 또는 그 이름의 탭이 ABSENT_SEC 넘게 하나도 안 붙어 있음.
    한계: 같은 이름의 다른 사람이 붙어 있으면 '있음'으로 본다 (입장 토큰이 이름만으로 만들어짐)."""
    from server.room import get_room
    if _owner_name is None:
        return True
    button, secs = get_room().absent_for(_owner_name)
    return button or secs > ABSENT_SEC


def _live_request() -> SwitchRequest | None:
    """지금 요청. 만료 확인을 여기서 한다 (따로 타이머 없이 누가 물어볼 때마다)."""
    global _request
    r = _request
    if r is None:
        return None
    if r.status == "waiting" and r.left() == 0:
        r.finish("timeout", f"{int(REQUEST_SEC)}초 안에 문서 주인이 답하지 않아 자동으로 거절됐어요.")
        log.info("바꾸기 요청 자동 거절 (%s)", r.by)
    if r.status not in ("waiting", "running") and time.monotonic() - r.done_at > RESULT_KEEP_SEC:
        _request = None
        return None
    return r


def cancel_request(why: str) -> None:
    """기다리는 바꾸기 요청이 있으면 닫는다 (모두 나감 등 바깥에서 부름)."""
    _cancel_request(why)


def at_default() -> bool:
    """지금 회의 문서가 기본 원본인가. 기본 원본이 없는 서버(SEED=sprint)면 누가 고른 문서가 없을 때 True."""
    S = google_source.S
    ids = _default_ids()
    if ids is None:
        return not S.active
    return S.active and _owner_gsid is None and google_auth.owner() is None and (S.sheet_id, S.doc_id) == ids


def _cancel_request(why: str) -> None:
    r = _live_request()
    if r is not None and r.status == "waiting":
        r.finish("canceled", why)


def _open_request(req: SwitchReq, who: str) -> dict:
    global _request
    _request = SwitchRequest(id=secrets.token_urlsafe(8), by=who, gsid=req.gsid, req=req)
    log.info("바꾸기 요청 (%s → 주인 승인 대기)", who)
    return {"ok": False, "pending": True, "request_id": _request.id, "timeout_sec": REQUEST_SEC}


class AnswerReq(BaseModel):
    token: str
    gsid: str = ""
    request_id: str
    approve: bool
    keep: bool | None = None  # 승인할 때 내 문서에 회의 결과를 남기나 (None = 남기기, 각자 문서 기본값)


@router.post("/api/google/source/answer")
async def answer(req: AnswerReq):
    name = _auth(req.token)
    if not req.gsid or req.gsid != _owner_gsid or user_auth.get(name, req.gsid) is None:
        raise HTTPException(403, "지금 회의 문서의 주인만 답할 수 있어요.")
    r = _live_request()
    if r is None or r.id != req.request_id or r.status != "waiting":
        same = r is not None and r.id == req.request_id and r.detail
        raise HTTPException(409, r.detail if same else "이미 끝난 요청이에요.")  # type: ignore[union-attr]
    if not req.approve:
        r.finish("rejected", "문서 주인이 거절했어요.")
        log.info("바꾸기 요청 거절 (%s)", r.by)
        return {"ok": True, "status": r.status}
    if _switch_lock.locked():
        raise HTTPException(409, "다른 사람이 문서를 바꾸는 중이에요.")
    r.status = "running"
    r.req = r.req.model_copy(update={"keep": req.keep})  # 주인 문서에 남길지는 주인이 정한다 (요청한 사람 값은 안 씀)
    try:
        async with _switch_lock:
            res = await _switch(r.req, r.by)
    except HTTPException as e:
        r.finish("failed", f"승인됐지만 바꾸지 못했어요: {e.detail}")
        raise
    except Exception:
        r.finish("failed", "승인됐지만 바꾸지 못했어요. 잠시 뒤 다시 시도해 주세요.")
        raise
    r.finish("approved", "문서 주인이 승인해서 바꿨어요.")
    log.info("바꾸기 요청 승인 (%s)", r.by)
    return {"ok": True, "status": r.status, **res}


# ================================================================ 새 회의 = 기본 원본으로

default_is_google = False  # 서버를 SEED=google로 켰는가 (app.load_google_source가 정함. 시작 때 못 읽어 sprint로 떨어져도 True)


def switching() -> bool:
    return _switch_lock.locked()


def _default_ids() -> tuple[str, str] | None:
    sid, did = os.getenv("GOOGLE_SHEET_ID", "").strip(), os.getenv("GOOGLE_DOC_ID", "").strip()
    if not (default_is_google and sid and did):
        return None
    return google_auth.parse_id(sid), google_auth.parse_id(did)


async def back_to_default(keep: bool | None = None) -> str:
    """회의 끝 화면의 '새 회의': .env 기본 원본(서버 계정)으로 바꾸며 새 회의를 연다.

    keep: 지금 문서에 회의 결과를 남기나 (None = keep_default: 기본 WBS면 되돌리기, 각자 문서면 남기기).
    돌려주는 값: "switched" 기본 원본으로 바꿔서 새 회의 / "kept" 지금 문서에 남기고 그 문서를 다시 읽어 새 회의 /
    "already" 이미 기본 원본 → 부르는 쪽이 보통 리셋 / "none" 원본 모드가 아님 → 보통 리셋 /
    "failed" 기본 원본을 못 엶(토큰 만료 등) → 부르는 쪽이 보통 리셋, 회의는 지금 문서로 /
    "failed_kept" 기본 원본을 못 열어 지금 문서에 남기고 그 문서로 새 회의까지 끝냄.
    "switched"·"kept"·"failed_kept"는 새 회의까지 끝난 것 (부르는 쪽은 리셋하지 않는다).
    """
    from server.room import get_room

    keep = _keep(keep)
    ids = _default_ids()
    if ids is None and not (keep and google_source.active()):
        return "none"
    if _switch_lock.locked():
        raise HTTPException(409, "다른 사람이 문서를 바꾸는 중이에요.")
    async with _switch_lock:
        S = google_source.S

        async def keep_here() -> None:
            """지금 문서에 남기고, 그 문서를 지금 주인 토큰으로 다시 읽어 새 회의 (주인은 그대로)."""
            await _reset_onto(get_room(), S.sheet_id, S.doc_id, google_auth._owner, google_auth._owner_label,
                              _owner_gsid, _owner_name, keep=True)

        if ids is None:
            await keep_here()
            return "kept"
        sid, did = ids
        if S.active and _owner_gsid is None and google_auth.owner() is None and (S.sheet_id, S.doc_id) == ids:
            if keep:
                await keep_here()
                return "kept"
            return "already"

        def prepare() -> None:  # 1. 서버 계정으로 기본 원본 구조 확인 (회의와 지금 주인은 그대로)
            with google_auth.as_owner(None, None):
                google_source.load(sid, did)
        try:
            await outbox.run_exclusive(prepare)
        except Exception as e:
            log.warning("새 회의: 기본 원본을 못 열어 지금 문서로 시작: %s", str(e)[:200])
            if keep and google_source.active():
                await keep_here()
                return "failed_kept"
            return "failed"
        try:
            st = await _reset_onto(get_room(), sid, did, None, None, None, None, keep=keep)
        except HTTPException as e:  # 드묾: 확인 뒤 기본 원본이 바뀜. 지금 원본은 이미 복원(또는 남김) + 새 회의
            log.warning("새 회의: 기본 원본 commit 실패, 지금 문서로 시작: %s", e.detail)
            if keep:  # 남긴 문서의 옛 시작점 사본으로 리셋하면 화면과 문서가 어긋난다 → 다시 읽는다
                await keep_here()
                return "failed_kept"
            return "failed"
        log.info("새 회의: 기본 원본으로 (시트 %d행, 문서 섹션 %d개, 옛 문서 %s)",
                 len(st["board"].rows), len(st["notes"].sections), "남김" if keep else "되돌림")
        return "switched"
