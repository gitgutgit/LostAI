"""LIVE LLM 워밍업: 첫 발화 콜드 스타트(라우터 3.5~8초, PR #9 측정)를 없앤다. author: Mal-Mi-Jal

서버 시작·`/api/reset` 때 라우터와 에디터를 한 번씩 미리 부른다.
- 연결(TLS)·클라이언트 생성과 고정 프롬프트 캐시(system + tools, ephemeral 약 5분)를 데운다.
- 결과는 버린다. 회의방 상태는 깊은 복사본만 넘기므로 아무것도 바뀌지 않고, 이벤트 로그에도 안 남긴다.
- MOCK이면 아무것도 안 한다. 실패해도 회의는 그대로 (로그 한 줄).
"""
from __future__ import annotations

import asyncio
import logging
import time

from server.model.docs import DocState

log = logging.getLogger("uvicorn.error")

WARMUP_TEXT = "(서버 워밍업: 무시)"


async def warm_llm(state: DocState) -> dict[str, int] | None:
    from server.agent import llm
    if not llm.is_live():
        return None
    from server.agent.editor import edit
    from server.agent.router import route

    async def timed(coro):
        t0 = time.perf_counter()
        await coro
        return int((time.perf_counter() - t0) * 1000)

    try:
        route_ms, edit_ms = await asyncio.gather(
            timed(route(WARMUP_TEXT, [])),
            timed(edit(WARMUP_TEXT, "system", state.model_copy(deep=True), [], "capture")),
        )
    except Exception as e:  # 키 없음·네트워크 등: 회의는 계속
        log.warning("LLM warmup failed: %s", str(e)[:200])
        return None
    log.info("LLM warmup done: router %dms, editor %dms", route_ms, edit_ms)
    return {"route": route_ms, "edit": edit_ms}


def schedule_warmup(state: DocState) -> asyncio.Task:
    """기다리지 않고 백그라운드로 (서버 시작을 늦추지 않는다)."""
    return asyncio.create_task(warm_llm(state))
