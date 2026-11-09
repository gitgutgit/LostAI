"""발화 하나 → Router → Editor 또는 Asker → Op 엔진 (docs/ARCHITECTURE.md 5-1).

TODO(P1): 라우터와 에디터 동시 시작, interim 텍스트로 미리 라우팅 (6절).
"""
from __future__ import annotations

import re
import time
from typing import TYPE_CHECKING

from server.agent.asker import ask
from server.agent.editor import edit
from server.agent.router import route
from server.events import Event
from server.gestures.votes import votes

if TYPE_CHECKING:
    from server.room import Room


# ep: 말로 하는 표결. 표결 부르기('투표하죠')는 열린 질문이 있으면 LLM 없이 바로 표결을 열고,
# 없으면 라우터, 에디터가 질문(open_conflict)부터 만든 뒤 연다. 표결 중 '2번' 같은 한마디는 한 표로 센다.
VOTE_CALL = re.compile(r"(투표|표결|다수결|손 ?들어|\bvote\b|voting)", re.IGNORECASE)
VOTE_PICK = re.compile(r"^\s*(?:[^:]{1,12}:\s*)?([1-4])\s*(번|표|번이요|번요|번이에요)?\s*[.!]?\s*$")


def _open_question(room: "Room") -> str | None:
    q = next((c for c in room.state.conflicts if not c.resolved), None)
    return q.topic if q else None


def _ms(t0: float) -> int:
    return int((time.perf_counter() - t0) * 1000)


async def handle_utterance(room: "Room", ev: Event) -> None:
    """정상으로 끝나는 모든 갈래(ignore, ask, edit, op 없음)에서 stage "done"을 한 번 보낸다.

    화면 상태 칩이 routing, asking, editing에서 벗어나는 신호다. 예외(LLM 시간 초과 포함)로 끝나면
    done 대신 발화 워커(room.py)가 stage "failed"를 보낸다.
    done의 ms는 발화가 서버에 도착한 때(ev.ts)부터 처리가 끝날 때까지의 벽시계 시간이다(큐 대기 포함).
    """
    utt_id, speaker, text = ev.refs.utt_id, ev.payload["speaker"], ev.payload["text"]
    refs = {"utt_id": utt_id}
    transcript = room.transcript()

    async def done(label: str) -> None:
        await room.emit("agent.progress", "agent", refs,
                        {"stage": "done", "label": label, "ms": int((room.now() - ev.ts) * 1000)})

    if votes.vote_id is not None and (m := VOTE_PICK.match(text)):
        await votes.cast_by_voice(room, speaker, int(m.group(1)))
        await done("vote")
        return
    if VOTE_CALL.search(text) and (q := _open_question(room)) is not None:
        await votes.open_by_voice(room, speaker, q)
        await done("vote")
        return

    await room.emit("agent.progress", "agent", refs, {"stage": "routing"})
    t0 = time.perf_counter()
    label = await route(text, transcript)
    route_ms = _ms(t0)
    await room.emit("agent.routed", "agent", refs, {"label": label, "ms": route_ms})

    if label == "ignore":
        await done(label)
        return

    if label == "ask":
        await room.emit("agent.progress", "agent", refs, {"stage": "asking"})
        t1 = time.perf_counter()
        answer, evidence = await ask(text, room.state, transcript)
        await room.emit("ask.answered", "agent", refs, {"answer": answer, "evidence_utt_ids": evidence, "ms": _ms(t1)})
        await done(label)
        return

    await room.emit("agent.progress", "agent", refs, {"stage": "editing"})
    t1 = time.perf_counter()
    ops = await edit(text, speaker, room.state, transcript, label)
    edit_ms = _ms(t1)
    if ops:
        await room.changes.propose(ops, requested_by=speaker, utt_id=utt_id, via="voice",
                                   reason=f"{speaker}: {text[:60]}",
                                   latency_ms={"route": route_ms, "edit": edit_ms})
        if VOTE_CALL.search(text) and (q := _open_question(room)) is not None:
            await votes.open_by_voice(room, speaker, q)
    await done(label)
