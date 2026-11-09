"""지연 퍼센타일 계산 (p50/p95). author: (초기 뼈대)"""
from __future__ import annotations


def percentiles(values: list[float]) -> dict[str, float | None]:
    if not values:
        return {"p50": None, "p95": None, "n": 0}
    s = sorted(values)

    def q(p: float) -> float:
        i = min(len(s) - 1, max(0, round(p * (len(s) - 1))))
        return s[i]

    return {"p50": q(0.5), "p95": q(0.95), "n": len(s)}
