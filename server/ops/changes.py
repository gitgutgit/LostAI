"""Change 수명주기와 커밋 정책 (docs/ARCHITECTURE.md 4-4, 5-3).

proposed → applied → approved | reverted,  실패는 failed,  지연 중 취소는 discarded.
policy: immediate(A·B) | delayed(C 제안 모드, N초 뒤 자동 반영)
"""
from __future__ import annotations

import asyncio
import copy
from typing import Any, Awaitable, Callable, Literal

from pydantic import BaseModel, Field

from server.model.docs import DocState
from server.ops.engine import OpError, anchors_of, apply_op, new_id, revert_diff

Status = Literal["proposed", "applied", "approved", "reverted", "discarded", "failed"]
Policy = Literal["immediate", "delayed"]

APPROVE_WINDOW_SEC = 15.0  # 엄지 위/아래가 대상으로 삼는 최근 변경 범위


class Change(BaseModel):
    change_id: str
    utt_id: str | None = None
    requested_by: str
    via: Literal["voice", "gesture", "button"] = "voice"
    ops: list[dict[str, Any]]
    targets: list[str] = Field(default_factory=list)
    diff: list[dict[str, Any]] = Field(default_factory=list)
    status: Status = "proposed"
    policy: Policy = "immediate"
    reason: str | None = None
    error: str | None = None
    approvals: list[dict[str, Any]] = Field(default_factory=list)
    latency_ms: dict[str, int] = Field(default_factory=dict)
    applied_ts: float | None = None


Emit = Callable[[str, str, dict[str, Any], dict[str, Any]], Awaitable[None]]
# emit(type, actor, refs, payload)


class ChangeManager:
    def __init__(self, state: DocState, emit: Emit, now: Callable[[], float],
                 policy: Policy = "immediate", delay_sec: float = 5.0):
        self.state = state
        self.emit = emit
        self.now = now
        self.policy = policy
        self.delay_sec = delay_sec
        self.changes: dict[str, Change] = {}
        self._timers: dict[str, asyncio.Task] = {}

    # ---- 생성 ----
    async def propose(self, ops: list[dict[str, Any]], requested_by: str, utt_id: str | None = None,
                      via: str = "voice", reason: str | None = None,
                      latency_ms: dict[str, int] | None = None) -> Change | None:
        # undo_last 는 엔진 op가 아니라 상태 전이다.
        if any(o.get("op") == "undo_last" for o in ops):
            last = self.latest(statuses=("applied", "approved"))
            if last:
                await self.revert(last.change_id, by=requested_by, via=via)
            ops = [o for o in ops if o.get("op") != "undo_last"]
            if not ops:
                return last

        ch = Change(change_id=new_id("c"), utt_id=utt_id, requested_by=requested_by, via=via,  # type: ignore[arg-type]
                    ops=ops, policy=self.policy, reason=reason, latency_ms=latency_ms or {})
        self.changes[ch.change_id] = ch
        await self._emit("change.proposed", ch)
        if self.policy == "immediate":
            await self.apply(ch.change_id)
        else:
            self._timers[ch.change_id] = asyncio.create_task(self._delayed_apply(ch.change_id))
        return ch

    async def _delayed_apply(self, change_id: str) -> None:
        await asyncio.sleep(self.delay_sec)
        await self.apply(change_id)

    # ---- 전이 ----
    async def apply(self, change_id: str) -> None:
        ch = self.changes[change_id]
        if ch.status != "proposed":
            return
        t0 = self.now()
        snapshot = copy.deepcopy(self.state)  # 원자성: 하나라도 실패하면 되돌린다
        diff: list[dict[str, Any]] = []
        try:
            for op in ch.ops:
                diff += apply_op(self.state, op)
        except OpError as e:
            self.state.__dict__.update(snapshot.__dict__)
            ch.status, ch.error = "failed", str(e)
            await self._emit("change.failed", ch)
            return
        ch.diff, ch.targets, ch.status = diff, anchors_of(diff), "applied"
        ch.applied_ts = self.now()
        ch.latency_ms["apply"] = int((self.now() - t0) * 1000)
        for a in ch.targets:
            self.state.provenance[a] = ch.change_id
        await self._emit("change.applied", ch)

    async def approve(self, change_id: str, by: str, via: str = "button") -> None:
        ch = self.changes[change_id]
        if ch.status == "proposed":  # 지연 중 엄지 위 → 바로 반영
            self._cancel_timer(change_id)
            await self.apply(change_id)
        if ch.status != "applied":
            return
        ch.approvals.append({"by": by, "via": via, "ts": self.now()})
        ch.status = "approved"
        await self._emit("change.approved", ch)

    async def revert(self, change_id: str, by: str, via: str = "button") -> str | None:
        """되돌릴 수 없으면 이유 문장을 돌려준다."""
        ch = self.changes[change_id]
        if ch.status == "proposed":
            self._cancel_timer(change_id)
            ch.status = "discarded"
            await self._emit("change.discarded", ch)
            return None
        if ch.status not in ("applied", "approved"):
            return f"status {ch.status}"
        # 이후 변경이 같은 앵커를 또 바꿨으면 충돌 → 막는다 (해커톤 범위)
        later = [a for a in ch.targets if self.state.provenance.get(a) not in (ch.change_id, None)]
        if later:
            return "이후에 바뀐 칸이라 되돌릴 수 없어요"
        revert_diff(self.state, ch.diff)
        for a in ch.targets:
            self.state.provenance.pop(a, None)
        ch.status = "reverted"
        ch.approvals.append({"by": by, "via": via, "ts": self.now(), "action": "revert"})
        await self._emit("change.reverted", ch)
        return None

    # ---- 조회 ----
    def latest(self, statuses: tuple[str, ...] = ("applied",), within_sec: float | None = None) -> Change | None:
        for ch in reversed(list(self.changes.values())):
            if ch.status not in statuses:
                continue
            if within_sec is not None and ch.applied_ts is not None and self.now() - ch.applied_ts > within_sec:
                return None
            return ch
        return None

    def _cancel_timer(self, change_id: str) -> None:
        t = self._timers.pop(change_id, None)
        if t:
            t.cancel()

    async def _emit(self, type_: str, ch: Change) -> None:
        await self.emit(type_, "agent" if ch.via == "voice" else ch.requested_by,
                        {"utt_id": ch.utt_id, "change_id": ch.change_id}, ch.model_dump())
