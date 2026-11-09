"""FastAPI 서버: 입장 관문, WebSocket, 통계 (docs/ARCHITECTURE.md 2절).

실행: uv run uvicorn server.app:app --reload --port 8000
"""
from __future__ import annotations

import json
from contextlib import asynccontextmanager

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect  # noqa: E402
from pydantic import BaseModel  # noqa: E402

from server.auth import challenge  # noqa: E402
from server.events import ClientMessage  # noqa: E402
from server.gestures.fastpath import handle_gesture  # noqa: E402
from server.room import get_room  # noqa: E402
from server.sync.outbox import outbox  # noqa: E402


@asynccontextmanager
async def lifespan(_: FastAPI):
    get_room().start()
    outbox.start()
    yield


app = FastAPI(title="meeting-agent", lifespan=lifespan)


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

@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket, token: str):
    name = challenge.verify_token(token)
    if name is None:
        await ws.close(code=4401)
        return
    await ws.accept()
    room = get_room()
    await room.connect(ws, name)
    try:
        while True:
            msg = ClientMessage.model_validate(json.loads(await ws.receive_text()))
            p = msg.payload
            if msg.kind in ("utterance.final", "utterance.interim"):
                await room.submit_utterance(name, p["text"], final=msg.kind == "utterance.final")
            elif msg.kind == "gesture":
                await handle_gesture(room, name, p["kind"], float(p.get("confidence", 1)), int(p.get("hold_ms", 0)))
            elif msg.kind == "change.approve":
                await room.changes.approve(p["change_id"], by=name, via="button")
            elif msg.kind == "change.revert":
                err = await room.changes.revert(p["change_id"], by=name, via="button")
                if err:
                    await ws.send_text(json.dumps({"kind": "notice", "text": err}, ensure_ascii=False))
    except WebSocketDisconnect:
        room.disconnect(ws)
        await room.emit("participant.left", name, {}, {"name": name})


@app.get("/api/state")
async def state():
    return get_room().snapshot()


@app.get("/api/stats")
async def stats():
    """말 → 화면 지연 등. 단계별 latency_ms를 모은다."""
    room = get_room()
    rows = [c.latency_ms for c in room.changes.changes.values() if c.status != "failed"]
    from server.common.latency import percentiles
    keys = sorted({k for r in rows for k in r})
    return {"changes": len(rows), "latency_ms": {k: percentiles([r[k] for r in rows if k in r]) for k in keys},
            "events": len(room.events)}


@app.post("/api/reset")
async def reset():
    from server import room as room_mod
    old = room_mod.rooms.pop("main", None)
    if old and old._worker:
        old._worker.cancel()
    new = get_room()
    new.start()
    await new.emit("room.reset", "server", {}, {})
    return {"ok": True}


@app.get("/health")
async def health():
    return {"ok": True}
