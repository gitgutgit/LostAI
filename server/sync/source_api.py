"""문서 고르기 API: 회의 원본 Sheet/Doc을 화면에서 고르거나 새로 만든다. author: Mal-Mi-Jal

    GET  /api/google/files?token=&kind=sheet|doc&q=   서버 계정 Drive 목록 (최근 수정 순, 공유받은 문서 포함)
    GET  /api/google/source?token=                    지금 회의 원본 (id·제목)
    POST /api/google/source  {token, sheet, doc, title} sheet·doc: 파일 id | "new" | null(그대로)

바꾸는 순서 (Google 호출은 전부 Outbox 줄 안에서, 동시 호출 없음):
  1. 새 문서 만들기("new") + 고른 문서 미리 읽어 구조 확인 → 못 쓰면 400, 회의는 그대로
  2. 회의 리셋 → 지금 원본은 회의 중 변경을 역순으로 되돌려 회의 전 상태로 (/api/reset과 같은 길)
  3. 되돌리기가 끝난 뒤 새 문서를 다시 읽어 commit (같은 문서를 그대로 둔 쪽도 복원된 상태로 다시 읽힌다)
  4. 한 번 더 리셋 → 새 원본으로 회의 시작, 화면에 새 스냅샷. 2~4 사이에 생긴 변경은 Google에 안 쓰고 버린다
고른 문서는 results/google_source_choice.json 에 남겨 서버를 다시 켜도 그대로 (문서 ID라 출력·커밋 안 함).
"""
from __future__ import annotations

import asyncio
import logging
import os
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from server.auth import challenge
from server.sync import google_auth, google_files, google_source
from server.sync.outbox import outbox

router = APIRouter()
log = logging.getLogger("uvicorn.error")
_switch_lock = asyncio.Lock()


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
        return HTTPException(400, "문서를 열 수 없어요. 서버 계정에 편집 권한이 있는지 확인해 주세요.")
    log.warning("google source error: %s", str(e)[:200])
    return HTTPException(502, "Google 호출이 실패했어요. 잠시 뒤 다시 시도해 주세요.")


@router.get("/api/google/files")
async def files(token: str, kind: Literal["sheet", "doc"], q: str = ""):
    _auth(token)
    if not google_auth.available():
        raise HTTPException(409, "서버에 Google 로그인이 없어요 (server/sync/GOOGLE_SETUP.md).")
    try:
        return {"files": await outbox.run_exclusive(lambda: google_files.list_files(kind, q))}
    except google_files.NeedsRelogin as e:
        raise HTTPException(409, str(e))
    except Exception as e:
        raise _google_error(e)


@router.get("/api/google/source")
async def current(token: str):
    _auth(token)
    S = google_source.S
    if not S.active:
        return {"active": False}
    b = S.baseline
    return {"active": True, "busy": _switch_lock.locked(),
            "sheet": {"id": S.sheet_id, "title": b.docs["board"].title if b else None},
            "doc": {"id": S.doc_id, "title": b.docs["notes"].title if b else None}}


class SwitchReq(BaseModel):
    token: str
    sheet: str | None = None   # 파일 id 또는 "new", None이면 지금 것 그대로
    doc: str | None = None
    title: str = ""            # 새로 만들 때 문서 제목


@router.post("/api/google/source")
async def switch(req: SwitchReq):
    who = _auth(req.token)
    if not req.sheet and not req.doc:
        raise HTTPException(400, "바꿀 Sheet나 Doc을 골라 주세요.")
    if _switch_lock.locked():
        raise HTTPException(409, "다른 사람이 문서를 바꾸는 중이에요.")
    async with _switch_lock:
        return await _switch(req, who)


async def _switch(req: SwitchReq, who: str) -> dict:
    from server.common.warmup import schedule_warmup
    from server.room import get_room

    S = google_source.S
    if (not req.sheet or not req.doc) and not S.active:
        raise HTTPException(400, "지금 원본 문서가 없어서 Sheet와 Doc을 둘 다 골라야 해요.")
    title = req.title.strip() or "회의"

    def prepare() -> tuple[str, str]:
        # 1. 만들기 + 구조 확인 (회의는 아직 그대로)
        sid = (google_files.create_sheet(f"{title} — 보드") if req.sheet == "new"
               else google_auth.parse_id(req.sheet) if req.sheet else S.sheet_id)
        did = (google_files.create_doc(f"{title} — 회의 노트") if req.doc == "new"
               else google_auth.parse_id(req.doc) if req.doc else S.doc_id)
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
            google_source.commit(google_source.load(sid, did))
            google_source.save_choice(sid, did)
        try:
            await outbox.run_exclusive(load_and_commit)
        except Exception as e:  # 드묾: 확인 뒤 문서가 바뀜. 옛 원본은 이미 복원됐고 S도 그대로 → 옛 원본으로 회의 계속
            await room.emit("room.reset", "server", {}, {})
            await room.broadcast(room.snapshot())
            raise _google_error(e) if not isinstance(e, google_source.SourceError) else HTTPException(400, str(e))
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
    log.info("회의 원본을 바꿈 (%s): 시트 %d행, 문서 섹션 %d개", who, len(st["board"].rows), len(st["notes"].sections))
    return {"ok": True, "sheet": {"id": sid, "title": st["board"].title}, "doc": {"id": did, "title": st["notes"].title}}
