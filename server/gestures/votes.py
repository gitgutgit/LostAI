"""손가락 표결 집계 (P2). 확인된 참석자 2명 이상이 2초 안에 손가락을 보이면 표결 시작, 5초 조용하면 마감.
gitgutgit: 표결은 두 가지. 질문 카드의 선택지가 찬성/반대뿐(또는 주장 하나 + 반대)이면 '찬반 카드' → 3 = 좋음, 2 = 보통, 1 = 싫음.
실제 선택지가 2~4개면 '선택지 카드' → 번호 1~N 고르기. 범위 밖의 손가락 수와 번호는 표로 세지 않는다.
화면(web/src/views/wall/live.ts)도 같은 규칙(is_rating_card)으로 카드 종류를 정한다.
ep: 말로 여는 표결(open_by_voice)과 말로 하는 한 표(cast_by_voice)를 더했다. 말로 연 표결은 아무도 안 내면 20초 뒤 마감."""
from __future__ import annotations

import asyncio
import re
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from server.room import Room

OPEN_WINDOW_SEC = 4.0   # gitgutgit 11-09: 2초 → 4초 (표결 시간 2배)
QUIET_CLOSE_SEC = 10.0  # 5초 → 10초
VOICE_OPEN_SEC = 40.0  # ep: 말로 연 표결의 첫 마감 시한
RATINGS = {3: "좋음", 2: "보통", 1: "싫음"}  # gitgutgit: 찬반 카드의 손가락 수 → 뜻
_AGAINST = {"반대", "no"}
# 찬반 카드에서 말 한마디로 한 표. 영어 회의(기본)와 한국어 회의 둘 다. 문장 전체가 이 말일 때만 센다.
_GOOD = r"좋아요?|좋음|좋습니다|찬성|good|yes|yeah|yep|agree|i agree|sounds good|for it|thumbs up"
_OKAY = r"보통(이에요|이요)?|그저 그래요?|괜찮아요|okay|ok|fine|neutral|so-so|so so|meh|maybe"
_NO = r"싫어요?|싫음|별로(예요|에요)?|반대|no|nope|bad|disagree|i disagree|against( it)?|thumbs down"
_RATING_WORDS = re.compile(rf"^\s*(?:[^:\s][^:]{{0,11}}:\s*)?(?:i say |i'?m |i vote |it'?s |that'?s )?({_GOOD}|{_OKAY}|{_NO})\s*[.!]?\s*$", re.IGNORECASE)


def is_rating_card(positions: list[dict[str, str]]) -> bool:
    """선택지가 1개 이하이거나 '반대'/'No'가 들어 있으면 찬반 카드(3·2·1)."""
    return len(positions) < 2 or any(str(p.get("says", "")).strip().lower() in _AGAINST for p in positions)


class Votes:
    def __init__(self) -> None:
        self.pending: dict[str, tuple[int, float]] = {}
        self.vote_id: str | None = None
        self.cast: dict[str, int] = {}
        self._closer: asyncio.Task | None = None
        self.mode = "rating"          # "rating"(3·2·1) | "options"(1~N)
        self.max_option = 3

    def _set_mode(self, room: "Room", question: str | None) -> str | None:
        """표결할 질문 카드를 찾아 종류를 정한다. 질문을 안 주면 가장 최근 열린 질문(화면과 같은 기준)."""
        conflicts = [c for c in room.state.conflicts if not c.resolved] if getattr(room, "state", None) else []
        card = next((c for c in conflicts if c.topic == question), None) if question else (conflicts[0] if conflicts else None)
        positions = card.positions if card else []
        self.mode = "rating" if is_rating_card(positions) else "options"
        self.max_option = 3 if self.mode == "rating" else min(len(positions), 4)
        return card.topic if card else question

    def valid(self, n: int) -> bool:
        return 1 <= n <= self.max_option

    def rating_word(self, text: str) -> int | None:
        """찬반 카드 표결 중 '좋아요/보통/싫어요' 한마디 → 3/2/1. 선택지 카드면 None."""
        if self.vote_id is None or self.mode != "rating" or not (m := _RATING_WORDS.match(text)):
            return None
        w = m.group(1).lower()
        if re.fullmatch(_GOOD, w, re.IGNORECASE):
            return 3
        if re.fullmatch(_OKAY, w, re.IGNORECASE):
            return 2
        return 1

    def reset(self) -> None:
        if self._closer:
            self._closer.cancel()
        self.__init__()

    async def on_fingers(self, room: "Room", who: str, n: int) -> None:
        if not 1 <= n <= 4:  # 주먹(0), 5는 어느 표결에서도 표가 아니다
            return
        now = time.monotonic()
        if self.vote_id is None:
            self.pending[who] = (n, now)
            self.pending = {k: v for k, v in self.pending.items() if now - v[1] < OPEN_WINDOW_SEC}
            if len(self.pending) < 2:
                return
            self.vote_id = f"v{len(room.events) + 1}"
            # TODO(P2): 직전 대사로 질문을 LLM이 비동기로 만든다. 지금은 가장 최근 열린 질문(없으면 None).
            question = self._set_mode(room, None)
            await room.emit("vote.opened", "server", {"vote_id": self.vote_id}, {"question": question, "closes_in": QUIET_CLOSE_SEC})
            for k, (m, _) in self.pending.items():
                if self.valid(m):
                    await self._cast(room, k, m)
            self.pending.clear()
            if not self.cast:  # 연 손이 모두 이 카드에서 안 세는 수였으면, 열린 채 남지 않게 마감 시계를 건다
                self._closer = asyncio.create_task(self._close_later(room))
        else:
            await self._cast(room, who, n)

    async def open_by_voice(self, room: "Room", by: str, question: str | None) -> bool:
        """ep: 표결을 말로 연다. 이미 열려 있으면 아무것도 하지 않는다."""
        if self.vote_id is not None:
            return False
        self.vote_id = f"v{len(room.events) + 1}"
        self._set_mode(room, question)
        await room.emit("vote.opened", by, {"vote_id": self.vote_id}, {"question": question, "closes_in": VOICE_OPEN_SEC})
        self._closer = asyncio.create_task(self._close_later(room, VOICE_OPEN_SEC))
        return True

    async def cast_by_voice(self, room: "Room", who: str, n: int) -> None:
        """ep: 열린 표결에 말로 한 표('2번', '좋아요')."""
        if self.vote_id is not None and self.valid(n):
            await self._cast(room, who, n)

    async def _cast(self, room: "Room", who: str, n: int) -> None:
        if not self.valid(n):
            return
        self.cast[who] = n
        # closes_in: 이 표로 마감 시계가 다시 시작된다 → 화면이 남은 초를 숫자로 보인다
        await room.emit("vote.cast", who, {"vote_id": self.vote_id}, {"value": n, "closes_in": QUIET_CLOSE_SEC})
        if self._closer:
            self._closer.cancel()
        self._closer = asyncio.create_task(self._close_later(room))

    async def _close_later(self, room: "Room", wait: float = QUIET_CLOSE_SEC) -> None:
        await asyncio.sleep(wait)
        await room.emit("vote.closed", "server", {"vote_id": self.vote_id},
                        {"votes": self.cast, "counted": len(self.cast)})
        self.vote_id, self.cast = None, {}


votes = Votes()
