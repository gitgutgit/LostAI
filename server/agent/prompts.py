"""라우터, 에디터, Asker 시스템 프롬프트의 진입점. 정확도가 나쁘면 여기서 가리키는 파일부터 고친다.

내용은 기능별 파일에 있다(구조는 PoC shared/prompts.py: 라벨 정의, 애매할 때 고르는 규칙, op별 쓰임새, 공통 규칙).
- prompts_router.py : 라우터 시스템 프롬프트와 route 툴
- prompts_editor.py : 에디터 공통(op 고르는 기준, 공통 규칙)
- prompts_vote.py   : 에디터의 표결(질문 카드) 절. 발동 조건의 코드 쪽은 vote_trigger.py
- prompts_asker.py  : Asker
다른 모듈은 이 파일에서만 import 한다.

이 파일이나 prompts_*.py를 고치면 라우터 정확도, 지연 기준이 바뀐다 → note `메모`에 "<시각> 이후 기준 변경".
평가 대본 작성자는 이 파일과 prompts_*.py, vote_trigger.py를 읽지 않는다 (init-collab §2 평가 대본 규칙).
시스템 프롬프트는 바이트 단위로 고정해 둔다 (프롬프트 캐시). 시각, ID 같은 가변 값은 넣지 않는다.
"""
from server.agent.prompts_asker import ASKER_SYSTEM
from server.agent.prompts_editor import EDITOR_CORE
from server.agent.prompts_router import ROUTE_TOOL, ROUTER_SYSTEM
from server.agent.prompts_vote import VOTE_RULES

EDITOR_SYSTEM = f"{EDITOR_CORE}\n\n{VOTE_RULES}\nDo not write any other text."

__all__ = ["ASKER_SYSTEM", "EDITOR_SYSTEM", "ROUTER_SYSTEM", "ROUTE_TOOL"]
