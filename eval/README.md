# eval — 평가 대본 · 채점 도구 (기능 파트)

- **대본 작성자는 `server/agent/prompts.py`를 읽지 않는다.** 대본 작성과 프롬프트 수정은 같은 사람이 하지 않는다.
- 평가·시연 입력은 영어 원문.
- 채점: op 이름은 `server/ops/registry.py`의 `EVAL_ALIAS`로 묶어서 센다 (`insert_item`/`update_item` → `edit_doc`). 라우터 `ask`는 `command`(ops 빈 목록)로 센다.
- 결과: `results/<GitHub>_eval_<MMDD_HHMM>.json`, 숫자는 note `최근 결과`에 (MOCK/LIVE, 모델 표기).

## 말로 하는 표결 발동 채점 (LIVE)
- `AGENT_MODE=LIVE uv run python eval/vote_live.py --runs 3`: 블라인드 시나리오 `eval/vote_scenarios_blind.json` 14개(한국어 8, 영어 6, 표결이 열리면 안 되는 경우 3 포함)로 표결이 맞는 질문으로 열리는지, 질문 카드 선택지가 2~4개인지, 표결이 열리기까지의 시간을 잰다. 채점 규칙은 스크립트 docstring.
- 시나리오는 프롬프트와 `server/agent/vote_trigger.py`를 읽지 않은 작성자가 썼다. 시나리오를 고치는 사람도 그 파일들을 읽지 않는다.

TODO
- [ ] PoC 평가 대본·채점 도구 가져오기 (`eval/scripts/`, `eval/grade.py`)
- [ ] `eval/WRITING_SPEC.md`
