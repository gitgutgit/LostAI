"""FastAPI 서버: 입장 관문, WebSocket, 통계 (docs/ARCHITECTURE.md 2절).

실행: uv run uvicorn server.app:app --reload --port 8000
"""
from __future__ import annotations

import json
import os
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
    room = get_room()
    room.start()
    outbox.start()
    outbox.enqueue_full_sync(room)  # 외부 문서를 시드 상태로 맞추고 Google 연결도 미리 데움
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


@app.get("/api/links")
async def links(token: str):
    """실제 Google 문서 바로가기. 입장한 참가자(토큰)에게만 준다 — 문서 주소는 로그·이벤트에 안 남긴다.
    Google을 새로 부르지 않는다 (호출은 Outbox 워커만): 탭 위치는 시작 동기화 때 캐시된 값만 쓴다."""
    if challenge.verify_token(token) is None:
        raise HTTPException(401, "invalid token")
    from server.sync import google_docs, google_sheets
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
    """말 → 화면 / 말 → Google 문서 / 단계별 지연 (이벤트 로그 기준, server/common/event_latency.py)."""
    from server.agent.llm import is_live
    from server.common.event_latency import summarize
    room = get_room()
    s = summarize(room.events)
    return {"mode": "LIVE" if is_live() else "MOCK",
            "changes": sum(1 for c in room.changes.changes.values() if c.status != "failed"),
            "utterances": s["utterances"], "latency_ms": s["latency_ms"], "vs_goal": s["vs_goal"],
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
    outbox.enqueue_full_sync(new)
    return {"ok": True}


@app.get("/health")
async def health():
    return {"ok": True}
