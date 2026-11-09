"""Linear 티켓 생성 (P2). create_ticket diff를 Linear 이슈로 만든다.

TODO: PoC OAuth 설정(credentials.json / token.json) 재사용. 비밀 파일 내용은 출력·기록하지 않는다.
"""
from __future__ import annotations

import os
from typing import Any

from server.model.docs import DocState


def enabled() -> bool:
    return bool(os.getenv("LINEAR_API_KEY"))


def push(state: DocState, event_type: str, change: dict[str, Any]) -> None:
    """event_type: change.applied | change.reverted. 실패하면 예외를 올린다 (Outbox가 재시도)."""
    raise NotImplementedError("linear.push")
