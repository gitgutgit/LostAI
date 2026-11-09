"""Editor: 발화 → ops (tool_use). 기본 sonnet. 툴 스키마는 server/ops/registry.py에서 생성."""
from __future__ import annotations

import re
from typing import Any

from server.agent import llm
from server.agent.prompts import EDITOR_SYSTEM
from server.agent.vote_trigger import is_choice_question, is_vote_call
from server.model.docs import DocState
from server.ops.registry import tool_schemas


async def edit(text: str, speaker: str, state: DocState, transcript: list[dict[str, str]],
               label: str, vote_call: bool = False) -> list[dict[str, Any]]:
    if not llm.is_live():
        return _mock_edit(text, speaker, label, transcript)

    # 표결 부르기 표시는 상태와 같은 사용자 메시지에 붙인다(시스템 프롬프트는 캐시 때문에 고정).
    tag = f"{label}, vote call" if vote_call else label

    # 상태는 발화마다 바뀌므로 캐시 대상이 아니다. 고정된 tools + system 까지만 캐시된다.
    resp = await llm.client().messages.create(
        model=llm.EDITOR_MODEL,
        max_tokens=4096,
        system=[{"type": "text", "text": EDITOR_SYSTEM, "cache_control": {"type": "ephemeral"}}],
        tools=tool_schemas(),
        tool_choice={"type": "auto"},  # forced tool_choice는 sonnet-5-5에서 400
        messages=[{"role": "user", "content": (
            f"Doc state:\n{llm.state_summary(state)}\n\n"
            f"Recent transcript:\n{llm.transcript_text(transcript)}\n\n"
            f"LATEST ({tag}) — {speaker}: {text}"
        )}],
    )
    return [{"op": b.name, **b.input} for b in resp.content if b.type == "tool_use"]


def _mock_edit(text: str, speaker: str, label: str, transcript: list[dict[str, str]] | None = None) -> list[dict[str, Any]]:
    """LLM 없이 화면·엔진을 돌려 보기 위한 최소 규칙."""
    if is_vote_call(text) or is_choice_question(text):
        # ep: 고르기 질문 → 질문 카드. 선택지는 최근 대화의 티켓 번호 두 개, 없으면 찬성/반대.
        recent = [l["text"] for l in (transcript or [])[-6:]] + [text]
        ids = list(dict.fromkeys(re.findall(r"[A-Z]{2,}-\d+", " ".join(recent))))[-2:]
        topic = next((t for t in reversed(recent) if "?" in t), text)[:80]
        opts = ids if len(ids) == 2 else ["찬성", "반대"]
        return [{"op": "open_conflict", "topic": topic, "positions": [{"who": speaker, "says": o} for o in opts]}]
    if re.search(r"(취소|undo|되돌)", text, re.IGNORECASE):
        return [{"op": "undo_last"}]
    if re.search(r"(결정|decid)", text, re.IGNORECASE):
        return [{"op": "add_decision", "text": text}]
    if re.search(r"(담당|action|할게|will do)", text, re.IGNORECASE):
        return [{"op": "add_action", "text": text, "owner": speaker}]
    if re.search(r"(리스크|위험|risk)", text, re.IGNORECASE):
        return [{"op": "insert_item", "doc": "notes", "section": "s_risk", "text": text}]
    if label == "edit" and re.search(r"(티켓|ticket|추가|add)", text, re.IGNORECASE):
        return [{"op": "add_row", "doc": "board", "values": {"제목": text[:40], "담당": speaker, "상태": "이번 스프린트"}}]
    if label in ("capture", "edit"):
        return [{"op": "add_note", "text": text}]
    return []
