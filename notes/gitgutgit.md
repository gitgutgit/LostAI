# Note — 지원 (gitgutgit) · 총괄 · 공용 계약 메인

> 마지막 업데이트: 2026-11-09 10:20
> 한 줄 상태: 🟢 진행 중 — 레포 뼈대 완성 (MOCK 모드로 끝까지 동작), 팀원 작업 시작 가능
> 실행: `uv run pytest -q` · `uv run python -m server.replay fixtures/sample_sprint.jsonl`  ·  모드: MOCK

## 현재 목표
- 팀에 계약 3종(`server/events.py`, `server/model/docs.py`, `server/ops/registry.py`) 리뷰 받고 고정 선언
- `docs/ARCHITECTURE.md` 14절 미정 사항 결정 → `notes/TEAM.md` `결정 사항`에 기록

## 최근 결과
| 지표 | 값 | 목표 | 언제 · 모드 | 결과 파일 |
|---|---|---|---|---|
| 스모크 테스트 | 2/2 통과 | 전부 통과 | 11-09 10:15 · MOCK | — |
| 리플레이 8줄 | 라우팅 8, 변경 applied 4 / reverted 1 | 끝까지 동작 | 11-09 10:10 · MOCK | `results/events_replay_*.jsonl` |
| 화면 빌드 | typecheck · build 통과 (브라우저 확인은 아직) | 통과 | 11-09 10:16 | — |

## 진행 중
- [ ] (P0) 계약 3종 팀 리뷰 · 고정 (시작: 10:20)
  - [x] 초안 작성 + TS 사본 `web/src/core/types.ts`
  - [ ] 한서·태우·주현 확인

## 할 일
- [ ] (P0) 14절 결정: 화면 B 확정, 시연 대본, 입장 실패 시 참관 허용, 확대 모드 켜는 방법, 추가 모션 범위
- [ ] (P0) 발표 전 동결 시각 정하기 → `init-collab` §3-6, `notes/TEAM.md`
- [ ] (P0) 브라우저에서 `?fixture=sample_sprint_events` 화면 재생 확인
- [ ] (P0) 첫 커밋 + GitHub 원격 연결

## 다른 영역 관련
- (없음 — 뼈대는 전 파트 초기 작성. 이후 각 폴더는 소유 파트로 넘김)

## 완료
### 2026-11-09
- [x] (P0) `.claude/skills/`에 `init-collab`, `note-tracking` 설치, 설계 문서 → `docs/ARCHITECTURE.md`
- [x] (P0) `CLAUDE.md` 작성
- [x] (P0) 레포 뼈대: `server/` (엔진·변경 수명주기·회의방·입장 관문·빠른 길·Outbox·리플레이·에이전트 MOCK/LIVE), `web/` (store·B 캔버스·입장 화면·STT·손 인식 엔진), `tests/test_smoke.py`
- [x] `notes/TEAM.md` 공용 노트 생성

## 메모
- 프런트 스택은 Vite + React + TS로 잡음 (14절 2번, 문서 권장안).
- `claude-sonnet-5-5`는 forced `tool_choice`가 400 → 에디터·라우터는 `tool_choice: auto` + 프롬프트 지시.
- 남은 빈칸: `server/sync/*.push` (NotImplementedError), 입장 직후 보정, Worker 이전(P1), T자(P2), A/C 화면.
