"""표결 발동 조건(server/agent/vote_trigger.py)과 한 회의 두 번 표결. MOCK, LLM 없이 돈다."""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("AGENT_MODE", "MOCK")

from server.agent.vote_trigger import (is_bare_vote_call, is_choice_question, is_vote_call,  # noqa: E402
                                       normalize_vote_ops, question_from_ops, vote_pick,
                                       vote_pick_loose)


@pytest.mark.parametrize("text", [
    "투표하죠.", "투표하죠", "자, 투표합시다!", "그럼 투표로 정하죠", "Eric: 투표하죠.", "그거 투표로 정합시다",
    "손 들어 봅시다", "다수결로 가죠", "표결에 부치죠", "Let's vote.", "OK let's vote on it", "Show of hands, please.",
])
def test_bare_vote_call(text):
    assert is_vote_call(text) and is_bare_vote_call(text)


@pytest.mark.parametrize("text", [
    "광고 페이지 우선순위로 투표 한 번 하죠.",          # 2026-11-09 LIVE 실사용: 주제가 붙은 부르기
    "화요일이랑 목요일 중에 투표하죠",
    "로그 정리랑 결제 재시도 중에 뭘 먼저 할지 투표하죠.",
    "Let's vote on dark mode or CSV export.",
    "이걸로 갈지 투표하죠",
])
def test_vote_call_with_subject_is_not_bare(text):
    assert is_vote_call(text) and not is_bare_vote_call(text)


@pytest.mark.parametrize("text", [
    "투표하지 말죠", "투표는 나중에 하죠", "Let's not vote", "투표 마감하죠", "Let's cancel the vote", "투표 그만해요",
    "손 들어서 말해 주세요", "the votes are in", "아까 투표 결과 뭐였지?", "We already voted on that.",
])
def test_talking_about_a_vote_is_not_a_call(text):
    assert not is_vote_call(text)


@pytest.mark.parametrize("text", ["아까 그거 투표하죠", "A 말고 B로 할지 투표하죠", "Yes or no, let's vote."])
def test_vote_call_with_common_words(text):
    assert is_vote_call(text)


@pytest.mark.parametrize("text,n", [
    ("2번에 투표할게요", 2), ("저는 3번이요", 3), ("I vote 2", 2), ("I'll go with option three", 3),
    ("1번이랑 2번 다 좋아요", None), ("PAY-423번 티켓", None), ("2번 투표하지 말죠", None), ("2번 뭐였죠?", None),
])
def test_loose_pick_while_a_vote_is_open(text, n):
    assert vote_pick_loose(text) == n


@pytest.mark.parametrize("text,n", [("No one.", None), ("no one", None), ("No. 2", 2), ("#3", 3),
    ("1번", 1), ("2번이요.", 2), ("Ines: 2번", 2), ("3", 3), ("option two", 2), ("Two.", 2), ("이번", None),
    ("2번 티켓 담당이 누구죠?", None), ("5번", None),
])
def test_vote_pick(text, n):
    assert vote_pick(text) == n


@pytest.mark.parametrize("text,want", [
    ("PAY-423이랑 AUTH-118 두 티켓 중에 뭐가 더 중요할까요?", True),
    ("Should we ship dark mode or CSV export first?", True),
    ("PAY-423 담당이 누구였지?", False),
    ("점심 뭐 먹지", False),
])
def test_choice_question(text, want):
    assert is_choice_question(text) is want


def test_normalize_fills_missing_options_and_maps_poc_keys():
    # 2026-11-09 LIVE 실사용: 선택지 0개 카드
    ops = normalize_vote_ops([{"op": "open_conflict", "topic": "광고 페이지 우선순위를 어떻게 정할까?", "positions": []}],
                             "Eric", "광고 페이지 우선순위로 투표 한 번 하죠.")
    assert [p["says"] for p in ops[0]["positions"]] == ["찬성", "반대"]
    ops = normalize_vote_ops([{"op": "open_conflict", "topic": "Ship it Friday?"}], "Owen", "let's vote on it")
    assert [p["says"] for p in ops[0]["positions"]] == ["Yes", "No"]
    ops = normalize_vote_ops([{"op": "open_conflict", "topic": "A or B?",
                               "positions": [{"speaker": "Ines", "claim": "A"}, {"speaker": "Owen", "claim": "B"}]}],
                             "Eric", "A or B?")
    assert ops[0]["positions"] == [{"who": "Ines", "says": "A"}, {"who": "Owen", "says": "B"}]
    five = [{"who": "x", "says": str(i)} for i in range(5)]
    assert len(normalize_vote_ops([{"op": "open_conflict", "topic": "t", "positions": five}], "x", "t")[0]["positions"]) == 4
    one = normalize_vote_ops([{"op": "open_conflict", "topic": "누가 맡나?", "positions": [{"who": "Ravi", "says": "Ravi가 맡음"}]}],
                             "Ines", "제가 할게요")
    assert one[0]["positions"] == [{"who": "Ravi", "says": "Ravi가 맡음"}, {"who": "Ines", "says": "반대"}]
    other = [{"op": "add_note", "text": "n"}]
    assert normalize_vote_ops(other, "x", "t") == other
    assert question_from_ops([{"op": "add_note"}, {"op": "open_conflict", "topic": "Q"}]) == "Q"


def test_second_vote_opens_on_the_new_question():
    """2026-11-09 LIVE 실측: 한 회의의 두 번째 '투표하죠'가 옛 질문으로 열렸다."""
    from fastapi.testclient import TestClient

    from server import app as app_mod
    from server import room as room_mod

    from tests.test_one_person import _wait

    try:
        with TestClient(app_mod.app) as c:
            c.post("/api/reset")
            tok = {n: c.post("/api/join/manual", json={"name": n, "host": "Eric"}).json()["token"] for n in ("Eric", "Ines")}
            ws = {n: c.websocket_connect(f"/ws?token={t}").__enter__() for n, t in tok.items()}
            for s in ws.values():
                s.receive_json()

            def say(who, text, pred, sec=8.0):
                ws[who].send_json({"kind": "utterance.final", "payload": {"text": text}})
                return _wait(c, pred, sec)

            opened = lambda k: (lambda ev: sum(e["type"] == "vote.opened" for e in ev) >= k)
            say("Eric", "PAY-423이랑 AUTH-118 두 티켓 중에 뭐가 더 중요할까요?",
                lambda ev: any(e["type"] == "change.applied" for e in ev))
            say("Eric", "투표하죠.", opened(1))
            say("Ines", "1번", lambda ev: any(e["type"] == "vote.cast" for e in ev))
            say("Ines", "그냥", lambda ev: True)  # 아무 말
            # 마감은 표가 들어와도 줄지 않는다(말로 연 표결 40초) → 입장한 두 명이 다 내서 바로 마감시킨다
            say("Eric", "2번", lambda ev: sum(e["type"] == "vote.cast" for e in ev) >= 2)
            from server.gestures.votes import ALL_IN_CLOSE_SEC
            ev = _wait(c, lambda ev: any(e["type"] == "vote.closed" for e in ev), sec=ALL_IN_CLOSE_SEC + 5)
            say("Eric", "회고는 화요일이랑 목요일 중에 어느 쪽이 좋을까요?",
                lambda ev: sum(e["type"] == "change.applied" for e in ev) >= 2)
            ev = say("Eric", "투표하죠.", opened(2))
            qs = [e["payload"]["question"] for e in ev if e["type"] == "vote.opened"]
            for s in ws.values():
                s.__exit__(None, None, None)
    finally:
        room_mod.rooms.pop("main", None)
    assert len(qs) == 2 and qs[0] != qs[1] and "화요일" in qs[1]


def test_vote_deadline_never_shrinks_and_closes_when_all_in():
    """gitgutgit 11-09: 말로 연 40초 표결이 첫 표에 10초로 줄던 문제. 마감은 늦출 수만 있고, 입장한 사람이 모두 내면 바로 마감."""
    import asyncio

    from server.gestures.votes import ALL_IN_CLOSE_SEC, VOICE_OPEN_SEC, Votes

    class FakeRoom:
        def __init__(self):
            self.events, self.participants, self.state = [], {"Jiwon": {}, "Mina": {}}, None

        async def emit(self, type_, actor, refs=None, payload=None):
            self.events.append({"type": type_, "actor": actor, "payload": payload or {}})

    async def run():
        room, v = FakeRoom(), Votes()
        await v.open_by_voice(room, "Jiwon", None)
        await v.cast_by_voice(room, "Haeun", 2)  # 대본 화자(입장 안 함)의 표: 마감이 줄면 안 된다
        assert room.events[-1]["payload"]["closes_in"] > VOICE_OPEN_SEC - 1
        await v.cast_by_voice(room, "Jiwon", 3)
        assert room.events[-1]["payload"]["closes_in"] > VOICE_OPEN_SEC - 1  # 아직 Mina가 안 냄
        await v.cast_by_voice(room, "Mina", 1)  # 입장한 사람 모두 냄 → 곧 마감
        assert room.events[-1]["payload"]["closes_in"] <= ALL_IN_CLOSE_SEC
        await asyncio.sleep(ALL_IN_CLOSE_SEC + 0.3)
        assert room.events[-1]["type"] == "vote.closed"
        assert room.events[-1]["payload"]["votes"] == {"Haeun": 2, "Jiwon": 3, "Mina": 1}

    asyncio.run(run())


def test_leave_removes_participant_and_reconnect_rejoins():
    """gitgutgit 11-09: 회의 나가기(마지막 탭 닫힘) → 참석자에서 빠짐. 재배포 뒤 토큰으로 다시 붙으면 되살아남."""
    import json

    from server.room import Room

    class FakeWS:
        async def send_text(self, data):
            pass

    async def run():
        room = Room("leave-test")
        a, b = FakeWS(), FakeWS()
        assert await room.connect(a, "Jiwon")          # 목록에 없던 이름 → 되살림
        assert not await room.connect(b, "Jiwon")      # 같은 사람 두 번째 탭
        assert not room.disconnect(a)                  # 탭 하나 남음 → 아직 참석
        assert "Jiwon" in room.participants
        assert room.disconnect(b)                      # 마지막 탭 → 나감
        assert "Jiwon" not in room.participants

    import asyncio
    asyncio.run(run())
