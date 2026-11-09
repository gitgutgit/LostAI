"""이벤트 로그 → 발화별 지연. author: Mal-Mi-Jal"""
from server.common.event_latency import per_utterance, summarize


def ev(seq, ts, type_, utt=None, change=None, **payload):
    return {"seq": seq, "ts": ts, "type": type_, "actor": "x",
            "refs": {"utt_id": utt, "change_id": change}, "payload": payload}


LOG = [
    ev(1, 10.000, "utterance.final", "u1", text="추정 3으로"),
    ev(2, 10.100, "agent.progress", "u1", stage="routing"),
    ev(3, 10.400, "agent.routed", "u1", label="edit", ms=400),
    ev(3, 11.900, "change.applied", "u1", "c1", latency_ms={"route": 400, "edit": 1450, "apply": 3}),
    ev(4, 12.400, "sync.ok", "u1", "c1", target="google_sheets", ms=480),
    ev(5, 20.000, "utterance.final", "u2", text="음 그러니까"),
    ev(6, 20.300, "agent.routed", "u2", label="ignore", ms=300),
    ev(7, 25.000, "sync.ok", None, None, target="google_docs", ms=900),  # 시작 전체 동기화: 발화 없음 → 무시
]


def test_per_utterance():
    rows = per_utterance(LOG)
    assert rows[0] == {"utt_id": "u1", "text": "추정 3으로", "queue_wait": 100, "label": "edit", "utt_to_routed": 400,
                       "utt_to_applied": 1900, "proc_to_applied": 1800, "route": 400, "edit": 1450, "apply": 3,
                       "sync_google_sheets": 480, "utt_to_synced_google_sheets": 2400}
    assert rows[1] == {"utt_id": "u2", "text": "음 그러니까", "label": "ignore", "utt_to_routed": 300}


def test_summarize_vs_goal():
    s = summarize(LOG)
    assert s["utterances"] == 2
    assert s["latency_ms"]["utt_to_routed"]["n"] == 2
    assert s["vs_goal"]["utt_to_applied"] == {"p50": 1900, "goal_lt": 2500, "ok": True}
    assert s["vs_goal"]["edit"]["ok"] is True and s["vs_goal"]["apply"]["ok"] is True


def test_stt_interim_to_final():
    log = [
        {**ev(1, 4.0, "utterance.interim", text="추정"), "actor": "태우"},
        {**ev(2, 4.2, "utterance.interim", text="추정"), "actor": "한서"},
        {**ev(3, 4.5, "utterance.interim", text="추정 3"), "actor": "태우"},
        {**ev(4, 5.2, "utterance.final", "u1", text="추정 3으로"), "actor": "태우"},
        {**ev(5, 9.0, "utterance.final", "u2", text="입력창"), "actor": "태우"},  # interim 없음(입력창) → 값 없음
    ]
    rows = per_utterance(log)
    assert rows[0]["stt_interim_to_final"] == 1200 and rows[0]["stt_endpoint"] == 700
    assert "stt_interim_to_final" not in rows[1] and "stt_endpoint" not in rows[1]
