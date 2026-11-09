"""Editor: 발화 → ops (tool_use). 기본 sonnet. 툴 스키마는 server/ops/registry.py에서 생성."""
from __future__ import annotations

import re
from typing import Any

from server.agent import llm
from server.agent.prompts import EDITOR_SYSTEM
from server.model.docs import DocState
from server.ops.registry import tool_schemas


async def edit(text: str, speaker: str, state: DocState, transcript: list[dict[str, str]],
               label: str) -> list[dict[str, Any]]:
    if not llm.is_live():
        return _mock_edit(text, speaker, label)

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
            f"LATEST ({label}) — {speaker}: {text}"
        )}],
    )
    return [{"op": b.name, **b.input} for b in resp.content if b.type == "tool_use"]


def _mock_edit(text: str, speaker: str, label: str) -> list[dict[str, Any]]:
    """LLM 없이 화면·엔진을 돌려 보기 위한 최소 규칙."""
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
