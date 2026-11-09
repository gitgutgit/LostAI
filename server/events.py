"""이벤트 계약 (docs/ARCHITECTURE.md 4-1). ← 계약 파일: 수정 시 팀장 승인 + web/src/core/types.ts 동시 수정."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

EventType = Literal[
    # 참석
    "participant.joined",
    "participant.verified",
    "participant.rejected",
    "participant.left",
    # 발화
    "utterance.interim",
    "utterance.final",
    # 손
    "gesture",
    # 표결
    "vote.opened",
    "vote.cast",
    "vote.closed",
    # 에이전트
    "agent.routed",
    "agent.progress",
    # 변경
    "change.proposed",
    "change.applied",
    "change.approved",
    "change.reverted",
    "change.discarded",
    "change.failed",
    # 묻기
    "ask.answered",
    # 동기화
    "sync.ok",
    "sync.failed",
    "doc.pulled",
    # 제어
    "agent.paused",
    "agent.resumed",
    "room.reset",
]

Actor = str  # "agent" | "server" | "<참석자 이름>"

RouteLabel = Literal["ignore", "capture", "edit", "command", "ask"]

GestureKind = Literal[
    "Thumb_Up",
    "Thumb_Down",
    "Pointing_Up",
    "Victory",
    "Open_Palm",
    "Closed_Fist",
    "ILoveYou",
    "Fingers_0",
    "Fingers_1",
    "Fingers_2",
    "Fingers_3",
    "Fingers_4",
    "Fingers_5",
    "T_Shape",
]


class Refs(BaseModel):
    utt_id: str | None = None
    change_id: str | None = None
    vote_id: str | None = None


class Event(BaseModel):
    seq: int
    ts: float  # 회의 시작 기준 초
    type: EventType
    actor: Actor
    refs: Refs = Field(default_factory=Refs)
    payload: dict[str, Any] = Field(default_factory=dict)


# ---- payload 모델 (payload dict의 형태를 문서화하고 검증할 때 쓴다) ----


class UtterancePayload(BaseModel):
    speaker: str
    text: str


class GesturePayload(BaseModel):
    kind: GestureKind
    confidence: float
    hold_ms: int = 0


class AgentRoutedPayload(BaseModel):
    label: RouteLabel
    ms: int


class AgentProgressPayload(BaseModel):
    stage: Literal["routing", "editing", "asking", "applying", "done", "failed"]
    ms: int | None = None


class ParticipantPayload(BaseModel):
    name: str
    gestures: list[GestureKind] = Field(default_factory=list)
    result: Literal["pass", "fail", "manual"] | None = None
    elapsed_ms: int | None = None


class AskAnsweredPayload(BaseModel):
    answer: str
    evidence_utt_ids: list[str] = Field(default_factory=list)


class SyncPayload(BaseModel):
    target: Literal["google_sheets", "google_docs", "linear"]
    change_id: str | None = None
    error: str | None = None
    ms: int | None = None


# 클라이언트 → 서버 WebSocket 메시지
class ClientMessage(BaseModel):
    kind: Literal["utterance.interim", "utterance.final", "gesture", "change.approve", "change.revert"]
    payload: dict[str, Any] = Field(default_factory=dict)
