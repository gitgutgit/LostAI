"""FastAPI 서버: 입장 관문, WebSocket, 통계 (docs/ARCHITECTURE.md 2절).

실행: uv run uvicorn server.app:app --reload --port 8000
"""
from __future__ import annotations

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
from server.common.warmup import schedule_warmup  # noqa: E402
from server.sync.outbox import outbox  # noqa: E402

log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    await load_google_source()      # SEED=google: 원본 Sheet/Doc을 회의 시작 상태로 (Outbox 시작 전 1회)
    room = get_room()
    room.start()
    outbox.start()
    outbox.enqueue_full_sync(room)  # 외부 문서를 시드 상태로 맞추고 Google 연결도 미리 데움
    schedule_warmup(room.state)     # LIVE면 라우터·에디터 미리 호출 (첫 발화 콜드 스타트 제거)
    yield


async def load_google_source() -> None:
    if os.getenv("SEED") != "google":
        return
    import asyncio
    import logging
    from server.sync import google_source
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
    await room.connect(ws, name)
    try:
        while True:
            raw = await ws.receive_text()
            try:
                await _handle_client_message(room, name, raw, ws)
            except Exception as e:  # 잘못된 메시지 하나로 접속을 끊지 않는다. 원인은 서버 로그에 남긴다
                log.exception("ws message failed name=%s raw=%.200s", name, raw)
                await _notice(ws, f"요청을 처리하지 못했어요 ({type(e).__name__}: {str(e)[:120]})")
    except WebSocketDisconnect:
        pass
    finally:
        room.disconnect(ws)
        await room.emit("participant.left", name, {}, {"name": name})


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


@app.get("/health")
async def health():
    return {"ok": True}
