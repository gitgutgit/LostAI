"""말로 하는 표결의 발동 채점 (LIVE). 블라인드 시나리오를 실제 라우터, 에디터로 돌린다.

    AGENT_MODE=LIVE uv run python eval/vote_live.py --runs 3

시나리오 `eval/vote_scenarios_blind.json`은 프롬프트(server/agent/prompts*.py)와 vote_trigger.py를 읽지 않은
작성자(서브에이전트)가 제품 동작 설명만 보고 썼다(2026-11-09). 대본 작성과 프롬프트 수정을 나누는 eval 규칙.

채점 규칙(실행 전 고정):
- votes_ok: 연 표결 수(vote.opened) == expect_votes
- last_ok: 마지막 표결의 질문 카드(같은 topic의 conflict)가 question_keywords 중 하나를 질문이나 선택지에 담고,
  기대 선택지 i번이 카드 선택지 i번과 동의어로 맞는다(선택지 순서 = 표 번호)
- cards_ok: 연 모든 표결의 카드 선택지가 2~4개
- pass = 셋 다
표결이 열리면 Ines '1번', Owen '2번'으로 표를 내고 마감을 기다린 뒤 다음 대사를 보낸다.
hold_vote 시나리오(표결이 열린 채 다시 부르기)는 표를 내지 않고 바로 다음 대사를 보낸다.

author: ProfessionalSeaweedDevourer
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--scenarios", default=str(ROOT / "eval" / "vote_scenarios_blind.json"))
    ap.add_argument("--only", default="", help="쉼표로 시나리오 id 제한, 예: s01,s05")
    ap.add_argument("--out", default="")
    a = ap.parse_args()
    if os.getenv("AGENT_MODE", "MOCK").upper() != "LIVE":
        sys.exit("AGENT_MODE=LIVE 에서만 의미가 있다 (MOCK 정확도는 의미 없음)")
    os.environ["COMMIT_POLICY"] = "immediate"
    os.chdir(ROOT)

    from fastapi.testclient import TestClient

    from server import app as app_mod
    from server import room as room_mod

    scenarios = json.load(open(a.scenarios))
    if a.only:
        keep = set(a.only.split(","))
        scenarios = [s for s in scenarios if s["id"] in keep]
    out_path = Path(a.out or ROOT / "results" / f"ProfessionalSeaweedDevourer_vote_live_{datetime.now():%m%d_%H%M}.jsonl")
    out_path.parent.mkdir(exist_ok=True)

    def events() -> list[dict]:
        r = room_mod.rooms.get("main")
        return [e.model_dump() for e in r.events] if r else []

    def wait(pred, sec: float = 45) -> list[dict]:
        end = time.time() + sec
        while time.time() < end:
            ev = events()
            if pred(ev):
                return ev
            time.sleep(0.2)
        return events()

    def count(ev, t, **kw) -> int:
        return sum(e["type"] == t and all(e["payload"].get(k) == v for k, v in kw.items()) for e in ev)

    def same(a_: str, syns: list[str]) -> bool:
        a_ = a_.lower()
        return any(s and (s.lower() in a_ or a_ in s.lower()) for s in syns)

    def run_one(sc: dict) -> dict:
        try:
            with TestClient(app_mod.app) as c:
                c.post("/api/reset")
                tok = {p: c.post("/api/join/manual", json={"name": p, "host": "Eric"}).json()["token"]
                       for p in ("Eric", "Ines", "Owen", "Ravi")}
                ws = {p: c.websocket_connect(f"/ws?token={t}").__enter__() for p, t in tok.items()}
                for s in ws.values():
                    s.receive_json()
                lat = []
                for who, text in sc["lines"]:
                    ev0 = events()
                    d0, f0 = count(ev0, "agent.progress", stage="done"), count(ev0, "agent.progress", stage="failed")
                    o0, t0 = count(ev0, "vote.opened"), time.time()
                    ws[who].send_json({"kind": "utterance.final", "payload": {"text": text}})
                    ev = wait(lambda e: count(e, "agent.progress", stage="done") > d0
                              or count(e, "agent.progress", stage="failed") > f0)
                    if count(ev, "vote.opened") > o0:
                        lat.append(round(time.time() - t0, 2))
                        if sc.get("hold_vote"):
                            continue
                        c0 = count(ev, "vote.closed")
                        ws["Ines"].send_json({"kind": "utterance.final", "payload": {"text": "1번"}})
                        ws["Owen"].send_json({"kind": "utterance.final", "payload": {"text": "2번"}})
                        wait(lambda e: count(e, "vote.closed") > c0, 30)
                ev = events()
                cards = {k.topic: [p.get("says", "") for p in k.positions] for k in room_mod.rooms["main"].state.conflicts}
                qs = [e["payload"].get("question") for e in ev if e["type"] == "vote.opened"]
                for s in ws.values():
                    s.__exit__(None, None, None)
        finally:
            room_mod.rooms.pop("main", None)
        rec = {"id": sc["id"], "questions": qs, "cards": cards, "lat": lat,
               "votes_ok": len(qs) == sc["expect_votes"],
               "cards_ok": all(2 <= len(cards.get(q, [])) <= 4 for q in qs if q)}
        if sc["expect_votes"] and qs:
            q, lv = qs[-1] or "", sc["last_vote"]
            opts = cards.get(q, [])
            blob = (q + " " + " ".join(opts)).lower()
            kw_ok = any(k.lower() in blob for k in lv["question_keywords"])
            opt_ok = len(opts) >= len(lv["options"]) and all(same(opts[i], s) for i, s in enumerate(lv["options"]))
            rec["last_ok"] = kw_ok and opt_ok
        else:
            rec["last_ok"] = sc["expect_votes"] == 0
        rec["pass"] = rec["votes_ok"] and rec["last_ok"] and rec["cards_ok"]
        return rec

    recs = []
    with open(out_path, "w") as out:
        for r in range(a.runs):
            for sc in scenarios:
                try:
                    rec = run_one(sc)
                except Exception as e:  # 한 시나리오가 전체를 멈추지 않게, 실패로 센다
                    rec = {"id": sc["id"], "error": repr(e)[:200], "pass": False, "lat": []}
                rec["run"] = r
                recs.append(rec)
                out.write(json.dumps(rec, ensure_ascii=False) + "\n")
                out.flush()
                print(r, rec["id"], "PASS" if rec["pass"] else "FAIL", rec.get("questions", rec.get("error")), flush=True)
    lat = [x for r in recs for x in r["lat"]]
    print(f"\npass {sum(r['pass'] for r in recs)}/{len(recs)}, cards_ok {sum(r.get('cards_ok', False) for r in recs)}/{len(recs)}, "
          f"vote open latency p50 {round(statistics.median(lat), 2) if lat else '-'}s max {max(lat) if lat else '-'}s, LIVE → {out_path}")


if __name__ == "__main__":
    main()
