# eval — 평가 대본 · 채점 도구 (기능 파트)

- **대본 작성자는 `server/agent/prompts.py`를 읽지 않는다.** 대본 작성과 프롬프트 수정은 같은 사람이 하지 않는다.
- 평가·시연 입력은 영어 원문.
- 채점: op 이름은 `server/ops/registry.py`의 `EVAL_ALIAS`로 묶어서 센다 (`insert_item`/`update_item` → `edit_doc`). 라우터 `ask`는 `command`(ops 빈 목록)로 센다.
- 결과: `results/<GitHub>_eval_<MMDD_HHMM>.json`, 숫자는 note `최근 결과`에 (MOCK/LIVE, 모델 표기).

TODO
- [ ] PoC 평가 대본·채점 도구 가져오기 (`eval/scripts/`, `eval/grade.py`)
- [ ] `eval/WRITING_SPEC.md`
