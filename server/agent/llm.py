"""Anthropic 클라이언트와 상태 요약 헬퍼."""
from __future__ import annotations

import json
import os
from functools import lru_cache

from server.model.docs import DocState


def is_live() -> bool:
    return os.getenv("AGENT_MODE", "MOCK").upper() == "LIVE"


# 호출 하나가 멈추면 발화 큐 전체가 멈춘다(워커 하나가 순서대로 처리). SDK 기본값은 600초에 재시도 2회.
LLM_TIMEOUT_SEC = 20.0
LLM_MAX_RETRIES = 1


@lru_cache(maxsize=1)
def client():
    import anthropic  # LIVE일 때만 필요
    return anthropic.AsyncAnthropic(timeout=LLM_TIMEOUT_SEC, max_retries=LLM_MAX_RETRIES)


ROUTER_MODEL = os.getenv("ROUTER_MODEL", "claude-haiku-5-5")
EDITOR_MODEL = os.getenv("EDITOR_MODEL", "claude-sonnet-5-5")


def state_summary(state: DocState) -> str:
    """에디터에 보내는 상태. provenance는 빼서 짧게 유지한다."""
    data = state.model_dump(exclude={"provenance"})
    return json.dumps(data, ensure_ascii=False, sort_keys=True)


def transcript_text(lines: list[dict[str, str]]) -> str:
    return "\n".join(f"[{l['utt_id']}] {l['speaker']}: {l['text']}" for l in lines)
