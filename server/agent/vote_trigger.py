"""말로 하는 표결의 발동 조건. 파이프라인, MOCK 라우터, MOCK 에디터가 같은 판정을 쓴다.

발화를 넷으로 나눈다.
- 한 표(pick): 표결 중 '2번', 'option two' 같은 한마디. LLM 없이 한 표로 센다.
- 맨 부르기(bare call): 선택지도 주제도 없이 표결만 부르는 말('투표하죠.', 'Let's vote.', '자, 그거 투표로 정합시다').
  열린 질문이 있으면 LLM 없이 바로 표결을 연다.
- 주제가 붙은 부르기(call): '광고 페이지 우선순위로 투표 한 번 하죠', '화요일이랑 목요일 중에 투표하죠'.
  새 질문일 수 있으므로 에디터가 질문 카드(open_conflict)부터 만들고, 그 질문으로 표결을 연다.
- 고르기 질문(choice): '두 티켓 중에 뭐가 더 중요할까요?'. 질문 카드만 만들고 표결은 부를 때 연다.

맨 부르기 판정은 길이가 아니라 '부르는 말과 군말을 빼면 남는 내용이 없는가'로 한다.
길이로 자르면 짧은 주제 부르기('광고 페이지 우선순위로 투표 한 번 하죠', 2026-11-09 실사용 기록)가 옛 질문으로 열린다.

author: ProfessionalSeaweedDevourer
"""
from __future__ import annotations

import re
from typing import Any

_SPEAKER_PREFIX = re.compile(r"^\s*[^:\s][^:]{0,11}:\s*")
_HANGUL = re.compile(r"[가-힣]")

VOTE_CALL = re.compile(
    r"(투표|표결|다수결|거수|손\s*들어\s*(봅시다|보죠|볼까요|보자)|\bvot(e|es|ing)\b|show of hands|hands up)", re.IGNORECASE)
# 투표라는 말이 나와도 표결을 부르는 게 아닌 말: 미루기, 그만두기, 마감, 결과 묻기, 지난 표결 언급.
# 이런 말은 표결 부르기로 치지 않고 보통 발화처럼 라우터를 거친다(코드 리뷰 지적, 2026-11-09).
VOTE_NOT_A_CALL = re.compile(
    r"(하지 말|말죠|말자|나중에|다음에|안 해|안 하|않|그만|마감|끝내|끝났|취소|결과|했잖|했던|했었|"
    r"\bnot\b|n't\b|\blater\b|\bcancel|\bstop\b|\bend\b|\bclose|\bresults?\b|\bare in\b|\bvoted\b)",
    re.IGNORECASE)
CHOICE_QUESTION = re.compile(
    r"(뭐가 더|뭘 (먼저|더)|어느 ?(쪽|게|것|거)|중에 (뭐|뭘|어느|어떤)|중 (뭐|뭘|어느|어떤)|아니면 .*\?|"
    r"\bwhich\b|\bor\b.*\?|\bvs\.?\b)", re.IGNORECASE)

# 한글 숫자 읽기('이번', '사번')는 다른 뜻과 겹쳐 받지 않는다. 한국어 음성 인식은 '2번'처럼 숫자로 적는다.
_PICK_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4}
_PICK = re.compile(
    r"^\s*(?:(?:option|number|옵션)\s*|(?:no\.?|#)\s*(?=[1-4]))?([1-4]|one|two|three|four)\s*"
    r"(?:번|표|번이요|번요|번이에요|번으로|번 할게요|번 찍을게요)?\s*[.!]?\s*$", re.IGNORECASE)

# 맨 부르기에서 빼는 말. 부르는 말의 어간을 뗀 나머지 토막('투표로' → '로', '투표하죠' → '하죠')도 여기서 지운다.
_CALL_STEMS = re.compile(r"(투표|표결|다수결|거수|votes|voting|vote)", re.IGNORECASE)
_FILLER = {
    # 한국어 군말, 어미, 조사
    "자", "그럼", "그러면", "그냥", "일단", "우리", "이제", "바로", "다들", "모두", "다", "한", "번", "한번",
    "그거", "이거", "그걸", "이걸", "그거로", "이거로", "그걸로", "이걸로", "그것도",
    "손", "들어", "들어서", "들어보죠", "봅시다", "보죠", "볼까요", "봐요", "주세요", "보자",
    "하죠", "합시다", "할까요", "하자", "해요", "해", "해서", "해봅시다", "해보죠", "해볼까요", "하겠습니다", "할게요",
    "정하죠", "정합시다", "정해요", "정할까요", "정하자", "결정하죠", "결정합시다", "결정해요",
    "가죠", "갑시다", "가자", "시작", "시작하죠", "시작합시다", "부치죠", "부칩시다", "붙이죠",
    "로", "으로", "를", "을", "에", "요", "네", "좋아요", "좋습니다", "그래요", "오케이",
    # 영어 군말
    "let's", "lets", "let", "us", "ok", "okay", "so", "then", "we", "i", "take", "a", "quick", "now", "all",
    "right", "alright", "please", "go", "to", "it", "on", "decide", "hands", "hand", "up", "show", "of",
    "call", "the", "everyone", "guys", "should", "shall", "do", "just", "by", "raise", "your", "this", "that",
    "time", "for", "have", "put", "s",
}


def strip_speaker(text: str) -> str:
    """시험용 채팅의 'Name: 말' 머리를 뗀다."""
    return _SPEAKER_PREFIX.sub("", text, count=1)


def vote_pick(text: str) -> int | None:
    """표결 중 한 표면 번호(1~4), 아니면 None."""
    body = strip_speaker(text)
    if m := _PICK.match(body):
        v = m.group(1).lower()
        return int(v) if v.isdigit() else _PICK_WORDS[v]
    return None


# 표결 중에만 쓰는 느슨한 한 표: '2번에 투표할게요', '저는 2번이요', 'I vote 2', 'I pick option 3'.
_PICK_LOOSE = [
    re.compile(r"(?<![\d-])([1-4])\s*번"),
    re.compile(r"\b(?:vote|pick|go with|choose)\s+(?:for\s+)?(?:option\s+|number\s+)?([1-4]|one|two|three|four)\b",
               re.IGNORECASE),
]


def vote_pick_loose(text: str) -> int | None:
    """표결이 열려 있을 때만 쓴다. 번호가 정확히 하나 나오고 부정이 없으면 그 번호."""
    body = strip_speaker(text)
    if VOTE_NOT_A_CALL.search(body) or "?" in body:
        return None
    found = {m.group(1).lower() for rx in _PICK_LOOSE for m in rx.finditer(body)}
    if len(found) != 1:
        return None
    v = found.pop()
    return int(v) if v.isdigit() else _PICK_WORDS[v]


def is_vote_call(text: str) -> bool:
    """표결을 부르는 말인가. '투표하지 말죠', '투표 결과 뭐였지?'처럼 투표를 말하기만 하는 것은 아니다."""
    return bool(VOTE_CALL.search(text)) and not VOTE_NOT_A_CALL.search(strip_speaker(text))


def is_choice_question(text: str) -> bool:
    return bool(CHOICE_QUESTION.search(text))


def is_bare_vote_call(text: str) -> bool:
    """표결을 부르기만 하고 선택지나 주제를 말하지 않았는가."""
    if not is_vote_call(text):
        return False
    body = strip_speaker(text).lower()
    tokens = re.findall(r"[\w']+", body)
    for tok in tokens:
        rest = _CALL_STEMS.sub("", tok)
        if rest and rest not in _FILLER:
            return False
    return True


def normalize_vote_ops(ops: list[dict[str, Any]], speaker: str, text: str) -> list[dict[str, Any]]:
    """질문 카드(open_conflict)의 선택지를 표결할 수 있는 모양으로 맞춘다.

    - 선택지 키가 PoC 식({speaker, claim})이면 {who, says}로 바꾼다.
    - 선택지가 0개면 찬성/반대(영어 회의면 Yes/No), 1개면 그 주장과 반대. 2026-11-09 LIVE 실사용에서 선택지 0개 카드가 나왔다.
    - 5개 이상이면 앞의 4개만 둔다(번호 표결과 손가락 1~4).
    """
    out = []
    for op in ops:
        if op.get("op") != "open_conflict":
            out.append(op)
            continue
        positions = []
        for p in op.get("positions") or []:
            if not isinstance(p, dict):
                continue
            says = str(p.get("says") or p.get("claim") or p.get("option") or "").strip()
            who = str(p.get("who") or p.get("speaker") or speaker).strip()
            if says:
                positions.append({"who": who, "says": says})
        korean = bool(_HANGUL.search(f"{op.get('topic', '')} {text}"))
        yes, no = ("찬성", "반대") if korean else ("Yes", "No")
        if not positions:
            positions = [{"who": speaker, "says": yes}, {"who": speaker, "says": no}]
        elif len(positions) == 1:  # 주장 하나(남의 작업을 가져가겠다 등)는 지우지 않고 반대 선택지만 붙인다
            positions.append({"who": speaker, "says": no})
        out.append({**op, "positions": positions[:4]})
    return out


def question_from_ops(ops: list[dict[str, Any]]) -> str | None:
    """이번 발화가 만든 질문 카드의 주제(마지막 것)."""
    return next((o.get("topic") for o in reversed(ops) if o.get("op") == "open_conflict" and o.get("topic")), None)
