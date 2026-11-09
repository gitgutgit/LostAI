"""Server robustness regressions found in the 11-09 diagnosis (MOCK mode, no network).

Each test reproduces one defect that broke or froze the live demo:
stuck status chip, half-applied changes, sockets closed by one bad message,
dependent reverts, orphaned sockets after reset, 403 instead of 4401, add_note on the seed.
"""
import asyncio
import os

os.environ.setdefault("AGENT_MODE", "MOCK")

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from server.model.docs import load_seed
from server.ops.changes import ChangeManager
from server.ops.engine import apply_op


# ---------------------------------------------------------------- helpers

def _join(c: TestClient, name: str) -> str:
    r = c.post("/api/join", json={"name": name}).json()
    res = None
    for g in r["gestures"]:
        res = c.post(f"/api/join/{r['challenge_id']}/step",
                     json={"gesture": g, "confidence": 0.9, "hold_ms": 700}).json()
    assert res["status"] == "pass"
    return res["token"]


def _until(ws, pred, limit: int = 40) -> list[dict]:
    """Read messages until pred(msg) is true; return everything read."""
    seen = []
    for _ in range(limit):
        m = ws.receive_json()
        seen.append(m)
        if pred(m):
            return seen
    raise AssertionError(f"condition not met in {limit} messages: {[_kind(m) for m in seen]}")


def _kind(m: dict) -> str:
    return m["event"]["type"] if m.get("kind") == "event" else m["kind"]


def _is(type_: str, **payload):
    def pred(m):
        if m.get("kind") != "event" or m["event"]["type"] != type_:
            return False
        return all(m["event"]["payload"].get(k) == v for k, v in payload.items())
    return pred


def _manager():
    events: list[tuple[str, dict]] = []

    async def emit(type_, actor, refs, payload):
        events.append((type_, payload))

    clock = iter(range(1000))
    return ChangeManager(load_seed("sprint"), emit, lambda: float(next(clock))), events


# ---------------------------------------------------------------- engine and changes

def test_add_note_has_a_section_on_the_seed():
    s = load_seed("sprint")
    diff = apply_op(s, {"op": "add_note", "text": "메모 한 줄"})
    assert diff[0]["after"]["text"] == "메모 한 줄"


def test_non_operror_exception_rolls_back_whole_change():
    cm, events = _manager()
    before = cm.state.sheet("board").model_dump()
    ops = [{"op": "set_cell", "doc": "board", "row": "r_pay423", "column": "추정", "value": 99},
           {"op": "set_cell", "doc": "no_such_doc", "row": "r1", "column": "추정", "value": 1}]
    ch = asyncio.run(cm.propose(ops, requested_by="Ines"))
    assert ch.status == "failed"
    assert ch.error
    assert cm.state.sheet("board").model_dump() == before
    assert [t for t, _ in events] == ["change.proposed", "change.failed"]


def test_revert_blocked_while_later_change_depends_on_new_row():
    cm, _ = _manager()

    async def run():
        a = await cm.propose([{"op": "add_row", "doc": "board", "values": {"제목": "새 티켓"}}], requested_by="Ines")
        row_id = a.targets[0].split("/")[1]
        b = await cm.propose([{"op": "set_cell", "doc": "board", "row": row_id, "column": "추정", "value": 3}],
                             requested_by="Ines")
        blocked = await cm.revert(a.change_id, by="Ines")
        assert blocked  # refusal message, not an exception
        assert a.status == "applied"
        assert await cm.revert(b.change_id, by="Ines") is None
        assert await cm.revert(a.change_id, by="Ines") is None
        assert all(r.row_id != row_id for r in cm.state.sheet("board").rows)

    asyncio.run(run())


def test_unknown_change_id_is_a_message_not_a_crash():
    cm, _ = _manager()
    assert asyncio.run(cm.revert("c_missing", by="Ines"))
    assert asyncio.run(cm.approve("c_missing", by="Ines"))


# ---------------------------------------------------------------- pipeline and websocket

def test_done_stage_after_edit_and_after_ask():
    from server import app as app_mod

    with TestClient(app_mod.app) as c:
        token = _join(c, "Ines")
        with c.websocket_connect(f"/ws?token={token}") as ws:
            ws.receive_json()  # snapshot
            ws.send_json({"kind": "utterance.final", "payload": {"text": "결제 테스트가 불안정한 게 리스크야"}})
            seen = _until(ws, _is("agent.progress", stage="done"))
            assert "change.applied" in [_kind(m) for m in seen]
            applied = next(m for m in seen if _kind(m) == "change.applied")["event"]["payload"]
            assert {"queue", "route", "edit", "apply", "total"} <= set(applied["latency_ms"])

            ws.send_json({"kind": "utterance.final", "payload": {"text": "그거 누가 맡았지?"}})
            seen = _until(ws, _is("agent.progress", stage="done"))
            assert "ask.answered" in [_kind(m) for m in seen]


def test_bad_messages_do_not_close_the_socket():
    from server import app as app_mod

    with TestClient(app_mod.app) as c:
        token = _join(c, "Ines")
        with c.websocket_connect(f"/ws?token={token}") as ws:
            ws.receive_json()  # snapshot
            ws.send_text("not json")
            ws.send_json({"kind": "change.approve", "payload": {"change_id": "c_missing"}})
            ws.send_json({"kind": "change.revert", "payload": {"change_id": "c_missing"}})
            ws.send_json({"kind": "utterance.final", "payload": {}})
            ws.send_json({"kind": "gesture", "payload": {"kind": "Fingers_x"}})
            ws.send_json({"kind": "utterance.final", "payload": {"text": "결제 테스트가 불안정한 게 리스크야"}})
            seen = _until(ws, _is("change.applied"))
            assert any(m["kind"] == "notice" for m in seen)


def test_reset_keeps_sockets_and_processing_alive():
    from server import app as app_mod

    with TestClient(app_mod.app) as c:
        token = _join(c, "Ines")
        with c.websocket_connect(f"/ws?token={token}") as ws:
            ws.receive_json()  # snapshot
            ws.send_json({"kind": "utterance.final", "payload": {"text": "결제 테스트가 불안정한 게 리스크야"}})
            _until(ws, _is("change.applied"))
            assert c.post("/api/reset").json()["ok"]
            seen = _until(ws, lambda m: m["kind"] == "snapshot")
            assert "room.reset" in [_kind(m) for m in seen]
            snap = seen[-1]
            assert snap["changes"] == []
            assert "Ines" in snap["participants"]
            ws.send_json({"kind": "utterance.final", "payload": {"text": "결제 테스트가 불안정한 게 리스크야"}})
            _until(ws, _is("change.applied"))


def test_invalid_token_closes_with_4401():
    from server import app as app_mod

    with TestClient(app_mod.app) as c:
        with pytest.raises(WebSocketDisconnect) as e:
            with c.websocket_connect("/ws?token=Ines.bad") as ws:
                ws.receive_json()
        assert e.value.code == 4401


# ---------------------------------------------------------------- join secret

def test_join_secret_persists_across_restarts(tmp_path):
    from server.auth.challenge import load_secret

    path = tmp_path / "join_secret"
    first = load_secret("", path)
    assert load_secret("", path) == first
    assert (path.stat().st_mode & 0o777) == 0o600
    assert load_secret("fixed", path) == b"fixed"


def test_korean_name_token_verifies():
    from server.auth.challenge import make_token, verify_token

    assert verify_token(make_token("지원")) == "지원"
    assert verify_token("지원.bad") is None


def test_revert_not_blocked_when_nothing_was_created():
    cm, _ = _manager()

    async def run():
        await cm.propose([{"op": "add_decision", "text": "출시 연기"}], requested_by="Ines")
        rename = await cm.propose([{"op": "rename_section", "doc": "notes", "section": "s_dec", "heading": "결정"}],
                                  requested_by="Ines")
        assert await cm.revert(rename.change_id, by="Ines") is None

        await cm.propose([{"op": "set_cell", "doc": "board", "row": "r_pay423", "column": "추정", "value": 8}],
                         requested_by="Ines")
        delete = await cm.propose([{"op": "delete_row", "doc": "board", "row": "r_pay423"}], requested_by="Ines")
        assert await cm.revert(delete.change_id, by="Ines") is None
        _, row = next((i, r) for i, r in enumerate(cm.state.sheet("board").rows) if r.row_id == "r_pay423")
        assert row.cells["추정"] == 8

    asyncio.run(run())


def test_voice_undo_with_nothing_to_undo_is_a_failure_not_done():
    from server.ops.engine import OpError

    cm, _ = _manager()
    with pytest.raises(OpError):
        asyncio.run(cm.propose([{"op": "undo_last"}], requested_by="Ines"))


def test_thumb_down_refusal_is_broadcast():
    from server.gestures import fastpath
    from server.room import Room

    async def run():
        room = Room("t_thumb")
        sent: list[str] = []

        class Sock:
            async def send_text(self, data):
                sent.append(data)

        room.sockets[Sock()] = "Ines"
        a = await room.changes.propose([{"op": "add_row", "doc": "board", "values": {"제목": "x"}}], requested_by="Ines")
        row_id = a.targets[0].split("/")[1]
        b = await room.changes.propose([{"op": "set_cell", "doc": "board", "row": row_id, "column": "추정", "value": 3}],
                                       requested_by="Ines")
        await room.changes.approve(b.change_id, by="Kim")  # Thumb_Down now targets a (latest applied)
        fastpath._last.clear()
        await fastpath.handle_gesture(room, "Ines", "Thumb_Down", 0.9, 700)
        assert a.status == "applied"
        assert any('"notice"' in s for s in sent)

    asyncio.run(run())
