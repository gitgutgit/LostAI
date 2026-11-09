"""Sync Outbox: 워커 1개로 외부 동기화를 줄 세운다 (docs/ARCHITECTURE.md 3-5).

PoC 실측: Google 8스레드 동시 호출 → 16건 중 12건 SSL 실패, 1스레드 → 16건 모두 성공.
화면은 이걸 기다리지 않는다. 결과는 sync.ok / sync.failed 이벤트로만 보인다.
"""
from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING, Any

from server.ops.registry import OPS
from server.sync import google_docs, google_sheets, linear

if TYPE_CHECKING:
    from server.room import Room

MAX_RETRIES = 3
TARGETS = {"sheets": ("google_sheets", google_sheets), "docs": ("google_docs", google_docs),
           "linear": ("linear", linear)}


class Outbox:
    def __init__(self) -> None:
        self.queue: asyncio.Queue[tuple["Room", str, dict[str, Any]]] = asyncio.Queue()
        self._worker: asyncio.Task | None = None

    def start(self) -> None:
        if self._worker is None:
            self._worker = asyncio.create_task(self._run())

    def enqueue(self, room: "Room", event_type: str, change: dict[str, Any]) -> None:
        self.queue.put_nowait((room, event_type, change))

    async def _run(self) -> None:
        while True:
            room, event_type, change = await self.queue.get()
            targets = {OPS[o["op"]].google for o in change["ops"] if o["op"] in OPS} - {None}
            for t in sorted(targets):  # type: ignore[arg-type]
                name, mod = TARGETS[t]
                if not mod.enabled():
                    continue
                await self._push(room, name, mod, event_type, change)
            self.queue.task_done()

    async def _push(self, room: "Room", name: str, mod: Any, event_type: str, change: dict[str, Any]) -> None:
        refs = {"change_id": change["change_id"], "utt_id": change.get("utt_id")}
        for attempt in range(1, MAX_RETRIES + 1):
            t0 = time.perf_counter()
            try:
                # 블로킹 Google 클라이언트를 쓰더라도 워커가 하나라 동시 호출은 생기지 않는다
                await asyncio.to_thread(mod.push, room.state, event_type, change)
                await room.emit("sync.ok", "server", refs,
                                {"target": name, "ms": int((time.perf_counter() - t0) * 1000)})
                return
            except Exception as e:
                if attempt == MAX_RETRIES:
                    await room.emit("sync.failed", "server", refs, {"target": name, "error": str(e)[:200]})
                else:
                    await asyncio.sleep(0.5 * attempt)


outbox = Outbox()
