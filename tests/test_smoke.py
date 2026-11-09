"""뼈대 스모크 테스트: 엔진 적용·역연산, 입장 관문 → WebSocket → 발화 → change.applied."""
import os

os.environ.setdefault("AGENT_MODE", "MOCK")

from fastapi.testclient import TestClient

from server.model.docs import load_seed
from server.ops.engine import apply_op, revert_diff


def test_apply_and_revert_roundtrip():
    s = load_seed("sprint")
    before = s.model_dump()
    diff = []
    diff += apply_op(s, {"op": "set_cell", "doc": "board", "row": "r_pay423", "column": "추정", "value": 3})
    diff += apply_op(s, {"op": "add_row", "doc": "board", "values": {"제목": "x"}})
    diff += apply_op(s, {"op": "add_decision", "text": "출시 연기"})
    diff += apply_op(s, {"op": "delete_item", "doc": "notes", "item": "i_7"})
    assert diff[0]["anchor"] == "board/r_pay423/추정"
    revert_diff(s, diff)
    assert s.model_dump() == before


def test_join_ws_utterance():
    from server import app as app_mod
    from server.auth import challenge

    with TestClient(app_mod.app) as c:
        r = c.post("/api/join", json={"name": "Ines"}).json()
        res = None
        for g in r["gestures"]:
            res = c.post(f"/api/join/{r['challenge_id']}/step",
                         json={"gesture": g, "confidence": 0.9, "hold_ms": 700}).json()
        assert res["status"] == "pass"
        assert challenge.verify_token(res["token"]) == "Ines"

        with c.websocket_connect(f"/ws?token={res['token']}") as ws:
            assert ws.receive_json()["kind"] == "snapshot"
            ws.send_json({"kind": "utterance.final", "payload": {"text": "결제 테스트가 불안정한 게 리스크야"}})
            types = []
            for _ in range(10):
                m = ws.receive_json()
                types.append(m["event"]["type"])
                if m["event"]["type"] == "change.applied":
                    break
            assert "change.applied" in types
