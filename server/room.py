"""회의방: 이벤트 로그(append-only), 발화 큐, 브로드캐스트 (docs/ARCHITECTURE.md 3-1, 5-1)."""
from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Protocol

from server.events import Event, Refs
from server.model.docs import DocState, load_seed
from server.ops.changes import Change, ChangeManager

RECENT_EVENTS_ON_CONNECT = 500

log = logging.getLogger(__name__)


class Socket(Protocol):
    async def send_text(self, data: str) -> None: ...


class Room:
    def __init__(self, room_id: str = "main", seed: str | None = None):
        self.room_id = room_id
        self.seed_name = seed or os.getenv("SEED", "sprint")
        self.sockets: dict[Socket, str] = {}  # socket → 참석자 이름
        self.participants: dict[str, dict[str, Any]] = {}
        self._worker: asyncio.Task | None = None
        self._init_meeting()

    def _init_meeting(self) -> None:
        """회의 내용(시간, 이벤트와 로그 파일, 일시정지, 문서, 변경, 발화 큐)만 처음 상태로. 접속과 참석자는 그대로."""
        self.t0 = time.perf_counter()  # Windows monotonic은 15.6ms 단위라 지연 측정에 부족
        self.events: list[Event] = []
        self.paused = False
        self.utterance_queue: asyncio.Queue[Event] = asyncio.Queue()
        if self.seed_name == "google":  # 원본 문서 모드: 서버 시작 때 불러온 원본 (server/sync/google_source.py)
            from server.sync import google_source
            self.state: DocState = google_source.baseline_copy()
        else:
            self.state = load_seed(self.seed_name)
        self.changes = ChangeManager(
            self.state, self._emit_from_changes, self.now,
            policy=os.getenv("COMMIT_POLICY", "immediate"),  # type: ignore[arg-type]
            delay_sec=float(os.getenv("DELAYED_COMMIT_SEC", "5")),
        )
        log_dir = Path(os.getenv("EVENT_LOG_DIR", "results"))
        log_dir.mkdir(parents=True, exist_ok=True)
        self.log_path = log_dir / f"events_{self.room_id}_{time.strftime('%m%d_%H%M%S')}.jsonl"

    async def reset(self) -> list[Change]:
        """같은 방 객체에서 회의 내용만 시드 상태로 되돌린다. 접속과 참석자는 그대로 둔다.

        방 객체를 새로 만들면 접속 중인 화면은 옛 방에 남아(옛 방 워커는 멈춤) 이후 발화가 처리되지 않는다.
        진행 중이던 발화 처리, 지연 반영 타이머, 표결은 취소하고 큐에서 기다리던 발화는 버린다.
        그 순간 처리 중이던 소켓 요청(버튼, 제스처)까지는 막지 않는다.
        """
        worker, self._worker = self._worker, None
        if worker is not None:
            worker.cancel()
            if worker.get_loop() is asyncio.get_running_loop():  # 취소가 끝날 때까지 기다려 옛 결과가 새 회의에 emit되지 않게
                try:
                    await worker
                except asyncio.CancelledError:
                    pass
                except Exception:  # 이미 죽어 있던 워커: 기록만 하고 리셋은 끝까지 한다
                    log.exception("utterance worker had died before reset")
        for t in self.changes._timers.values():
            t.cancel()
        from server.gestures.votes import votes  # 순환 import 방지
        votes.reset()  # 옛 회의의 표결 마감이 새 회의에 끼어들지 않게
        old_changes = list(self.changes.changes.values())  # 원본 문서 복원용 (app.reset → outbox.enqueue_restore)
        self._init_meeting()
        self.start()
        return old_changes

    # ---- 시간 ----
    def now(self) -> float:
        return round(time.perf_counter() - self.t0, 3)

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
    async def connect(self, ws: Socket, name: str) -> bool:
        """접속. 토큰은 유효한데 참석자 목록에 없으면(서버 재배포·리셋 뒤 다시 붙음) 다시 넣고 True."""
        self.sockets[ws] = name
        rejoined = name not in self.participants
        if rejoined:  # gitgutgit 11-09: 재배포하면 방이 비므로, 다시 붙은 사람을 참석자로 되살린다
            self.participants[name] = {"verified": True, "via": "rejoin"}
        await ws.send_text(json.dumps(self.snapshot(), ensure_ascii=False, default=str))
        return rejoined

    def disconnect(self, ws: Socket) -> bool:
        """접속 하나를 뺀다. 그 이름의 탭이 하나도 안 남으면 참석자에서 빼고 True (회의 나가기, 탭 닫기)."""
        name = self.sockets.pop(ws, None)
        if name is None or name in self.sockets.values():
            return False
        self.participants.pop(name, None)
        return True

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
                log.exception("utterance failed utt=%s", ev.refs.utt_id)
                await self.emit("agent.progress", "agent", {"utt_id": ev.refs.utt_id},
                                {"stage": "failed", "error": str(e)[:200],
                                 "ms": int((self.now() - ev.ts) * 1000)})
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
