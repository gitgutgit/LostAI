"""회의방: 이벤트 로그(append-only), 발화 큐, 브로드캐스트 (docs/ARCHITECTURE.md 3-1, 5-1)."""
from __future__ import annotations

import asyncio
import json
import os
import time
from pathlib import Path
from typing import Any, Protocol

from server.events import Event, Refs
from server.model.docs import DocState, load_seed
from server.ops.changes import ChangeManager

RECENT_EVENTS_ON_CONNECT = 500


class Socket(Protocol):
    async def send_text(self, data: str) -> None: ...


class Room:
    def __init__(self, room_id: str = "main", seed: str | None = None):
        self.room_id = room_id
        self.seed_name = seed or os.getenv("SEED", "sprint")
        self.t0 = time.monotonic()
        self.events: list[Event] = []
        self.sockets: dict[Socket, str] = {}  # socket → 참석자 이름
        self.participants: dict[str, dict[str, Any]] = {}
        self.paused = False
        self.utterance_queue: asyncio.Queue[Event] = asyncio.Queue()
        self.state: DocState = load_seed(self.seed_name)
        self.changes = ChangeManager(
            self.state, self._emit_from_changes, self.now,
            policy=os.getenv("COMMIT_POLICY", "immediate"),  # type: ignore[arg-type]
            delay_sec=float(os.getenv("DELAYED_COMMIT_SEC", "5")),
        )
        log_dir = Path(os.getenv("EVENT_LOG_DIR", "results"))
        log_dir.mkdir(parents=True, exist_ok=True)
        self.log_path = log_dir / f"events_{room_id}_{time.strftime('%m%d_%H%M%S')}.jsonl"
        self._worker: asyncio.Task | None = None

    # ---- 시간 ----
    def now(self) -> float:
        return round(time.monotonic() - self.t0, 3)

    # ---- 이벤트 ----
    async def emit(self, type_: str, actor: str, refs: dict[str, Any] | None = None,
                   payload: dict[str, Any] | None = None) -> Event:
        ev = Event(seq=len(self.events) + 1, ts=self.now(), type=type_,  # type: ignore[arg-type]
                   actor=actor, refs=Refs(**(refs or {})), payload=payload or {})
        self.events.append(ev)
        with self.log_path.open("a", encoding="utf-8") as f:
            f.write(ev.model_dump_json() + "\n")
        await self.broadcast({"kind": "event", "event": ev.model_dump()})
        return ev

    async def _emit_from_changes(self, type_: str, actor: str, refs: dict[str, Any], payload: dict[str, Any]) -> None:
        await self.emit(type_, actor, refs, payload)
        if type_ in ("change.applied", "change.reverted"):
            from server.sync.outbox import outbox  # 순환 import 방지
            outbox.enqueue(self, type_, payload)

    async def broadcast(self, msg: dict[str, Any]) -> None:
        data = json.dumps(msg, ensure_ascii=False, default=str)
        dead = []
        for ws in list(self.sockets):
            try:
                await ws.send_text(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.sockets.pop(ws, None)

    def snapshot(self) -> dict[str, Any]:
        return {
            "kind": "snapshot",
            "room_id": self.room_id,
            "state": self.state.model_dump(),
            "changes": [c.model_dump() for c in self.changes.changes.values()],
            "events": [e.model_dump() for e in self.events[-RECENT_EVENTS_ON_CONNECT:]],
            "participants": self.participants,
            "paused": self.paused,
        }

    # ---- 접속 ----
    async def connect(self, ws: Socket, name: str) -> None:
        self.sockets[ws] = name
        await ws.send_text(json.dumps(self.snapshot(), ensure_ascii=False, default=str))

    def disconnect(self, ws: Socket) -> str | None:
        return self.sockets.pop(ws, None)

    # ---- 발화 큐: 순서대로 하나씩 ----
    def start(self) -> None:
        # 이전 이벤트 루프에 묶인 워커(테스트에서 서버를 다시 띄울 때)는 버리고 새 루프에서 다시 만든다
        if self._worker is not None and self._worker.get_loop() is not asyncio.get_running_loop():
            self._worker, self.utterance_queue = None, asyncio.Queue()
        if self._worker is None:
            self._worker = asyncio.create_task(self._utterance_worker())

    async def submit_utterance(self, speaker: str, text: str, final: bool = True) -> Event:
        ev = await self.emit("utterance.final" if final else "utterance.interim", speaker,
                             {"utt_id": f"u{len(self.events) + 1}"} if final else {},
                             {"speaker": speaker, "text": text})
        if final:
            await self.utterance_queue.put(ev)
        return ev

    async def _utterance_worker(self) -> None:
        from server.agent.pipeline import handle_utterance
        while True:
            ev = await self.utterance_queue.get()
            try:
                if not self.paused:
                    await handle_utterance(self, ev)
            except Exception as e:  # 회의는 멈추지 않는다
                await self.emit("agent.progress", "agent", {"utt_id": ev.refs.utt_id},
                                {"stage": "failed", "error": str(e)[:200]})
            finally:
                self.utterance_queue.task_done()

    def transcript(self, last_n: int = 12) -> list[dict[str, str]]:
        utts = [e for e in self.events if e.type == "utterance.final"]
        return [{"utt_id": e.refs.utt_id or "", "speaker": e.payload["speaker"], "text": e.payload["text"]}
                for e in utts[-last_n:]]


rooms: dict[str, Room] = {}


def get_room(room_id: str = "main") -> Room:
    if room_id not in rooms:
        rooms[room_id] = Room(room_id)
    return rooms[room_id]
