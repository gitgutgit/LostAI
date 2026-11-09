"""대본 → 회의방 재생, 단계별 지연 기록 (docs/ARCHITECTURE.md 13절 "리플레이와 단계별 지연 측정").

대본 JSONL 한 줄: {"speaker": "Ines", "text": "...", "delay": 1.5}
  (fixture 이벤트 JSONL이면 utterance.final 줄만 골라 재생한다)
실행: uv run python -m server.replay fixtures/sample_sprint.jsonl [--out results/<GitHub>_replay_MMDD_HHMM.json]
"""
from __future__ import annotations

import argparse
import asyncio
import json
import time
from pathlib import Path

from dotenv import load_dotenv

from server.agent.llm import is_live
from server.common.event_latency import summarize


def load_script(path: Path) -> list[dict]:
    lines = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        if not raw.strip():
            continue
        d = json.loads(raw)
        if "type" in d:  # fixture 이벤트
            if d["type"] == "utterance.final":
                lines.append({"speaker": d["payload"]["speaker"], "text": d["payload"]["text"], "delay": 0})
        else:
            lines.append(d)
    return lines


async def run(path: Path, out: Path | None, realtime: bool, seed: str = "sprint") -> dict:
    from server.room import Room

    room = Room("replay", seed=seed)  # 대본은 시드 기준으로 쓰여 있다 (.env SEED=google이어도 원본을 안 건드린다)
    room.start()
    for line in load_script(path):
        if not line.get("text"):  # 손 신호·wait 줄(데모 자동 재생용)은 리플레이에서 건너뛴다
            continue
        if realtime and line.get("delay"):
            await asyncio.sleep(line["delay"])
        await room.submit_utterance(line["speaker"], line["text"])
    await room.utterance_queue.join()

    changes = list(room.changes.changes.values())
    e2e = summarize(room.events)  # 이벤트 로그 기준 말 → 화면 (리플레이는 Google 동기화를 돌리지 않는다)
    summary = {
        "script": str(path),
        "mode": "LIVE" if is_live() else "MOCK",
        "utterances": e2e["utterances"],
        "routes": [e.payload["label"] for e in room.events if e.type == "agent.routed"],
        "changes": {s: sum(1 for c in changes if c.status == s) for s in {c.status for c in changes}},
        "latency_ms": e2e["latency_ms"],
        "vs_goal": e2e["vs_goal"],
        "event_log": str(room.log_path),
    }
    if out:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


def main() -> None:
    load_dotenv()
    ap = argparse.ArgumentParser()
    ap.add_argument("script", type=Path)
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--realtime", action="store_true", help="delay 값만큼 기다리며 재생")
    ap.add_argument("--seed", default="sprint", help="시작 문서 (server/model/seeds/<이름>.json)")
    a = ap.parse_args()
    t0 = time.perf_counter()
    summary = asyncio.run(run(a.script, a.out, a.realtime, a.seed))
    summary["wall_sec"] = round(time.perf_counter() - t0, 2)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
