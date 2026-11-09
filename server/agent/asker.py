"""Asker: 질문에 한 문장으로 답하고 근거 utt_id를 붙인다. 문서는 건드리지 않는다."""
from __future__ import annotations

from server.agent import llm
from server.agent.prompts import ASKER_SYSTEM
from server.model.docs import DocState


async def ask(text: str, state: DocState, transcript: list[dict[str, str]]) -> tuple[str, list[str]]:
    if not llm.is_live():
        return f"(MOCK) '{text}'에 대한 답변 자리", [l["utt_id"] for l in transcript[-1:]]

    resp = await llm.client().messages.create(
        model=llm.EDITOR_MODEL,
        max_tokens=1024,
        system=[{"type": "text", "text": ASKER_SYSTEM, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": (
            f"Doc state:\n{llm.state_summary(state)}\n\nTranscript:\n{llm.transcript_text(transcript)}\n\nQuestion: {text}"
        )}],
    )
    out = "".join(b.text for b in resp.content if b.type == "text").strip()
    answer, _, ev = out.partition("EVIDENCE:")
    return answer.strip(), [x.strip() for x in ev.split(",") if x.strip()]
