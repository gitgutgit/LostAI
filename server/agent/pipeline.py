"""발화 하나 → Router → Editor 또는 Asker → Op 엔진 (docs/ARCHITECTURE.md 5-1).

TODO(P1): 라우터와 에디터 동시 시작, interim 텍스트로 미리 라우팅 (6절).
"""
from __future__ import annotations

import time
from typing import TYPE_CHECKING

from server.agent.asker import ask
from server.agent.editor import edit
from server.agent.router import route
from server.events import Event

if TYPE_CHECKING:
    from server.room import Room


def _ms(t0: float) -> int:
    return int((time.perf_counter() - t0) * 1000)


async def handle_utterance(room: "Room", ev: Event) -> None:
    utt_id, speaker, text = ev.refs.utt_id, ev.payload["speaker"], ev.payload["text"]
    refs = {"utt_id": utt_id}
    transcript = room.transcript()

    await room.emit("agent.progress", "agent", refs, {"stage": "routing"})
    t0 = time.perf_counter()
    label = await route(text, transcript)
    route_ms = _ms(t0)
    await room.emit("agent.routed", "agent", refs, {"label": label, "ms": route_ms})

    if label == "ignore":
        await room.emit("agent.progress", "agent", refs, {"stage": "done", "ms": route_ms})
        return

    if label == "ask":
        await room.emit("agent.progress", "agent", refs, {"stage": "asking"})
        t1 = time.perf_counter()
        answer, evidence = await ask(text, room.state, transcript)
        await room.emit("ask.answered", "agent", refs, {"answer": answer, "evidence_utt_ids": evidence, "ms": _ms(t1)})
        return

    await room.emit("agent.progress", "agent", refs, {"stage": "editing"})
    t1 = time.perf_counter()
    ops = await edit(text, speaker, room.state, transcript, label)
    edit_ms = _ms(t1)
    if not ops:
        await room.emit("agent.progress", "agent", refs, {"stage": "done", "ms": route_ms + edit_ms})
        return
    await room.changes.propose(ops, requested_by=speaker, utt_id=utt_id, via="voice",
                               reason=f"{speaker}: {text[:60]}",
                               latency_ms={"route": route_ms, "edit": edit_ms})
