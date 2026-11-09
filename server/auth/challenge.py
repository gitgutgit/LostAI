"""입장 관문: 랜덤 손동작 3개 발급 → 단계 결과 검증 → 입장 토큰 (docs/ARCHITECTURE.md 5-2-1).

도전은 서버가 만든다(브라우저가 고르면 녹화 영상으로 통과 가능). 만료 60초.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import random
import secrets
import time
from dataclasses import dataclass, field

CHALLENGE_TTL_SEC = 60
STEPS = 3
MIN_HOLD_MS = 600
MIN_CONFIDENCE = 0.6
MAX_FAILS_BEFORE_MANUAL = 3

CANDIDATES = ["Thumb_Up", "Thumb_Down", "Pointing_Up", "Victory", "Open_Palm", "Closed_Fist",
              "ILoveYou"]  # hs: MediaPipe 기본 제스처 7개만 사용 (커스텀 Fingers_* 제거)
# 같은 도전에 같이 넣지 않는 헷갈리는 쌍
CONFUSABLE: list[set[str]] = []  # hs: 기본 제스처만 쓰므로 헷갈리는 쌍 없음 (Fingers_* 제거됨)

_SECRET = (os.getenv("JOIN_SECRET") or secrets.token_hex(16)).encode()


@dataclass
class Challenge:
    challenge_id: str
    name: str
    gestures: list[str]
    issued_at: float
    step: int = 0
    fails: int = 0
    started_ms: float = field(default_factory=lambda: time.time() * 1000)

    @property
    def expired(self) -> bool:
        return time.time() - self.issued_at > CHALLENGE_TTL_SEC


_challenges: dict[str, Challenge] = {}


def _pick() -> list[str]:
    while True:
        g = random.sample(CANDIDATES, STEPS)
        if not any(pair <= set(g) for pair in CONFUSABLE):
            return g


def issue(name: str) -> Challenge:
    ch = Challenge(challenge_id=secrets.token_urlsafe(8), name=name, gestures=_pick(), issued_at=time.time())
    _challenges[ch.challenge_id] = ch
    return ch


def submit_step(challenge_id: str, gesture: str, confidence: float, hold_ms: int) -> dict:
    """반환: {"status": "next"|"pass"|"retry"|"expired"|"manual", ...}"""
    ch = _challenges.get(challenge_id)
    if ch is None or ch.expired:
        return {"status": "expired"}
    expected = ch.gestures[ch.step]
    if gesture != expected or confidence < MIN_CONFIDENCE or hold_ms < MIN_HOLD_MS:
        ch.fails += 1
        if ch.fails >= MAX_FAILS_BEFORE_MANUAL:
            return {"status": "manual", "expected": expected}
        return {"status": "retry", "expected": expected, "step": ch.step}
    ch.step += 1
    if ch.step < STEPS:
        return {"status": "next", "step": ch.step, "expected": ch.gestures[ch.step]}
    _challenges.pop(challenge_id, None)
    return {"status": "pass", "token": make_token(ch.name),
            "elapsed_ms": int(time.time() * 1000 - ch.started_ms), "gestures": ch.gestures}


def make_token(name: str) -> str:
    sig = hmac.new(_SECRET, name.encode(), hashlib.sha256).hexdigest()[:24]
    return f"{name}.{sig}"


def verify_token(token: str) -> str | None:
    name, _, sig = token.rpartition(".")
    if name and hmac.compare_digest(make_token(name), token):
        return name
    return None
