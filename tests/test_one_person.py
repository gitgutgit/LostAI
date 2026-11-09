"""1인 회의 리허설: 개발자 한 명이 4인 회의의 모든 요소를 MOCK으로 몰고, 계약(server/events.py)의 이벤트 종류마다
실제로 한 번 이상 나왔는지 센다. 판정 기준은 내 판단이 아니라 계약 목록이다.

몰기 방식은 화면의 1인 시험(web/src/views/wall/puppets.ts)과 같다: 수동 입장 소켓마다 한 사람,
발화는 utterance.final, 손은 gesture 메시지. 카메라와 마이크가 없어도 된다.
실행: `uv run pytest -q tests/test_one_person.py -s` (약 15초, 비용 0원).
author: ProfessionalSeaweedDevourer
"""
import os
import time
import typing

os.environ.setdefault("AGENT_MODE", "MOCK")

from fastapi.testclient import TestClient

from server.events import EventType

# 이 시험이 낼 수 없는 종류와 이유. 여기 없는 종류가 안 나오면 실패한다.
EXEMPT = {
    "sync.ok": "Google 동기화는 시험에서 꺼 둔다(conftest)",
    "sync.failed": "Google 동기화는 시험에서 꺼 둔다(conftest)",
    "doc.pulled": "Google 문서 당겨오기, 외부 연결 필요",
    "change.failed": "MOCK 에디터는 실패하는 op를 만들지 않는다. tests/test_server_robustness.py가 직접 다룬다",
    "change.discarded": "지연 반영 중(proposed) 되돌림에서만 난다. MOCK 에디터는 바로 반영한다",
}
# 계약에는 있으나 서버가 아직 내지 않는 종류. 발견 기록이며, 고쳐지면 지운다.
KNOWN_GAPS = {
    "participant.rejected": "입장 3회 실패 때 응답만 manual이고 이벤트를 내지 않는다(server/app.py join_step)",
}


def _wait(c: TestClient, pred, sec: float = 8.0) -> list[dict]:
    end = time.time() + sec
    while time.time() < end:
        ev = c.get("/api/state").json()["events"]
        if pred(ev):
            return ev
        time.sleep(0.1)
    raise AssertionError("시간 안에 기대한 이벤트가 오지 않음")


def _has(type_: str, **payload):
    return lambda ev: any(e["type"] == type_ and all(e["payload"].get(k) == v for k, v in payload.items()) for e in ev)


def test_one_person_runs_the_whole_meeting():
    from server import app as app_mod
    from server import room as room_mod

    try:
        ev, state = _run(app_mod)
    finally:
        # 회의방 작업자는 이 시험 클라이언트의 이벤트 루프에 묶여 있다. 남기면 다음 시험의 발화가 멈춘다.
        room_mod.rooms.pop("main", None)
    _judge(ev, state)


def _run(app_mod):
    with TestClient(app_mod.app) as c:
        c.post("/api/reset")
        # 입장: 손동작 관문 통과 한 명(Ines), 나머지는 호스트 수동 입장
        r = c.post("/api/join", json={"name": "Ines"}).json()
        for g in r["gestures"]:
            res = c.post(f"/api/join/{r['challenge_id']}/step", json={"gesture": g, "confidence": 0.9, "hold_ms": 700}).json()
        tok = {"Ines": res["token"]}
        for n in ("Owen", "Eric", "Ravi"):
            tok[n] = c.post("/api/join/manual", json={"name": n, "host": "Eric"}).json()["token"]

        ws = {n: c.websocket_connect(f"/ws?token={t}").__enter__() for n, t in tok.items()}
        try:
            for s in ws.values():
                assert s.receive_json()["kind"] == "snapshot"

            def say(who, text, pred, final=True):
                ws[who].send_json({"kind": "utterance.final" if final else "utterance.interim", "payload": {"text": text}})
                return _wait(c, pred)

            def hand(who, kind, pred):
                ws[who].send_json({"kind": "gesture", "payload": {"kind": kind, "confidence": 1, "hold_ms": 1000}})
                return _wait(c, pred)

            n_applied = lambda k: (lambda ev: sum(e["type"] == "change.applied" for e in ev) >= k)

            say("Owen", "로그 정리", lambda ev: any(e["type"] == "utterance.interim" for e in ev), final=False)
            say("Owen", "로그 정리 티켓 추가해 줘", n_applied(1))                      # 시트 행 추가
            hand("Eric", "Thumb_Up", lambda ev: any(e["type"] == "change.approved" for e in ev))
            say("Ines", "결제 테스트가 불안정한 게 리스크야", n_applied(2))              # 노트 문서
            hand("Owen", "Thumb_Down", lambda ev: any(e["type"] == "change.reverted" for e in ev))
            say("Ravi", "점심 뭐 먹지", _has("agent.routed", label="ignore"))
            say("Ines", "PAY-423 담당이 누구였지?", lambda ev: any(e["type"] == "ask.answered" for e in ev))

            # 질문 카드와 표결: 말로 열고, 말과 손가락으로 한 표씩
            say("Eric", "PAY-423이랑 AUTH-118 두 티켓 중에 뭐가 더 중요할까요?",
                lambda ev: any(e["type"] == "change.applied" and any(o["op"] == "open_conflict" for o in e["payload"]["ops"]) for e in ev))
            say("Eric", "투표하죠.", lambda ev: any(e["type"] == "vote.opened" for e in ev))
            say("Ines", "1번", lambda ev: sum(e["type"] == "vote.cast" for e in ev) >= 1)
            say("Owen", "2번", lambda ev: sum(e["type"] == "vote.cast" for e in ev) >= 2)
            hand("Ravi", "Fingers_1", lambda ev: sum(e["type"] == "vote.cast" for e in ev) >= 3)
            # 마감은 표가 들어와도 앞당겨지지 않는다(40초). 입장한 4명이 모두 내면 ALL_IN_CLOSE_SEC 뒤 바로 마감.
            say("Eric", "2번", lambda ev: sum(e["type"] == "vote.cast" for e in ev) >= 4)
            from server.gestures.votes import ALL_IN_CLOSE_SEC
            ev = _wait(c, lambda ev: any(e["type"] == "vote.closed" for e in ev), sec=ALL_IN_CLOSE_SEC + 5)
            closed = next(e for e in ev if e["type"] == "vote.closed")
            assert closed["payload"]["votes"] == {"Ines": 1, "Owen": 2, "Ravi": 1, "Eric": 2}

            # 멈춤, 재개(T자), 말로 취소, 퇴장
            hand("Eric", "T_Shape", lambda ev: any(e["type"] == "agent.paused" for e in ev))
            hand("Owen", "T_Shape", lambda ev: any(e["type"] == "agent.resumed" for e in ev))
            say("Owen", "방금 거 취소해 줘", lambda ev: sum(e["type"] == "change.reverted" for e in ev) >= 2)
            ws.pop("Ravi").__exit__(None, None, None)
            ev = _wait(c, lambda ev: any(e["type"] == "participant.left" for e in ev))

            state = c.get("/api/state").json()
        finally:
            # 중간 실패에도 소켓을 닫아야 시험 클라이언트가 멈추지 않고 실패를 보여 준다
            for s in ws.values():
                s.__exit__(None, None, None)
    return ev, state


def _judge(ev, state):
    seen = {e["type"] for e in ev}
    contract = set(typing.get_args(EventType))
    missing = sorted(contract - seen - set(EXEMPT) - set(KNOWN_GAPS))
    print(f"\n계약 {len(contract)}종 중 이 시험이 낸 것 {len(seen & contract)}종, 제외 {len(EXEMPT)}, 알려진 빈칸 {len(KNOWN_GAPS)}")
    for k, why in KNOWN_GAPS.items():
        print(f"  빈칸 {k}: {why}")
    assert not missing, f"안 나온 이벤트 종류: {missing}"
    assert not (seen & set(KNOWN_GAPS)), "알려진 빈칸이 고쳐졌다: KNOWN_GAPS에서 지울 것"
    # 문서 결과: 시트에 행이 남았고(승인됨), 말로 한 취소는 직전 변경인 질문 카드 열기를 되돌렸다
    assert any("로그 정리" in str(r["cells"]) for r in state["state"]["docs"]["board"]["rows"])
    assert state["state"]["conflicts"] == []
