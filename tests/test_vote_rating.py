"""표결 값 3 = 좋음, 2 = 보통, 1 = 싫음. author: gitgutgit"""
import asyncio

import pytest

from server.agent.pipeline import vote_value
from server.gestures.votes import Votes


@pytest.mark.parametrize("text,want", [
    ("3", 3), ("2번", 2), ("1표", 1), ("Jiwon: 좋아요", 3), ("찬성", 3), ("보통", 2), ("보통이에요", 2),
    ("싫어요", 1), ("반대", 1), ("ok", 2), ("no", 1),
    ("4", None), ("5번", None), ("좋아요 근데 일정은요", None), ("오늘 점심 뭐 먹지", None),
])
def test_vote_value(text, want):
    assert vote_value(text) == want


class FakeRoom:
    def __init__(self):
        self.events = []

    async def emit(self, type_, actor, refs, payload):
        self.events.append((type_, actor, refs, payload))


def test_fingers_outside_1_to_3_are_not_votes():
    async def run():
        room, v = FakeRoom(), Votes()
        await v.on_fingers(room, "a", 5)
        await v.on_fingers(room, "b", 0)
        await v.on_fingers(room, "c", 4)
        assert room.events == [] and v.vote_id is None  # 표결이 열리지도 않는다
        await v.on_fingers(room, "a", 3)
        await v.on_fingers(room, "b", 1)
        assert [e[0] for e in room.events] == ["vote.opened", "vote.cast", "vote.cast"]
        await v.cast_by_voice(room, "c", 4)  # 4는 무시
        assert v.cast == {"a": 3, "b": 1}
        v.reset()
    asyncio.run(run())
