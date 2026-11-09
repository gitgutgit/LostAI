"""에디터 프롬프트의 표결(질문 카드) 절. 발동 조건의 코드 쪽은 server/agent/vote_trigger.py.

서버가 LLM 없이 처리하는 것(표결 중 '2번', 열린 질문이 있을 때의 맨 '투표하죠')은 에디터까지 오지 않는다.
에디터가 맡는 것은 질문 카드를 만들 때뿐이다. 선택지 순서가 표 번호이고, 선택지가 2개 미만이면
서버(vote_trigger.normalize_vote_ops)가 찬성/반대로 채우지만, 그 전에 여기서 제대로 내도록 한다.
"""

VOTE_RULES = """Votes (question cards):
- Call open_conflict when the team must choose: (a) a question that names 2 to 4 options to choose from; \
(b) a call to vote (the LATEST line is marked "vote call"), with the options named in the same utterance \
or in the recent transcript; (c) two participants state INCOMPATIBLE positions on the same topic \
(a date, an owner, a scope item, a number), or someone claims a task another person already owns.
- topic = the choice as one short question, in the language of the meeting.
- positions = one {"who": name, "says": short option label} per option, in the order the options were first named. \
The order is the vote number: the first position is option 1. who = the person who named or backs that option. \
Always give 2 to 4 positions.
- A vote call about a single proposal or topic with no alternatives named ("광고 페이지 우선순위로 투표하죠", \
"let's vote on shipping it Friday") → a yes/no card: topic = the proposal as a question, \
positions = "찬성" and "반대" (or "Yes" and "No" in an English meeting).
- A vote call about a choice that is already an unresolved conflict in the state → call no tools; \
the vote opens on that card. Never open a duplicate card.
- Mentioning a past vote, or a single number said as a pick, is never a new card."""
