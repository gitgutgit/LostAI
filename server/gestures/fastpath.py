"""손 신호 빠른 길: LLM 없이 규칙으로 1초 안에 처리 (docs/ARCHITECTURE.md 5-2-3)."""
from __future__ import annotations

import time
from typing import TYPE_CHECKING

from server.ops.changes import APPROVE_WINDOW_SEC

if TYPE_CHECKING:
    from server.room import Room

COOLDOWN_SEC = 2.0
_last: dict[tuple[str, str], float] = {}


async def handle_gesture(room: "Room", who: str, kind: str, confidence: float, hold_ms: int) -> None:
    now = time.monotonic()
    if now - _last.get((who, kind), 0) < COOLDOWN_SEC:
        return
    _last[(who, kind)] = now

    await room.emit("gesture", who, {}, {"kind": kind, "confidence": confidence, "hold_ms": hold_ms})

    if kind in ("Thumb_Up", "Thumb_Down"):
        target = room.changes.latest(statuses=("proposed", "applied"), within_sec=APPROVE_WINDOW_SEC)
        if target is None:
            return  # 대상 없음: 화면이 작은 안내만 띄운다
        if kind == "Thumb_Up":
            await room.changes.approve(target.change_id, by=who, via="THUMB_UP")
        else:
            err = await room.changes.revert(target.change_id, by=who, via="THUMB_DOWN")
            if err:  # 손을 내렸는데 아무 일도 없어 보이지 않게 모두에게 알린다
                await room.broadcast({"kind": "notice", "text": err})
    elif kind == "T_Shape":  # P2
        room.paused = not room.paused
        await room.emit("agent.paused" if room.paused else "agent.resumed", who, {}, {"by": who, "via": "T_SHAPE"})
    elif kind.startswith("Fingers_"):
        from server.gestures.votes import votes
        await votes.on_fingers(room, who, int(kind.split("_")[1]))
