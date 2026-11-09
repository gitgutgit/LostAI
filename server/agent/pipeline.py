"""발화 하나 → Router → Editor 또는 Asker → Op 엔진 (docs/ARCHITECTURE.md 5-1).

TODO(P1): 라우터와 에디터 동시 시작, interim 텍스트로 미리 라우팅 (6절).
"""
from __future__ import annotations

import time
from typing import TYPE_CHECKING

from server.agent.asker import ask
from server.agent.editor import edit
from server.agent.router import route
from server.agent.vote_trigger import (is_bare_vote_call, is_vote_call, normalize_vote_ops,
                                       question_from_ops, vote_pick, vote_pick_loose)
from server.events import Event
from server.gestures.votes import votes

if TYPE_CHECKING:
    from server.room import Room


# ep: 말로 하는 표결. 발동 조건은 server/agent/vote_trigger.py 에 모여 있다.
# - 표결 중 '2번' 같은 한마디 → LLM 없이 한 표.
# - 선택지도 주제도 없는 맨 부르기('투표하죠') + 열린 질문 → LLM 없이 가장 최근 질문으로 표결.
# - 주제나 선택지가 붙은 부르기 → 라우터를 건너뛰고(capture) 에디터가 질문 카드를 만든 뒤 그 질문으로 표결.
#   에디터가 '이미 같은 질문이 있다'며 카드를 안 만들면 가장 최근 질문으로 표결.


def _open_question(room: "Room") -> str | None:
    """해소 안 된 질문 중 가장 최근 것. 표결 마감은 질문을 닫지 않으므로 첫 것을 고르면 옛 질문으로 다시 열린다."""
    q = next((c for c in reversed(room.state.conflicts) if not c.resolved), None)
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

    # gitgutgit: 찬반 카드(선택지가 찬성/반대뿐) 표결이면 '좋아요/보통/싫어요'도 한 표(3/2/1).
    if votes.vote_id is not None and (n := vote_pick(text) or vote_pick_loose(text) or votes.rating_word(text)) is not None:
        await votes.cast_by_voice(room, speaker, n)
        await done("vote")
        return
    vote_call = is_vote_call(text)
    if vote_call and is_bare_vote_call(text) and (q := _open_question(room)) is not None:
        await votes.open_by_voice(room, speaker, q)
        await done("vote")
        return

    await room.emit("agent.progress", "agent", refs, {"stage": "routing"})
    t0 = time.perf_counter()
    # 표결 부르기는 언제나 질문 카드로 가므로 라우터 LLM을 건너뛴다(지연 1~2초 절약, 오분류 없음).
    label = "capture" if vote_call else await route(text, transcript)
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
    # 키워드는 표결 부르기일 때만 넘긴다(edit을 바꿔 끼우는 시험 대역이 옛 서명이어도 돌게).
    ops = await (edit(text, speaker, room.state, transcript, label, vote_call=True) if vote_call
                 else edit(text, speaker, room.state, transcript, label))
    edit_ms = _ms(t1)
    ops = normalize_vote_ops(ops, speaker, text)
    asked = question_from_ops(ops)
    failed = False
    if ops:
        ch = await room.changes.propose(ops, requested_by=speaker, utt_id=utt_id, via="voice",
                                        reason=f"{speaker}: {text[:60]}",
                                        latency_ms={"route": route_ms, "edit": edit_ms})
        failed = ch is not None and ch.status == "failed"
    if vote_call and not failed:
        # 이번 발화가 질문 카드를 만들었으면 그 질문(지연 반영이면 아직 상태에 없으므로 op에서 읽는다),
        # 카드를 안 만들었으면(같은 질문이 이미 열려 있음) 가장 최근 질문.
        if (q := asked or _open_question(room)) is not None:
            await votes.open_by_voice(room, speaker, q)
    await done(label)
