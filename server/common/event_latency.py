"""이벤트 로그 → 발화별 지연 (말 → 화면, 말 → Google 문서). author: Mal-Mi-Jal

이벤트 로그가 단일 진실이므로 지연도 로그의 ts(회의 시작 기준 초)만으로 계산한다.
- utt_to_routed : utterance.final → agent.routed           (라우터)
- utt_to_applied: utterance.final → change.applied          (= 말 → 화면. 브로드캐스트는 emit 안에서 같이 나간다)
- utt_to_synced : utterance.final → sync.ok (대상별)         (= 말 → 실제 Google 문서)
- route / edit / apply : change.latency_ms 단계값 (pipeline·ChangeManager가 잰 것)
- sync_<대상>   : sync.ok payload.ms (Google 호출 자체)
STT 시간(말 끝 → 브라우저 final)은 서버 로그에 없다 → 화면 쪽에서 따로 잰다.

    uv run python -m server.common.event_latency results/events_main_1109_140000.jsonl
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

from server.common.latency import percentiles

TARGETS_MS = {"utt_to_applied": 2500, "route": 600, "edit": 1500, "apply": 50}  # CLAUDE.md 목표 숫자


def _d(e: Any) -> dict[str, Any]:
    return e if isinstance(e, dict) else e.model_dump()


def per_utterance(events: Iterable[Any]) -> list[dict[str, Any]]:
    """발화 하나당 한 줄. 변경이 없던 발화(ignore·ask)도 라우터 시간은 남긴다."""
    rows: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    for raw in events:
        e = _d(raw)
        refs, p, t, ts = e.get("refs") or {}, e.get("payload") or {}, e["type"], e["ts"]
        uid = refs.get("utt_id")
        if not uid:
            continue
        if t == "utterance.final":
            rows[uid] = {"utt_id": uid, "text": p.get("text", ""), "t0": ts, "synced": {}}
            order.append(uid)
            continue
        r = rows.get(uid)
        if r is None:
            continue
        if t == "agent.routed":
            r["label"] = p.get("label")
            r["utt_to_routed"] = round((ts - r["t0"]) * 1000)
        elif t == "change.applied" and "utt_to_applied" not in r:
            r["utt_to_applied"] = round((ts - r["t0"]) * 1000)
            for k, v in (p.get("latency_ms") or {}).items():
                r[k] = v
        elif t == "sync.ok" and p.get("target") not in r["synced"]:
            r["synced"][p["target"]] = round((ts - r["t0"]) * 1000)
            r[f"sync_{p['target']}"] = p.get("ms")
    out = []
    for uid in order:
        r = rows[uid]
        r.pop("t0")
        for tgt, ms in r.pop("synced").items():
            r[f"utt_to_synced_{tgt}"] = ms
        out.append(r)
    return out


def summarize(events: Iterable[Any]) -> dict[str, Any]:
    rows = per_utterance(events)
    cols: dict[str, list[float]] = defaultdict(list)
    for r in rows:
        for k, v in r.items():
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                cols[k].append(v)
    stats = {k: percentiles(v) for k, v in sorted(cols.items())}
    verdict = {}
    for k, goal in TARGETS_MS.items():
        p50 = (stats.get(k) or {}).get("p50")
        if p50 is not None:
            verdict[k] = {"p50": p50, "goal_lt": goal, "ok": p50 < goal}
    return {"utterances": len(rows), "latency_ms": stats, "vs_goal": verdict}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    evs = load_jsonl(Path(sys.argv[1]))
    print(json.dumps(summarize(evs), ensure_ascii=False, indent=2))
