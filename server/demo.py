"""데모 자동 재생: 지금 시드의 대본을 회의방에 사람이 말하듯 한 줄씩 넣는다 (테스트, 시연용).

대본: server/model/scripts/<시드>.jsonl (없으면 fixtures/sample_<시드>.jsonl). 줄 형식은 server/replay.py와 같고
"gesture"(Fingers_3, Thumb_Up 같은 손 신호 이름)가 있으면 말 대신 그 사람의 손 신호로 보낸다.
gitgutgit: "wait"(초)가 있으면 앞 줄 처리가 끝난 뒤 그만큼 쉰다. 표결 결과·끝 화면을 보여 줄 때 쓴다. {"wait": 7}만 있는 줄도 된다.
속도: 읽는 시간만큼 기다렸다 말하고, 에이전트가 그 줄을 다 처리한 뒤 다음 줄로 간다 (PoC A Replay와 같은 방식).
손 신호 줄은 기다리지 않고 바로 이어 보낸다: 표결은 2초 안에 두 사람 이상이 손가락을 보여야 열린다.
author: ProfessionalSeaweedDevourer
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from pathlib import Path
from typing import TYPE_CHECKING

from server.replay import load_script

if TYPE_CHECKING:
    from server.room import Room

log = logging.getLogger(__name__)

ROOT = Path(__file__).parent.parent
SCRIPT_DIR = Path(__file__).parent / "model" / "scripts"


def script_path(seed: str) -> Path | None:
    for p in (SCRIPT_DIR / f"{seed}.jsonl", ROOT / "fixtures" / f"sample_{seed}.jsonl"):
        if p.is_file():
            return p
    return None


TURN_WAIT_SEC = 60.0  # gitgutgit 11-09: 입장한 사람의 차례를 이만큼 기다리고, 그래도 없으면 그 줄을 건너뛴다


def is_real_person(room: "Room", name: str | None) -> bool:
    """대본 화자와 같은 이름으로 진짜 사람이 입장해 있나."""
    return bool(name) and name in getattr(room, "participants", {})


def turn_kind(line: dict, vote_open: bool) -> str:
    """입장한 사람의 대본 줄이 무엇을 기다리나: vote(표) | gesture(손 신호) | line(말 한 줄)."""
    g = str(line.get("gesture") or "")
    if g.startswith("Fingers_") or (vote_open and line.get("text")):
        return "vote"
    return "gesture" if g else "line"


async def tell(room: "Room", name: str, text: str) -> None:
    """그 사람의 탭에만 안내를 띄운다 (빈 문자열이면 안내를 지운다). 이벤트 로그에는 남기지 않는다."""
    data = json.dumps({"kind": "notice", "text": text}, ensure_ascii=False)
    for ws, n in list(getattr(room, "sockets", {}).items()):
        if n == name:
            try:
                await ws.send_text(data)
            except Exception:
                pass


class Demo:
    def __init__(self) -> None:
        self.task: asyncio.Task | None = None
        self.seed = ""
        self.pos = 0
        self.total = 0
        self.speed = 1.0
        self.waiting_for: str | None = None  # 지금 차례를 기다리는 입장한 사람

    @property
    def running(self) -> bool:
        return self.task is not None and not self.task.done()

    def status(self, seed: str) -> dict:
        p = script_path(seed)
        lines = len(load_script(p)) if p else 0
        mine = self.seed == seed
        return {"seed": seed, "lines": lines, "running": self.running and mine,
                "pos": self.pos if mine else 0, "speed": self.speed,
                "waiting_for": self.waiting_for if mine else None}

    async def stop(self) -> None:
        task, self.task = self.task, None
        if task and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    def start(self, room: "Room", speed: float) -> int:
        p = script_path(room.seed_name)
        if p is None:
            return 0
        lines = load_script(p)
        self.seed, self.pos, self.total, self.speed = room.seed_name, 0, len(lines), speed
        self.task = asyncio.create_task(self._run(room, lines, speed))
        return len(lines)

    async def _run(self, room: "Room", lines: list[dict], speed: float) -> None:
        from server.gestures.fastpath import handle_gesture
        from server.gestures.votes import QUIET_CLOSE_SEC, votes
        try:
            for i, line in enumerate(lines):
                self.pos = i + 1
                if line.get("wait"):  # gitgutgit: 화면을 보여 줄 시간(표결 결과, 끝 화면). 처리가 끝난 뒤 그만큼 쉰다
                    await room.utterance_queue.join()
                    wait = float(line["wait"])
                    if votes.vote_id is not None:  # gitgutgit 11-09: 사람이 아직 표결 중이면 마감까지 기다린 뒤 결과를 보인다
                        while votes.vote_id is not None:
                            await asyncio.sleep(0.2)
                        wait = max(3.0, wait - QUIET_CLOSE_SEC)  # wait는 '마감 10초 + 볼 시간'으로 쓰여 있다
                    await asyncio.sleep(wait / speed)
                    if not line.get("text") and not line.get("gesture"):
                        continue
                if is_real_person(room, line.get("speaker")):
                    # gitgutgit 11-09: 입장한 사람의 줄은 대본이 대신 말하지 않는다. 그 사람에게 안내를 띄우고 직접 할 때까지 기다린다.
                    # 예전엔 Jiwon으로 입장해도 대본이 Jiwon 대사(표결 열기, 결정, 회의 끝)를 다 해 버려서 회의가 혼자 끝났다.
                    await self._wait_turn(room, line, votes)
                    continue
                if line.get("gesture"):
                    await room.utterance_queue.join()  # 엄지는 직전 줄의 변경을 가리키므로 처리가 끝난 뒤에
                    await handle_gesture(room, line["speaker"], line["gesture"], 1.0, 1000)
                    await asyncio.sleep(0.3 / speed)
                    continue
                await asyncio.sleep(min(3.0, len(line["text"]) * 0.03) / speed)
                await room.submit_utterance(line["speaker"], line["text"])
                await room.utterance_queue.join()
                await asyncio.sleep(0.6 / speed)
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("demo replay failed at line %d", self.pos)
        finally:
            if self.waiting_for:
                await tell(room, self.waiting_for, "")
                self.waiting_for = None

    async def _wait_turn(self, room: "Room", line: dict, votes) -> None:
        who = line["speaker"]
        await room.utterance_queue.join()
        kind = turn_kind(line, votes.vote_id is not None)
        since = room.events[-1].seq if room.events else 0
        if kind == "vote":
            await tell(room, who, "Your vote: show fingers, or say it (3 good · 2 okay · 1 no, or the option number).")
            done = lambda: who in votes.cast or votes.vote_id is None
        elif kind == "gesture":
            await tell(room, who, f"Your turn: show {line['gesture']}.")
            done = lambda: any(e.type == "gesture" and e.actor == who and e.seq > since for e in room.events)
        else:
            await tell(room, who, f'Your line: "{line["text"]}"  (say it or type it)')
            done = lambda: any(e.type == "utterance.final" and e.actor == who and e.seq > since for e in room.events)
        self.waiting_for = who
        end = time.monotonic() + TURN_WAIT_SEC
        while not done() and time.monotonic() < end:
            await asyncio.sleep(0.2)
        if not done():
            log.info("demo: %s did not take their turn in %.0fs, skipping line %d", who, TURN_WAIT_SEC, self.pos)
        self.waiting_for = None
        await tell(room, who, "")
        await room.utterance_queue.join()  # 그 사람이 한 말을 에이전트가 다 처리한 뒤 다음 줄


demo = Demo()
