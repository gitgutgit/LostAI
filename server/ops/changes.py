"""Change 수명주기와 커밋 정책 (docs/ARCHITECTURE.md 4-4, 5-3).

proposed → applied → approved | reverted,  실패는 failed,  지연 중 취소는 discarded.
policy: immediate(A·B) | delayed(C 제안 모드, N초 뒤 자동 반영)
"""
from __future__ import annotations

import asyncio
import copy
import logging
from typing import Any, Awaitable, Callable, Literal

from pydantic import BaseModel, Field

from server.model.docs import DocState
from server.ops.engine import OpError, anchors_of, apply_op, new_id, revert_diff

Status = Literal["proposed", "applied", "approved", "reverted", "discarded", "failed"]
Policy = Literal["immediate", "delayed"]

log = logging.getLogger(__name__)

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
            err = await self.revert(last.change_id, by=requested_by, via=via) if last else "되돌릴 변경이 없어요"
            ops = [o for o in ops if o.get("op") != "undo_last"]
            if not ops:
                if err:  # 발화 워커가 stage failed로 남긴다(조용히 done으로 끝나지 않게)
                    raise OpError(err)
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
        except Exception as e:  # OpError 밖의 예외(없는 문서 KeyError 등)도 반쯤 적용된 채로 두지 않는다
            self.state.__dict__.update(snapshot.__dict__)
            if not isinstance(e, OpError):  # 엔진이나 op 형식 문제일 수 있어 traceback을 서버 로그에 남긴다
                log.exception("apply failed change=%s ops=%s", change_id, ch.ops)
            ch.status = "failed"
            ch.error = str(e) if isinstance(e, OpError) else f"{type(e).__name__}: {e}"
            await self._emit("change.failed", ch)
            return
        ch.diff, ch.targets, ch.status = diff, anchors_of(diff), "applied"
        ch.applied_ts = self.now()
        ch.latency_ms["apply"] = int((self.now() - t0) * 1000)
        # 단계 값의 합(음성 변경이면 queue + route + edit + apply). 단계 사이 emit, 브로드캐스트와
        # 지연 정책의 대기 시간은 빠지므로 발화 도착 → 반영 벽시계 시간보다 짧다(벽시계는 done의 ms)
        ch.latency_ms["total"] = sum(v for k, v in ch.latency_ms.items() if k != "total")
        for a in ch.targets:
            self.state.provenance[a] = ch.change_id
        await self._emit("change.applied", ch)

    async def approve(self, change_id: str, by: str, via: str = "button") -> str | None:
        """승인할 변경이 없으면 이유 문장을 돌려준다. 이미 승인됐거나 반영 전인 경우는 조용히 넘긴다."""
        ch = self.changes.get(change_id)
        if ch is None:  # 리셋 전 변경이나 오래된 화면의 버튼
            return "이미 없는 변경이에요"
        if ch.status == "proposed":  # 지연 중 엄지 위 → 바로 반영
            self._cancel_timer(change_id)
            await self.apply(change_id)
        if ch.status != "applied":
            return None
        ch.approvals.append({"by": by, "via": via, "ts": self.now()})
        ch.status = "approved"
        await self._emit("change.approved", ch)
        return None

    async def revert(self, change_id: str, by: str, via: str = "button") -> str | None:
        """되돌릴 수 없으면 이유 문장을 돌려준다."""
        ch = self.changes.get(change_id)
        if ch is None:
            return "이미 없는 변경이에요"
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
        # 이 변경이 새로 만든 행, 구역 안을 이후 변경이 고쳤으면 그것부터 되돌려야 한다
        if self._dependents(ch):
            return "이 변경에 딸린 이후 변경을 먼저 되돌려 주세요"
        snapshot = copy.deepcopy(self.state)
        try:
            revert_diff(self.state, ch.diff)
        except Exception as e:  # 되돌리기가 반쯤 끝난 상태를 남기지 않는다
            # 반영도 의존 검사도 통과한 뒤의 실패라 엔진 상태 불일치(버그) 신호다
            log.exception("revert_diff failed change=%s", change_id)
            self.state.__dict__.update(snapshot.__dict__)
            return f"되돌릴 수 없어요 ({type(e).__name__}: {e})"
        for a in ch.targets:
            self.state.provenance.pop(a, None)
        ch.status = "reverted"
        ch.approvals.append({"by": by, "via": via, "ts": self.now(), "action": "revert"})
        await self._emit("change.reverted", ch)
        return None

    def _dependents(self, ch: Change) -> list[Change]:
        """ch가 새로 만든 앵커(diff before가 None인 행, 구역) 아래를 고친, ch보다 나중의 살아 있는 변경.

        이름 바꾸기나 삭제처럼 아무것도 만들지 않은 변경은 딸린 변경이 없다.
        """
        created = tuple(d["anchor"] + "/" for d in ch.diff if d.get("before") is None)
        if not created:
            return []
        ids = list(self.changes)  # dict는 제안 순서를 지킨다
        return [self.changes[i] for i in ids[ids.index(ch.change_id) + 1:]
                if self.changes[i].status in ("applied", "approved")
                and any(t.startswith(created) for t in self.changes[i].targets)]

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
