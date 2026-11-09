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
RESTORE = "source.restore"  # 원본 모드 리셋: 앞서 넣은 되돌리기들이 끝난 뒤 하이라이트·추가 섹션 정리
CALL = "outbox.call"  # 줄에 서서 함수 하나 실행 (문서 고르기: 목록·만들기·불러오기도 Google 동시 호출 금지)
FULL_SYNC = "sync.full"  # 큐 안에서만 쓰는 작업 이름 (이벤트 type 아님): 서버 시작·리셋 때 전체 미러링


class Outbox:
    def __init__(self) -> None:
        self.queue: asyncio.Queue[tuple["Room", str, dict[str, Any]]] = asyncio.Queue()
        self._worker: asyncio.Task | None = None
        # 문서 바꾸는 중: 옛 문서 복원과 새 문서 commit 사이에 생긴 변경은 곧 버려진다 → Google에 쓰지 않는다
        self.hold = False

    def start(self) -> None:
        # 이전 이벤트 루프에 묶인 워커(테스트에서 서버를 다시 띄울 때)는 버리고 새 루프에서 다시 만든다
        if self._worker is not None and self._worker.get_loop() is not asyncio.get_running_loop():
            self._worker, self.queue = None, asyncio.Queue()
        if self._worker is None:
            self._worker = asyncio.create_task(self._run())

    def enqueue(self, room: "Room", event_type: str, change: dict[str, Any]) -> None:
        if self.hold:
            return
        self.queue.put_nowait((room, event_type, change))

    async def run_exclusive(self, fn: Any, room: "Room | None" = None) -> Any:
        """fn()을 Outbox 줄 순서대로 워커 스레드에서 실행하고 결과를 돌려준다 (예외도 그대로).
        앞에 선 동기화가 다 끝난 뒤 돌기 때문에 Google 호출이 겹치지 않는다."""
        fut: asyncio.Future = asyncio.get_running_loop().create_future()
        self.queue.put_nowait((room, CALL, {"fn": fn, "fut": fut}))  # type: ignore[arg-type]
        return await fut

    def enqueue_full_sync(self, room: "Room") -> None:
        """방 상태 전체를 외부 문서에 미러링. 같은 워커 줄에 서므로 동시 호출이 생기지 않는다.
        첫 호출이 Google 연결 준비(서비스 생성·탭 조회)도 겸해서 첫 발화 동기화가 빨라진다."""
        self.queue.put_nowait((room, FULL_SYNC, {}))

    def enqueue_restore(self, room: "Room", changes: list[dict[str, Any]]) -> None:
        """원본 모드 리셋: 회의 중 적용된 change를 역순으로 되돌리고 정리한다 (전부 같은 워커 줄).

        room은 리셋된(같은) 방 객체. 원본 모드 push는 room.state를 읽지 않고 change의 diff만 쓰므로 새 회의 상태여도 된다.
        sync 이벤트는 새 회의 로그에 남으니 옛 회의 utt_id는 지운다 (새 회의도 u1부터라 지연 집계에 섞이지 않게).
        """
        for ch in reversed(changes):
            self.queue.put_nowait((room, "change.reverted", {**ch, "utt_id": None}))
        self.queue.put_nowait((room, RESTORE, {}))

    async def _run(self) -> None:
        while True:
            room, event_type, change = await self.queue.get()
            if event_type == CALL:
                fut = change["fut"]
                try:
                    res = await asyncio.to_thread(change["fn"])
                    if not fut.done():
                        fut.set_result(res)
                except Exception as e:
                    if not fut.done():
                        fut.set_exception(e)
                self.queue.task_done()
                continue
            if event_type == RESTORE:
                from server.sync import google_source
                await self._push(room, "google_restore", google_source, RESTORE, change)
                self.queue.task_done()
                continue
            if event_type == FULL_SYNC:
                mods = [TARGETS[t] for t in sorted(TARGETS)]
            else:
                targets = {OPS[o["op"]].google for o in change["ops"] if o["op"] in OPS} - {None}
                mods = [TARGETS[t] for t in sorted(targets)]  # type: ignore[index]
            for name, mod in mods:
                if not mod.enabled() or (event_type == FULL_SYNC and not hasattr(mod, "push_all")):
                    continue
                await self._push(room, name, mod, event_type, change)
            self.queue.task_done()

    async def _push(self, room: "Room", name: str, mod: Any, event_type: str, change: dict[str, Any]) -> None:
        refs = {"change_id": change.get("change_id"), "utt_id": change.get("utt_id")}
        for attempt in range(1, MAX_RETRIES + 1):
            t0 = time.perf_counter()
            try:
                # 블로킹 Google 클라이언트를 쓰더라도 워커가 하나라 동시 호출은 생기지 않는다
                if event_type == RESTORE:
                    await asyncio.to_thread(mod.cleanup)
                elif event_type == FULL_SYNC:
                    await asyncio.to_thread(mod.push_all, room.state)
                else:
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
