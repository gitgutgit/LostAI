"""LLM 워밍업: MOCK이면 아무것도 안 하고, LIVE면 라우터·에디터를 부르되 상태를 안 바꾼다. author: Mal-Mi-Jal"""
import asyncio

from server.common import warmup
from server.model.docs import load_seed


def test_mock_is_noop():
    assert asyncio.run(warmup.warm_llm(load_seed("sprint"))) is None


def test_live_calls_both_and_keeps_state(monkeypatch):
    from server.agent import editor, llm, router
    calls = []

    async def fake_route(text, transcript):
        calls.append("route")
        return "ignore"

    async def fake_edit(text, speaker, state, transcript, label):
        calls.append("edit")
        state.docs["board"].rows.clear()  # 복사본이어야 원본이 안 바뀐다
        return []

    monkeypatch.setattr(llm, "is_live", lambda: True)
    monkeypatch.setattr(router, "route", fake_route)
    monkeypatch.setattr(editor, "edit", fake_edit)
    s = load_seed("sprint")
    before = s.model_dump()
    res = asyncio.run(warmup.warm_llm(s))
    assert sorted(calls) == ["edit", "route"] and set(res) == {"route", "edit"}
    assert s.model_dump() == before


def test_live_failure_does_not_raise(monkeypatch):
    from server.agent import llm, router

    async def boom(text, transcript):
        raise RuntimeError("no key")

    monkeypatch.setattr(llm, "is_live", lambda: True)
    monkeypatch.setattr(router, "route", boom)
    assert asyncio.run(warmup.warm_llm(load_seed("sprint"))) is None
