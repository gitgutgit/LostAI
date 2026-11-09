"""손가락 표결 집계 (P2). 확인된 참석자 2명 이상이 2초 안에 손가락을 보이면 표결 시작, 5초 조용하면 마감.
gitgutgit: 값은 3 = 좋음, 2 = 보통, 1 = 싫음. 그 밖의 손가락 수(0, 4, 5)는 표로 세지 않는다.
ep: 말로 여는 표결(open_by_voice)과 말로 하는 한 표(cast_by_voice)를 더했다. 말로 연 표결은 아무도 안 내면 20초 뒤 마감."""
from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from server.room import Room

OPEN_WINDOW_SEC = 2.0
QUIET_CLOSE_SEC = 5.0
VOICE_OPEN_SEC = 20.0  # ep: 말로 연 표결의 첫 마감 시한
RATINGS = {3: "좋음", 2: "보통", 1: "싫음"}  # gitgutgit: 손가락 수 → 뜻


class Votes:
    def __init__(self) -> None:
        self.pending: dict[str, tuple[int, float]] = {}
        self.vote_id: str | None = None
        self.cast: dict[str, int] = {}
        self._closer: asyncio.Task | None = None

    def reset(self) -> None:
        if self._closer:
            self._closer.cancel()
        self.__init__()

    async def on_fingers(self, room: "Room", who: str, n: int) -> None:
        if n not in RATINGS:  # 주먹(0), 4, 5는 표가 아니다
            return
        now = time.monotonic()
        if self.vote_id is None:
            self.pending[who] = (n, now)
            self.pending = {k: v for k, v in self.pending.items() if now - v[1] < OPEN_WINDOW_SEC}
            if len(self.pending) < 2:
                return
            self.vote_id = f"v{len(room.events) + 1}"
            # TODO(P2): 직전 대사로 질문을 LLM이 비동기로 만든다
            await room.emit("vote.opened", "server", {"vote_id": self.vote_id}, {"question": None})
            for k, (m, _) in self.pending.items():
                await self._cast(room, k, m)
            self.pending.clear()
        else:
            await self._cast(room, who, n)

    async def open_by_voice(self, room: "Room", by: str, question: str | None) -> bool:
        """ep: 표결을 말로 연다. 이미 열려 있으면 아무것도 하지 않는다."""
        if self.vote_id is not None:
            return False
        self.vote_id = f"v{len(room.events) + 1}"
        await room.emit("vote.opened", by, {"vote_id": self.vote_id}, {"question": question})
        self._closer = asyncio.create_task(self._close_later(room, VOICE_OPEN_SEC))
        return True

    async def cast_by_voice(self, room: "Room", who: str, n: int) -> None:
        """ep: 열린 표결에 말로 한 표('2번', '좋아요')."""
        if self.vote_id is not None and n in RATINGS:
            await self._cast(room, who, n)

    async def _cast(self, room: "Room", who: str, n: int) -> None:
        self.cast[who] = n
        await room.emit("vote.cast", who, {"vote_id": self.vote_id}, {"value": n})
        if self._closer:
            self._closer.cancel()
        self._closer = asyncio.create_task(self._close_later(room))

    async def _close_later(self, room: "Room", wait: float = QUIET_CLOSE_SEC) -> None:
        await asyncio.sleep(wait)
        await room.emit("vote.closed", "server", {"vote_id": self.vote_id},
                        {"votes": self.cast, "counted": len(self.cast)})
        self.vote_id, self.cast = None, {}


votes = Votes()
