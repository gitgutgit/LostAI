"""Router: 발화 → ignore / capture / edit / command / ask. 기본 haiku."""
from __future__ import annotations

import re

from server.agent import llm
from server.agent.prompts import ROUTE_TOOL, ROUTER_SYSTEM
from server.agent.vote_trigger import CHOICE_QUESTION, VOTE_CALL
from server.events import RouteLabel

_MOCK_RULES: list[tuple[str, RouteLabel]] = [
    (r"(취소|undo|되돌|cancel|pause|멈춰|resume)", "command"),
    (VOTE_CALL.pattern, "capture"),        # ep: 표결 부르기와 고르기 질문은 질문 카드로
    (CHOICE_QUESTION.pattern, "capture"),
    (r"(\?|뭐였|누구|언제|what|who|when|how many)", "ask"),
    (r"(바꿔|넣어|빼|추가|지워|해줘|해주세요|적용|set|add|remove|change|move|update|delete|please)", "edit"),  # hs: 해줘/적용/please 추가
    (r"(결정|하기로|리스크|위험|담당|decide|decided|risk|action|will do|owner)", "capture"),
]


async def route(text: str, transcript: list[dict[str, str]]) -> RouteLabel:
    if not llm.is_live():
        for pattern, label in _MOCK_RULES:
            if re.search(pattern, text, re.IGNORECASE):
                return label
        return "ignore"

    resp = await llm.client().messages.create(
        model=llm.ROUTER_MODEL,
        max_tokens=256,
        system=[{"type": "text", "text": ROUTER_SYSTEM, "cache_control": {"type": "ephemeral"}}],
        tools=[ROUTE_TOOL],
        tool_choice={"type": "auto"},
        messages=[{"role": "user", "content": f"Recent transcript:\n{llm.transcript_text(transcript[-6:])}\n\nLATEST: {text}"}],
    )
    for block in resp.content:
        if block.type == "tool_use" and block.name == "route":
            return block.input.get("label", "ignore")
    return "ignore"
