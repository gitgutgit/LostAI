"""표결 두 가지 (author: gitgutgit)
- 찬반 카드(선택지가 찬성/반대뿐, 주장 하나 + 반대, 또는 카드 없음): 3 = 좋음, 2 = 보통, 1 = 싫음.
- 선택지 카드(실제 선택지 2~4개): 번호 1~N 고르기 (PR #38 방식 그대로).
"""
import asyncio
from types import SimpleNamespace

import pytest

from server.gestures.votes import Votes, is_rating_card
from server.model.docs import Conflict


@pytest.mark.parametrize("positions,want", [
    ([], True),
    ([{"who": "a", "says": "찬성"}, {"who": "a", "says": "반대"}], True),
    ([{"who": "a", "says": "Yes"}, {"who": "a", "says": "No"}], True),
    ([{"who": "a", "says": "웹훅은 준호가"}, {"who": "b", "says": "반대"}], True),
    ([{"who": "a", "says": "병행"}, {"who": "b", "says": "순차"}], False),
    ([{"who": "a", "says": "화"}, {"who": "b", "says": "수"}, {"who": "c", "says": "목"}], False),
])
def test_is_rating_card(positions, want):
    assert is_rating_card(positions) is want


class FakeRoom:
    def __init__(self, conflicts=()):
        self.events = []
        self.state = SimpleNamespace(conflicts=list(conflicts))

    async def emit(self, type_, actor, refs, payload):
        self.events.append((type_, actor, refs, payload))


YES_NO = Conflict(conflict_id="c1", topic="성능 테스트는 통합 테스트 뒤", positions=[{"who": "지원", "says": "찬성"}, {"who": "지원", "says": "반대"}])
THREE = Conflict(conflict_id="c2", topic="회의 요일", positions=[{"who": "a", "says": "화"}, {"who": "b", "says": "수"}, {"who": "c", "says": "목"}])


def run(coro):
    asyncio.run(coro)


def test_rating_card_counts_1_to_3_and_words():
    async def go():
        room, v = FakeRoom([YES_NO]), Votes()
        assert await v.open_by_voice(room, "지원", YES_NO.topic)
        assert v.mode == "rating"
        await v.cast_by_voice(room, "a", 4)          # 찬반 카드에서 4는 안 셈
        assert v.rating_word("좋아요") == 3 and v.rating_word("보통") == 2 and v.rating_word("하은: 싫어요") == 1
        assert v.rating_word("좋아요 근데 일정은요") is None
        # 영어 회의(기본 언어)
        for said, want in [("Good.", 3), ("Yes", 3), ("I agree", 3), ("Mina: sounds good", 3), ("Okay", 2), ("fine", 2),
                           ("neutral", 2), ("No.", 1), ("nope", 1), ("I disagree", 1), ("against it", 1)]:
            assert v.rating_word(said) == want, said
        assert v.rating_word("Good point, but what about the date?") is None
        await v.cast_by_voice(room, "a", v.rating_word("좋아요"))
        await v.on_fingers(room, "b", 1)
        assert v.cast == {"a": 3, "b": 1}
        v.reset()
    run(go())


def test_option_card_counts_1_to_n_and_ignores_rating_words():
    async def go():
        room, v = FakeRoom([THREE]), Votes()
        assert await v.open_by_voice(room, "지원", THREE.topic)
        assert v.mode == "options" and v.max_option == 3
        assert v.rating_word("좋아요") is None       # 선택지 카드에서는 말 표가 아니다
        await v.cast_by_voice(room, "a", 3)
        await v.cast_by_voice(room, "b", 4)          # 선택지는 3개뿐
        assert v.cast == {"a": 3}
        v.reset()
    run(go())


def test_fingers_0_and_5_never_open_a_vote():
    async def go():
        room, v = FakeRoom(), Votes()
        await v.on_fingers(room, "a", 5)
        await v.on_fingers(room, "b", 0)
        assert room.events == [] and v.vote_id is None
        await v.on_fingers(room, "a", 3)
        await v.on_fingers(room, "b", 1)
        assert [e[0] for e in room.events] == ["vote.opened", "vote.cast", "vote.cast"]
        v.reset()
    run(go())
