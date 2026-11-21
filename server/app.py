"""FastAPI 서버: 입장 관문, WebSocket, 통계 (docs/ARCHITECTURE.md 2절).

실행: uv run uvicorn server.app:app --reload --port 8000
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect  # noqa: E402
from pydantic import BaseModel  # noqa: E402

from server.auth import challenge  # noqa: E402
from server.events import ClientMessage  # noqa: E402
from server.gestures.fastpath import handle_gesture  # noqa: E402
from server.room import get_room  # noqa: E402
from server.demo import demo  # noqa: E402
from server.common.warmup import schedule_warmup  # noqa: E402
from server.sync.outbox import outbox  # noqa: E402

log = logging.getLogger(__name__)
_WEB_DIST = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "web", "dist")  # 배포 때 화면 빌드


@asynccontextmanager
async def lifespan(_: FastAPI):
    await load_google_source()      # SEED=google: 원본 Sheet/Doc을 회의 시작 상태로 (Outbox 시작 전 1회)
    room = get_room()
    room.start()
    outbox.start()
    outbox.enqueue_full_sync(room)  # 외부 문서를 시드 상태로 맞추고 Google 연결도 미리 데움
    schedule_warmup(room.state)     # LIVE면 라우터·에디터 미리 호출 (첫 발화 콜드 스타트 제거)
    yield
    _cancel_empty_reset()  # 꺼지면서 접속이 다 끊겨도 새 회의를 열지 않는다 (복원은 아래가 한다)
    await restore_on_shutdown()


async def restore_on_shutdown(timeout: float = 25.0) -> None:
    """원본 모드에서 서버가 꺼질 때(Ctrl+C, Railway 재배포의 SIGTERM) 회의 중 변경을 되돌려 원본을 회의 전으로.
    안 하면 다음 시작 때 회의 중 변경까지 원본으로 읽힌다. 강제 종료(kill -9)에는 못 돈다 → 끄기 전 리셋이 가장 확실."""
    import asyncio
    from server.sync import google_source
    if not google_source.active():
        return
    room = get_room()
    active = [c.model_dump() for c in room.changes.changes.values() if c.status in ("applied", "approved")]
    if not active:
        return
    log.warning("서버 종료: 회의 중 변경 %d개를 원본에서 되돌리는 중", len(active))
    outbox.enqueue_restore(room, active)
    try:
        await asyncio.wait_for(outbox.queue.join(), timeout)
        log.warning("서버 종료: 원본 복원 끝")
    except asyncio.TimeoutError:
        log.error("서버 종료: 원본 복원이 %.0f초 안에 안 끝남 → Google 문서 버전 기록으로 확인", timeout)


async def load_google_source() -> None:
    if os.getenv("SEED") != "google":
        return
    import asyncio
    import logging
    from server.sync import google_source, source_api
    source_api.default_is_google = True  # 회의 끝 '새 회의'는 이 기본 원본으로 (못 읽어 sprint로 떨어져도 다음에 다시 시도)
    log = logging.getLogger("uvicorn.error")
    try:
        await asyncio.to_thread(google_source.pull_baseline)
        b = google_source.baseline_copy()
        log.info("원본 문서 불러옴: 시트 %d행, 문서 섹션 %d개", len(b.docs["board"].rows), len(b.docs["notes"].sections))
    except Exception as e:  # 원본을 못 읽으면 시드로 (회의는 연다)
        log.warning("원본 문서 불러오기 실패 → SEED=sprint로 시작: %s", str(e)[:200])
        os.environ["SEED"] = "sprint"


app = FastAPI(title="meeting-agent", lifespan=lifespan)

from server.sync.source_api import router as source_router  # noqa: E402  문서 고르기·새로 만들기

app.include_router(source_router)


# ---------------------------------------------------------------- 입장 관문

class JoinReq(BaseModel):
    name: str


class StepReq(BaseModel):
    gesture: str
    confidence: float
    hold_ms: int


@app.post("/api/join")
async def join(req: JoinReq):
    ch = challenge.issue(req.name)
    room = get_room()
    await room.emit("participant.joined", req.name, {}, {"name": req.name})
    return {"challenge_id": ch.challenge_id, "gestures": ch.gestures, "ttl_sec": challenge.CHALLENGE_TTL_SEC}


@app.post("/api/join/{challenge_id}/step")
async def join_step(challenge_id: str, req: StepReq):
    res = challenge.submit_step(challenge_id, req.gesture, req.confidence, req.hold_ms)
    if res["status"] == "pass":
        name = res["token"].rpartition(".")[0]
        room = get_room()
        room.participants[name] = {"verified": True, "via": "gesture"}
        await room.emit("participant.verified", name, {},
                        {"name": name, "gestures": res["gestures"], "result": "pass", "elapsed_ms": res["elapsed_ms"]})
    return res


class ManualReq(BaseModel):
    name: str
    host: str


@app.post("/api/join/manual")
async def join_manual(req: ManualReq):
    """3번 실패 시 호스트가 수동으로 들여보낸다 (시연 사고 대비)."""
    room = get_room()
    room.participants[req.name] = {"verified": True, "via": "manual", "by": req.host}
    await room.emit("participant.verified", req.host, {}, {"name": req.name, "result": "manual"})
    return {"token": challenge.make_token(req.name)}


# ---------------------------------------------------------------- 회의

async def _notice(ws: WebSocket, text: str) -> None:
    await ws.send_text(json.dumps({"kind": "notice", "text": text}, ensure_ascii=False))


async def _handle_client_message(room, name: str, raw: str, ws: WebSocket) -> None:
    msg = ClientMessage.model_validate(json.loads(raw))
    p = msg.payload
    if msg.kind in ("utterance.final", "utterance.interim"):
        text = p.get("text")
        if not isinstance(text, str):  # 화면 쪽 형식 오류는 알린다(조용히 버리면 에이전트가 말을 무시하는 것처럼 보인다)
            raise ValueError(f"utterance payload has no text: keys={sorted(p)}")
        if not text.strip():
            return  # 빈 인식 결과
        await room.submit_utterance(name, text, final=msg.kind == "utterance.final")
    elif msg.kind == "gesture":
        await handle_gesture(room, name, p["kind"], float(p.get("confidence", 1)), int(p.get("hold_ms", 0)))
    elif msg.kind in ("change.approve", "change.revert"):
        act = room.changes.approve if msg.kind == "change.approve" else room.changes.revert
        err = await act(p["change_id"], by=name, via="button")
        if err:
            await _notice(ws, err)


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket, token: str = ""):  # 토큰이 빠져도 검증 오류(403) 대신 4401로 닫는다
    name = challenge.verify_token(token)
    # accept 전에 close하면 uvicorn이 HTTP 403으로 바꿔 보내 브라우저는 4401을 못 보고 계속 다시 붙는다
    await ws.accept()
    if name is None:
        await ws.close(code=4401)
        return
    room = get_room()  # 리셋은 같은 방 객체를 그 자리에서 비우므로 이 참조는 계속 유효하다
    _cancel_empty_reset()  # 새로고침·잠깐 끊김: 유예 시간 안에 다시 붙으면 회의 그대로
    if await room.connect(ws, name):
        await room.emit("participant.verified", name, {}, {"name": name, "result": "pass", "via": "rejoin"})
    close_code = None
    try:
        while True:
            raw = await ws.receive_text()
            try:
                await _handle_client_message(room, name, raw, ws)
            except Exception as e:  # 잘못된 메시지 하나로 접속을 끊지 않는다. 원인은 서버 로그에 남긴다
                log.exception("ws message failed name=%s raw=%.200s", name, raw)
                await _notice(ws, f"요청을 처리하지 못했어요 ({type(e).__name__}: {str(e)[:120]})")
    except WebSocketDisconnect as e:
        close_code = e.code
    finally:
        # 1000 = 화면의 🚪 회의 나가기 (core/ws.ts leave). 탭 닫기 1001, 끊김 1006
        if room.disconnect(ws, left_by_button=close_code == 1000):  # 같은 이름의 다른 탭이 남아 있으면 나간 게 아니다
            await room.emit("participant.left", name, {}, {"name": name})
        after_disconnect(room)


# ---- 모두 나가면 새 회의 (Mal-Mi-Jal) ----
# 마지막 접속이 끊기고 EMPTY_ROOM_GRACE_SEC 안에 아무도 다시 안 붙으면 '새 회의'와 같은 길로 기본 문서로 돌아간다.
# 유예를 두는 이유: 혼자 새로고침해도 옛 탭이 끊기고 새 탭이 붙기 전까지 접속이 잠깐 0이 된다.
EMPTY_ROOM_GRACE_SEC = float(os.getenv("EMPTY_ROOM_GRACE_SEC", "5"))
_empty_task: asyncio.Task | None = None
_empty_resetting = False  # 새 회의를 여는 중에는 취소하지 않는다 (Google 작업 도중에 끊으면 문서가 어중간해진다)


def after_disconnect(room) -> None:
    """접속 하나가 끊긴 뒤. 남은 접속이 없으면 유예 타이머를 건다."""
    global _empty_task
    if room.sockets:
        return
    _cancel_empty_reset()
    _empty_task = asyncio.create_task(_reset_when_empty(room))


def _cancel_empty_reset() -> None:
    global _empty_task
    if _empty_task is not None and not _empty_task.done() and not _empty_resetting:
        _empty_task.cancel()


async def _reset_when_empty(room) -> None:
    global _empty_resetting
    from server.sync import source_api
    while True:
        await asyncio.sleep(EMPTY_ROOM_GRACE_SEC)
        if room.sockets:  # 그사이 누가 붙음 (보통은 connect가 이미 취소함)
            return
        if not source_api.switching():  # 누가 문서를 바꾸는 중이면 끝난 뒤 다시 본다
            break
    if not room.changes.changes and source_api.at_default():
        return  # 이미 기본 문서의 빈 회의 → 할 일 없음 (Google에 쓸데없이 다시 쓰지 않는다)
    _empty_resetting = True
    try:
        source_api.cancel_request("회의에 아무도 남지 않아 요청을 닫았어요.")
        how = await start_new_meeting(None)  # 남기기/되돌리기 = 기본값 (기본 WBS 되돌리기, 각자 문서 남기기)
        log.info("모두 나감 → 새 회의 (%s)", how)
    except Exception:
        log.exception("모두 나감: 새 회의를 열지 못함")
    finally:
        _empty_resetting = False


@app.get("/api/state")
async def state():
    return get_room().snapshot()


@app.get("/api/links")
async def links(token: str):
    """실제 Google 문서 바로가기. 입장한 참가자(토큰)에게만 준다 — 문서 주소는 로그·이벤트에 안 남긴다.
    Google을 새로 부르지 않는다 (호출은 Outbox 워커만): 탭 위치는 시작 동기화 때 캐시된 값만 쓴다."""
    if challenge.verify_token(token) is None:
        raise HTTPException(401, "invalid token")
    from server.sync import google_docs, google_sheets, google_source
    if google_source.active():  # 원본 모드: 원본 탭으로 바로
        return {**google_source.links(), "doc_sync": True}
    sheet = None
    if google_sheets.enabled():
        sid = google_sheets.spreadsheet_id()
        sheet = f"https://docs.google.com/spreadsheets/d/{sid}/edit"
        board = next((d.title for d in get_room().state.docs.values() if d.kind == "sheet"), None)
        gid = google_sheets._tabs.get(sid, {}).get(board) if board else None
        if gid is not None:
            sheet += f"#gid={gid}"
    doc = None
    if google_docs.enabled():
        from server.sync.google_auth import parse_id
        doc = f"https://docs.google.com/document/d/{parse_id(os.environ['GOOGLE_DOC_ID'])}/edit"
        notes = next((d.title for d in get_room().state.docs.values() if d.kind == "doc"), None)
        tab = google_docs.tab_id_for(notes) if notes else None
        if tab:
            doc += f"?tab={tab}"  # 회의 노트 전용 탭으로 바로
    return {"sheet": sheet, "doc": doc, "doc_sync": getattr(google_docs, "IMPLEMENTED", False)}


@app.get("/api/stats")
async def stats():
    """말 → 화면 / 말 → Google 문서 / 단계별 지연 (이벤트 로그 기준, server/common/event_latency.py).

    failed_utterances: 처리 중 예외(LLM 시간 초과 등)로 끝난 발화 수. 지연 분포에는 들어가지 않으므로 따로 본다.
    """
    from server.agent.llm import is_live
    from server.common.event_latency import summarize
    room = get_room()
    s = summarize(room.events)
    return {"mode": "LIVE" if is_live() else "MOCK",
            "changes": sum(1 for c in room.changes.changes.values() if c.status != "failed"),
            "utterances": s["utterances"], "latency_ms": s["latency_ms"], "vs_goal": s["vs_goal"],
            "failed_utterances": sum(1 for e in room.events
                                     if e.type == "agent.progress" and e.payload.get("stage") == "failed"),
            "events": len(room.events)}


SEED_DIR = Path(__file__).parent / "model" / "seeds"


def _seed_names() -> list[str]:
    return sorted(p.stem for p in SEED_DIR.glob("*.json"))


@app.get("/api/seeds")
async def seeds():
    """테스트용 시드(대본 시작 상태) 목록과 지금 쓰는 시드. 원본 문서 모드(SEED=google)에서는 바꿀 수 없다."""
    from server.sync import google_source
    out = []
    for name in _seed_names():
        try:
            data = json.loads((SEED_DIR / f"{name}.json").read_text(encoding="utf-8"))
            title = next((d.get("title") for d in data.get("docs", {}).values() if d.get("kind") == "sheet"), name)
        except (OSError, ValueError):
            title = name
        out.append({"name": name, "title": title})
    return {"current": get_room().seed_name, "seeds": out, "locked": google_source.active()}


class ResetBody(BaseModel):
    seed: str | None = None  # 주면 이 시드로 바꿔서 시작 (테스트용)


@app.post("/api/reset")
async def reset(body: ResetBody | None = None):
    """회의 내용을 시드로 되돌린다. 접속 중인 화면은 끊지 않고 새 스냅샷을 받는다.

    원본 문서 모드면 회의 중 적용된 변경을 역순으로 되돌려 Google 원본도 회의 시작 전으로 (Outbox 줄 맨 앞에서).
    body.seed를 주면 그 시드로 바꿔서 시작한다 (테스트 대본 선택). 원본 문서 모드에서는 거절한다.
    """
    from server.sync import google_source
    room = get_room()
    await demo.stop()  # 재생 중이던 대본이 새 회의에 말하지 않게
    seed = body.seed if body else None
    if seed and seed != room.seed_name:
        if google_source.active():
            raise HTTPException(409, "원본 문서 모드(SEED=google)에서는 시드를 바꿀 수 없음")
        if seed not in _seed_names():
            raise HTTPException(404, f"seed not found: {seed}")
        room.seed_name = seed  # 아래 room.reset()이 이 이름으로 시드를 다시 읽는다
    old_changes = await room.reset()  # 워커·타이머를 멈춘 뒤의 변경 목록 → 그 사이 적용된 것도 빠지지 않는다
    await room.emit("room.reset", "server", {}, {})
    await room.broadcast(room.snapshot())
    if google_source.active():
        active = [c.model_dump() for c in old_changes if c.status in ("applied", "approved")]
        outbox.enqueue_restore(room, active)
    outbox.enqueue_full_sync(room)
    schedule_warmup(room.state)  # 시연 직전 리셋 → 프롬프트 캐시(약 5분)를 다시 데움
    return {"ok": True}


class NewMeetingBody(BaseModel):
    token: str
    keep: bool | None = None  # 지금 문서에 회의 결과를 남기나 (None = 기본값: 기본 WBS면 되돌리기, 각자 문서면 남기기)


@app.post("/api/meeting/new")
async def new_meeting(body: NewMeetingBody):
    """회의 끝 화면의 '새 회의'. 입장한 사람만.

    SEED=google로 켠 서버면 .env 기본 원본(서버 계정)으로 바꿔서 새 회의 — 누가 다른 문서로 바꿨어도 기본으로 돌아온다.
    이미 기본 원본이거나 기본 원본이 없으면(SEED=sprint) 보통 리셋. 기본 원본을 못 열면(토큰 만료 등) 지금 문서로 리셋.
    """
    from server.sync import source_api
    if challenge.verify_token(body.token) is None:
        raise HTTPException(401, "invalid token")
    if source_api.switching():
        raise HTTPException(409, "다른 사람이 문서를 바꾸는 중이에요.")
    how = await start_new_meeting(body.keep)
    return {"ok": True, "source": "default" if how in ("switched", "already") else "current",
            **({"notice": "기본 문서를 열지 못해 지금 문서로 새 회의를 시작했어요."} if how.startswith("failed") else {})}


async def start_new_meeting(keep: bool | None) -> str:
    """'새 회의' 버튼과 '모두 나감'이 같이 쓰는 길. 돌려주는 값은 source_api.back_to_default와 같다."""
    from server.sync import source_api
    await demo.stop()
    how = await source_api.back_to_default(keep)
    if how in ("already", "none", "failed"):
        await reset()  # 되돌리기 리셋 (남기기 경로는 back_to_default가 새 회의까지 끝냈다)
    return how


@app.get("/api/demo")
async def demo_status():
    """지금 시드의 데모 대본 줄 수와 재생 상태 (대본이 없으면 lines 0)."""
    return demo.status(get_room().seed_name)


class DemoBody(BaseModel):
    speed: float = 1.0


@app.post("/api/demo/start")
async def demo_start(body: DemoBody | None = None):
    """회의를 처음 상태로 되돌린 뒤 지금 시드의 대본을 자동 재생한다 (server/demo.py)."""
    room = get_room()
    if demo.status(room.seed_name)["lines"] == 0:
        raise HTTPException(404, f"no demo script for seed: {room.seed_name}")
    await reset(None)
    speed = min(4.0, max(0.25, body.speed if body else 1.0))
    return {"ok": True, "lines": demo.start(room, speed)}


@app.post("/api/demo/stop")
async def demo_stop():
    await demo.stop()
    return {"ok": True}


@app.get("/health")
async def health():
    """배포 확인용: 비밀 값은 없이 있다/없다만."""
    from server.sync import google_auth, google_source
    return {"ok": True, "image": os.getenv("LOSTAI_IMAGE", "local"), "web": os.path.isdir(_WEB_DIST),
            "google_token": google_auth.token_path().exists() or bool(os.getenv("GOOGLE_TOKEN_JSON") or os.getenv("GOOGLE_TOKEN_B64")),
            "source": google_source.active(), "seed": get_room().seed_name}


# ---- 배포(Railway 등): 빌드된 화면(web/dist)을 같은 서버가 내보낸다. 개발 때는 Vite(5173)가 프록시하므로 없음.
# API·WebSocket 라우트가 먼저 잡히고, 나머지 경로만 화면 파일로 간다 (맨 마지막에 둔다).
if os.path.isdir(_WEB_DIST):
    from fastapi.staticfiles import StaticFiles
    app.mount("/", StaticFiles(directory=_WEB_DIST, html=True), name="web")
