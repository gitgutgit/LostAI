"""손가락 표결 집계 (P2). 확인된 참석자 2명 이상이 2초 안에 손가락을 보이면 표결 시작, 5초 조용하면 마감.
gitgutgit: 표결은 두 가지. 질문 카드의 선택지가 찬성/반대뿐(또는 주장 하나 + 반대)이면 '찬반 카드' → 3 = 좋음, 2 = 보통, 1 = 싫음.
실제 선택지가 2~4개면 '선택지 카드' → 번호 1~N 고르기. 범위 밖의 손가락 수와 번호는 표로 세지 않는다.
화면(web/src/views/wall/live.ts)도 같은 규칙(is_rating_card)으로 카드 종류를 정한다.
ep: 말로 여는 표결(open_by_voice)과 말로 하는 한 표(cast_by_voice)를 더했다. 말로 연 표결은 아무도 안 내면 20초 뒤 마감."""
from __future__ import annotations

import asyncio
import logging
import re
import time
from typing import TYPE_CHECKING

log = logging.getLogger(__name__)

if TYPE_CHECKING:
    from server.room import Room

OPEN_WINDOW_SEC = 4.0   # gitgutgit 11-09: 2초 → 4초 (표결 시간 2배)
QUIET_CLOSE_SEC = 10.0  # 5초 → 10초
MIN_OPEN_SEC = 40.0     # hs: 투표 시간 40초로 넉넉하게
ALL_IN_CLOSE_SEC = 2.0  # gitgutgit 11-09: 입장한 사람이 모두 냈으면 화면에 ✓를 보일 만큼만 기다리고 마감
VOICE_OPEN_SEC = 40.0  # ep: 말로 연 표결의 첫 마감 시한
RATINGS = {3: "좋음", 2: "보통", 1: "싫음"}  # gitgutgit: 찬반 카드의 손가락 수 → 뜻
_AGAINST = {"반대", "no"}
# 찬반 카드에서 말 한마디로 한 표. 영어 회의(기본)와 한국어 회의 둘 다. 문장 전체가 이 말일 때만 센다.
_GOOD = r"좋아요?|좋음|좋습니다|찬성|good|yes|yeah|yep|agree|i agree|sounds good|for it|thumbs up"
_OKAY = r"보통(이에요|이요)?|그저 그래요?|괜찮아요|okay|ok|fine|neutral|so-so|so so|meh|maybe"
_NO = r"싫어요?|싫음|별로(예요|에요)?|반대|no|nope|bad|disagree|i disagree|against( it)?|thumbs down"
_RATING_WORDS = re.compile(rf"^\s*(?:[^:\s][^:]{{0,11}}:\s*)?(?:i say |i'?m |i vote |it'?s |that'?s )?({_GOOD}|{_OKAY}|{_NO})\s*[.!]?\s*$", re.IGNORECASE)


def is_rating_card(positions: list[dict[str, str]]) -> bool:
    """선택지가 1개 이하이거나 '반대'/'No'가 들어 있으면 찬반 카드(3·2·1)."""
    return len(positions) < 2 or any(str(p.get("says", "")).strip().lower() in _AGAINST for p in positions)


class Votes:
    def __init__(self) -> None:
        self.pending: dict[str, tuple[int, float]] = {}
        self.vote_id: str | None = None
        self.cast: dict[str, int] = {}
        self._closer: asyncio.Task | None = None
        self.deadline: float | None = None  # gitgutgit: 마감 시각(monotonic)
        self.opened_at = 0.0
        self.mode = "rating"          # "rating"(3·2·1) | "options"(1~N)
        self.max_option = 3
        self._conflict_id: str | None = None  # hs: 투표 대상 conflict ID (자동 resolve용)

    def _set_mode(self, room: "Room", question: str | None) -> str | None:
        """표결할 질문 카드를 찾아 종류를 정한다. 질문을 안 주면 가장 최근 열린 질문(화면과 같은 기준)."""
        conflicts = [c for c in room.state.conflicts if not c.resolved] if getattr(room, "state", None) else []
        card = next((c for c in conflicts if c.topic == question), None) if question else (conflicts[0] if conflicts else None)
        positions = card.positions if card else []
        self.mode = "rating" if is_rating_card(positions) else "options"
        self.max_option = 3 if self.mode == "rating" else min(len(positions), 4)
        self._conflict_id = card.conflict_id if card else None  # hs: 자동 resolve용
        return card.topic if card else question

    def valid(self, n: int) -> bool:
        return 1 <= n <= self.max_option

    def rating_word(self, text: str) -> int | None:
        """찬반 카드 표결 중 '좋아요/보통/싫어요' 한마디 → 3/2/1. 선택지 카드면 None."""
        if self.vote_id is None or self.mode != "rating" or not (m := _RATING_WORDS.match(text)):
            return None
        w = m.group(1).lower()
        if re.fullmatch(_GOOD, w, re.IGNORECASE):
            return 3
        if re.fullmatch(_OKAY, w, re.IGNORECASE):
            return 2
        return 1

    def reset(self) -> None:
        if self._closer:
            self._closer.cancel()
        self.__init__()

    async def on_fingers(self, room: "Room", who: str, n: int) -> None:
        if not 1 <= n <= 4:  # 주먹(0), 5는 어느 표결에서도 표가 아니다
            return
        now = time.monotonic()
        if self.vote_id is None:
            self.pending[who] = (n, now)
            self.pending = {k: v for k, v in self.pending.items() if now - v[1] < OPEN_WINDOW_SEC}
            if len(self.pending) < 2:
                return
            self.vote_id = f"v{len(room.events) + 1}"
            # TODO(P2): 직전 대사로 질문을 LLM이 비동기로 만든다. 지금은 가장 최근 열린 질문(없으면 None).
            question = self._set_mode(room, None)
            await room.emit("vote.opened", "server", {"vote_id": self.vote_id}, {"question": question, "closes_in": self._open_clock(room, QUIET_CLOSE_SEC)})
            for k, (m, _) in self.pending.items():
                if self.valid(m):
                    await self._cast(room, k, m)
            self.pending.clear()
        else:
            await self._cast(room, who, n)

    async def open_by_voice(self, room: "Room", by: str, question: str | None) -> bool:
        """ep: 표결을 말로 연다. 이미 열려 있으면 아무것도 하지 않는다."""
        if self.vote_id is not None:
            return False
        self.vote_id = f"v{len(room.events) + 1}"
        self._set_mode(room, question)
        await room.emit("vote.opened", by, {"vote_id": self.vote_id}, {"question": question, "closes_in": self._open_clock(room, VOICE_OPEN_SEC)})
        return True

    async def cast_by_voice(self, room: "Room", who: str, n: int) -> None:
        """ep: 열린 표결에 말로 한 표('2번', '좋아요')."""
        if self.vote_id is not None and self.valid(n):
            await self._cast(room, who, n)

    async def _cast(self, room: "Room", who: str, n: int) -> None:
        if not self.valid(n):
            return
        self.cast[who] = n
        # gitgutgit 11-09: 예전에는 표 하나마다 마감을 '지금부터 10초'로 다시 걸어서, 말로 연 40초 표결이
        # 대본 화자들의 첫 표에 10초로 줄어 사람이 손을 들기 전에 끝났다.
        # 이제: 열린 뒤 MIN_OPEN_SEC 안에는 마감하지 않고, 그 뒤로는 마지막 표 QUIET_CLOSE_SEC 뒤 마감.
        # 입장한 사람(room.participants)이 모두 직접 냈으면 ALL_IN_CLOSE_SEC 뒤 바로 마감.
        now = time.monotonic()
        people = set(getattr(room, "participants", {}) or {})
        if people and people <= set(self.cast):
            # hs: 2명 이상 모두 투표 → 빠르게 마감. 1명만 있을 때는 MIN_OPEN_SEC 대기 (카메라 초기화 시간 확보)
            if len(people) >= 2:
                at = now + ALL_IN_CLOSE_SEC
            else:
                at = max(now + ALL_IN_CLOSE_SEC, self.opened_at + MIN_OPEN_SEC)
        else:
            at = max(now + QUIET_CLOSE_SEC, self.opened_at + MIN_OPEN_SEC)
        await room.emit("vote.cast", who, {"vote_id": self.vote_id}, {"value": n, "closes_in": self._set_deadline(room, at)})

    def _open_clock(self, room: "Room", wait: float) -> float:
        self.opened_at = time.monotonic()
        return self._set_deadline(room, self.opened_at + wait)

    def _set_deadline(self, room: "Room", at: float) -> float:
        """마감 시각을 at(monotonic)으로 다시 걸고 남은 초를 돌려준다."""
        now = time.monotonic()
        self.deadline = at
        if self._closer:
            self._closer.cancel()
        self._closer = asyncio.create_task(self._close_later(room, max(0.0, at - now)))
        return round(at - now, 1)

    async def _close_later(self, room: "Room", wait: float = QUIET_CLOSE_SEC) -> None:
        await asyncio.sleep(wait)
        cast_copy = dict(self.cast)
        conflict_id = self._conflict_id
        await room.emit("vote.closed", "server", {"vote_id": self.vote_id},
                        {"votes": cast_copy, "counted": len(cast_copy)})
        self.vote_id, self.cast, self.deadline, self._conflict_id = None, {}, None, None
        # hs: 투표 결과로 conflict 자동 resolve — 과반 이상 한 쪽이면 결정
        log.info("_close_later: conflict_id=%s cast=%s", conflict_id, cast_copy)
        if conflict_id and cast_copy:
            await self._auto_resolve(room, conflict_id, cast_copy)
        else:
            log.info("_close_later: skip auto_resolve (no conflict_id or empty cast)")

    async def _auto_resolve(self, room: "Room", conflict_id: str, cast: dict[str, int]) -> None:
        """hs: 투표 결과 과반 이상이면 conflict를 자동 resolve한다."""
        from collections import Counter
        counts = Counter(cast.values())
        if not counts:
            return
        top_val, top_count = counts.most_common(1)[0]
        total = sum(counts.values())
        # 동점이면 resolve 안 함 (SPLIT)
        if len(counts) > 1 and counts.most_common(2)[1][1] == top_count:
            return
        # conflict 찾기
        card = None
        for c in room.state.conflicts:
            if c.conflict_id == conflict_id and not c.resolved:
                card = c
                break
        if not card:
            return
        # 결과 텍스트 생성
        positions = card.positions
        if is_rating_card(positions):
            label = RATINGS.get(top_val, str(top_val))
            resolution = f"Vote result: {label} ({top_count}/{total})"
        else:
            opt = positions[top_val - 1].get("says", f"Option {top_val}") if top_val <= len(positions) else f"Option {top_val}"
            resolution = f"Vote result: {opt} ({top_count}/{total})"
        # hs: resolve_conflict op 실행
        try:
            op = {"op": "resolve_conflict", "conflict": conflict_id, "resolution": resolution}
            log.info("auto_resolve: conflict=%s resolution=%s", conflict_id, resolution)
            await room.changes.propose(
                ops=[op], requested_by="server", utt_id=None, via="gesture"
            )
        except Exception:
            log.exception("auto_resolve FAILED conflict=%s", conflict_id)
            return
        # hs: 찬성(Good=3)이면 conflict topic에서 편집 명령을 뽑아 agent에 보내서 셀 편집 실행
        approved = (is_rating_card(positions) and top_val == 3) or (not is_rating_card(positions) and top_count > total / 2)
        if not approved:
            return
        # hs: topic에서 편집 명령 추출 — "XXX을 Y로 바꿀까요?" → "XXX을 Y로 바꿔줘"
        topic = card.topic
        edit_text = re.sub(r'[?？]$', '', topic).strip()  # 물음표 제거
        edit_text = re.sub(r'(할까요|할까|바꿀까요|바꿀까|될까요|될까|좋을까요|좋을까)$', '해줘', edit_text)
        # hs: 영어 질문도 처리 — "Should we ..." → "Please ..."
        edit_text = re.sub(r'^[Ss]hould we ', 'Please ', edit_text)
        edit_text = re.sub(r'^[Ss]hall we ', 'Please ', edit_text)
        if not edit_text or edit_text == topic.rstrip('?？ '):
            edit_text = topic.rstrip('?？ ') + ' 적용해줘'
        # 원래 요청자 찾기
        speaker = "server"
        for ch_obj in room.changes.changes.values():
            for op_item in ch_obj.ops:
                if op_item.get("op") == "open_conflict":
                    for d in ch_obj.diff:
                        if d.get("kind") == "conflict" and conflict_id in d.get("anchor", ""):
                            speaker = ch_obj.requested_by
                            break
        # hs: 라우터 건너뛰고 에디터 직접 호출 — LLM 라우터가 ignore로 분류하는 문제 방지
        log.info("auto_resolve: direct edit speaker=%s text=%s", speaker, edit_text)
        try:
            from server.agent.editor import edit as agent_edit
            ops = await agent_edit(edit_text, speaker, room.state, room.transcript(), "edit")
            if ops:
                await room.changes.propose(ops, requested_by=speaker, utt_id=None, via="gesture",
                                           reason=f"vote resolved: {edit_text[:60]}")
        except Exception:
            log.exception("auto_resolve edit FAILED text=%s", edit_text)


votes = Votes()
