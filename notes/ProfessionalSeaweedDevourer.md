# Note: 주현 (ProfessionalSeaweedDevourer), 기능 서브, 서버 UI 서브

> 마지막 업데이트: 2026-11-09 12:50
> 한 줄 상태: 🟢 진행 중: 입장 화면과 입장 뒤 회의 화면이 모두 창 전체를 차지하는 렌더 v0.4 무대가 됐다(벽 밖 조작 띠 없음). 서버 상태 대 화면 27/27 유지
> 실행: `uv run pytest -q`, `uv run python -m server.replay fixtures/sample_sprint.jsonl`, 모드: MOCK

## 현재 목표
- [서버 UI] 렌더 v0.4를 픽셀 그대로 옮긴 결정 벽 화면, 그다음 같은 화면을 실제 이벤트 로그로 움직이게.
- 남은 판정: 시안의 벽 색(#CDD6D0, 회색빛 초록)이 '회색 배경' 피드백에 걸린다. 색 토큰 하나만 바꾸면 되도록 둠, Eric 판정 대기.

## 최근 결과
| 지표 | 값 | 목표 | 언제, 모드 | 결과 파일 |
|---|---|---|---|---|
| 전체 화면: 창 크기 4종 x 화면 2종(입장, 회의) | 8/8: 무대가 창 한 변을 꽉 채움, 남는 띠 벽색 아닌 화소 0, 벽 밖 보이는 요소 0 | 전부 | 11-09 11:30, MOCK 8001 | 판정 스크립트 shots.py는 로컬 임시 폴더 |
| 1인 회의 리허설 `tests/test_one_person.py` | 계약 이벤트 25종 중 20종 실제 발생, 제외 4(Google 동기화 3, 지연 반영 버림 1), 빈칸 1(participant.rejected를 서버가 안 냄). 전체 시험 8/8, 6초 | 제외 말고 전부 | 11-09 12:05, MOCK | `uv run pytest -q` |
| 말로 여는 질문 카드와 표결(MOCK 흐름 7단계) | 질문 카드 열림, '투표하죠'로 표결 열림, 말로 3표, 마감 뒤 결과 화면, 노트 문서 표, 긴 답 3줄 자르기 모두 확인 | 전부 | 11-09 11:52, MOCK 8001 | 로컬 임시 폴더 vote.py |
| 실시간 결정 벽: 서버 상태 대 화면 DOM | 27/27 일치 | 전부 | 11-09 11:52 재측정(표결, 노트 표 추가 뒤), MOCK 서버 발화 6줄 | 판정 도구 meeting-agent-poc/design/tools/wall_judge |
| 결정 벽 대 렌더 v0.4 픽셀 대조 (장면 11 x 질문 띠 켬, 끔) | 22/22 통과, 다른 화소 0개, 평균 차이 0.000 | 프레임마다 0.5% 이하 | 11-09 10:47, 1920x1080 headless Chrome | 대조 도구는 로컬 임시 폴더(아직 리포 밖) |
| 스모크 테스트 | 2/2 통과 | 전부 통과 | 11-09 10:24, MOCK | 없음 |
| 리플레이 8줄 | applied 4, reverted 1 | 끝까지 동작 | 11-09 10:24, MOCK | `results/events_replay_1109_102454.jsonl` |
| 화면 빌드 | typecheck, build 통과 (288 kB) | 통과 | 11-09 10:25 | 없음 |
| 실서버 WS 발화 6줄 | applied 1, reverted 1, failed 1, 변경 없음 3 | 없음 | 11-09 10:25, MOCK | `results/events_main_1109_102520.jsonl` |

## 진행 중
- [ ] [서버 UI] (P0) 결정 벽 화면 = 렌더 v0.4 그대로 (시작: 10:38, 브랜치 `ProfessionalSeaweedDevourer/minutes-card`)
  - [x] 시안 CSS 원문 이식 `web/src/views/wall/wall.css`, 뷰 모델 `types.ts`, 무대 `Wall.tsx`, 장면 11개 `scenes.ts`, 화면 `WallView.tsx`
  - [x] `?view=wall`이면 공용 styles.css를 싣지 않게 `web/src/main.tsx` 분기
  - [x] 앞 개편(회의록 카드, 남색 벽) 되돌림: CanvasView, SheetView, DocView, ChangeCard, styles.css 원래대로, MinutesCard/MinutesFull 삭제
  - [x] 판정: 22장 모두 다른 화소 0개 (첫 측정 최대 0.014%: React가 글을 여러 텍스트 노드로 쪼개 글자 모양이 달라짐, 한 문자열로 합쳐 0)
  - [x] 실시간: 회의방(RoomView) → WallState 변환 `web/src/views/wall/live.ts`, 입장 뒤 화면 `LiveWallView.tsx`(마이크, 회의록 전문, 손 공유 신호), `App.tsx` 입장 뒤 기본 화면을 결정 벽으로(`?ui=canvas`면 예전 화면), 개발 서버 전용 `?as=이름` 수동 입장
  - [x] 판정: MOCK 서버에 발화 6줄 → 서버 /api/state 대 화면 DOM 칸 단위 27/27 일치(행 수, 칸 값, 출처 칩, 마지막 발화, 쓴 횟수). 장면 22장 픽셀 대조도 그대로 0
  - [x] 원격 main(PR #3 입장 손동작 UI, PR #5 팀 스킬) 로컬로 합침, 충돌 없음 (11:24)
  - [x] 전체 화면(Eric 11:23 지시): 무대를 창에 맞춰 키우고 남는 띠는 벽색(`FitStage.tsx`), 아래 조작 띠 삭제. 마이크는 오른쪽 위 표지(누르거나 M 키), 회의록 전문은 Log 상자를 누르면 열림, F 키 브라우저 전체 화면. 실화면 전용 규칙은 `#stage.live`로만 걸어 장면 화소 불변
  - [x] 입장 화면(e951d08, 77SONNY77 작업)에 렌더 v0.4 규약 적용: 같은 무대, 왼쪽 큰 카드 = 카메라, 오른쪽 카드 = 이름 또는 손동작, 진행 칸은 Q 슬롯 모양. 판정 로직(타이머, 단계, 수동 입장)은 그대로 `web/src/views/join/join.css` → 77SONNY77, Mal-Mi-Jal에게 알림 필요
  - [x] 임시 채팅(Eric 11:32 제안): 마이크 없이 시험하도록 실화면에서 Enter 또는 발화 줄을 누르면 그 자리가 입력칸, Enter로 utterance.final 송신, Esc로 닫힘. MOCK 확인: 친 줄이 Eric L1 출처로 표에 들어가고 잡담은 무시됨. 27/27, 22/22 유지
  - [x] Eric 11:40 지적 4건: (1) 고르기 질문이 ask로 가 답만 하고 '투표하죠'는 ignore → 라우터, 에디터 프롬프트에 고르기 질문과 표결 부르기 = open_conflict, 파이프라인에서 열린 질문이 있으면 표결 부르기로 바로 vote.opened, 표결 중 '2번'은 한 표, 말로 연 표결은 20초 무응답이면 마감(`server/agent/*`, `server/gestures/votes.py`, 기능 서브). MOCK 규칙도 같게 (2) 긴 ASK 답이 카드 밖으로 → 28px 세 줄 말줄임, Asker 답 60자 이내 지시 (3) 노트 문서(액션, 결정, 리스크) 변경이 벽에 안 보임 → 문서 칸이 마지막으로 고친 문서를 따라감 (4) 'a here' = 입장 때 이름 'a'로 들어온 참가자. 덧붙여 실화면이 손 신호를 서버로 안 보내던 것 고침, 첫 표결 결과 화면 문구(재투표용 'Revote' 대신 질문, 이긴 선택지, 표 수)
  - [x] 1인 시험(Eric 11:44 /be-ambitious, 목표: 개발자 한 명이 제품 모든 요소를 시험): 개발 서버 화면 채팅에서 'Ines: 줄'은 Ines로 수동 입장한 소켓으로 말하고, '/up' '/down' '/1'..'/5' '/t'는 카메라 없이 손 신호(`web/src/views/wall/puppets.ts`). 벽 표지에 MOCK, LIVE 표시(`/api/stats`의 mode, `server/app.py` 서버 서브). 브라우저 확인: 네 사람 발화, 엄지 승인, 표결 열기, 손가락과 말로 3표, 마감까지 전부 서버에 들어감
  - [x] `tests/test_one_person.py`: 같은 방식으로 회의 전 과정을 몰고 계약 이벤트 종류 커버리지를 판정. 남은 회의방이 다음 시험을 멈추게 하던 것도 처리(끝에 회의방 제거)
  - [x] 실제 Google 문서 내용으로 칸 넘침 + 노트 수정 뒤 보드가 사라짐(Eric 12:31 화면, 팀원 12:36 화면). 의도와 검증: 긴 한국어 제목, 문장, 이름이 와도 모든 칸이 제자리에 머물고 보드는 늘 메인 / 판단 밖 검증 = 긴 한국어 상태 4장면을 headless Chrome에 주입해 칸 밖 글자 수와 말없이 잘린 칸 수를 DOM으로 셈, 문턱 0 / 기준선(수정 전) 넘침 2, 1, 1, 4와 잘림 3, 3, 22, 22, 노트 수정 장면에서 보드 행 0 → 수정 뒤 전부 0, 보드 5행 + 고친 노트 1행. 고친 것: 문서 칸 주인은 시트이고 이번 회의에서 고친 노트 항목만 보드 아래에 덧붙임(시트 없는 방이면 노트 문서 전체), 열 폭을 글자에 맞추되 넘치면 넓은 열부터 깎음(작업 열 최소 360px), 머리줄 제목, Last 줄, 칸, 선택지, 참가자 이름은 칸 안에서 말줄임, 작업 열은 두 줄까지(`live.ts`, `wall.css`의 `#stage.live` 규칙만). 남은 것: 행이 종이 높이를 넘으면 아래 행은 종이 안에서 잘림(넘치진 않음), 방금 고친 행으로 스크롤은 없음
  - [ ] 표결 결과로 질문을 닫기(resolve_conflict)는 아직 없음: 결과 화면 뒤에도 '0 of 1 decided'
  - [ ] 입장 뒤 기본 화면 변경은 Mal-Mi-Jal(서버 UI 메인) 확인 필요
- [ ] [기능][서버 UI] (P0) 아래 결함 2건 담당자에게 전달 (시작: 10:30)

## 할 일
- [ ] (P1, Eric 12:08 다음 목표) '티켓 열자'처럼 말하면 번호를 지정하지 않아도 바로 새 티켓 행 추가(번호는 서버가 매김)
- [ ] (P1, Eric 12:08 다음 목표) 지금 회의 상태에서 시험하기 좋은 시나리오와 상황 선택지를 화면에 함께 제시해 시험 효율 올리기(1인 시험 채팅과 연결)
- [ ] (P1) 표결 결과로 질문 닫기(resolve_conflict). 지금은 결과 화면 뒤에도 '0 of 1 decided'
- [ ] (P0) 데모 기획(120초 판)과 이 리포 P0, P1, P2 대조

## 다른 영역 관련
- [ ] `server/app.py` join_step: 입장 3회 실패 때 participant.rejected 이벤트를 내지 않음(계약에는 있음). 1인 리허설 시험의 알려진 빈칸 → Mal-Mi-Jal (상태: 미전달)
- [ ] `server/model/seeds/sprint.json` 또는 `server/agent/editor.py`: MOCK 기본 op `add_note`가 binding `notes` 섹션을 찾는데 sprint 시드에 그 섹션이 없어 매번 `change.failed` → gitgutgit(시드), 77SONNY77(에디터) (상태: 미전달)
- [x] `web/src/App.tsx`: 개발 서버(StrictMode)에서 fixture 재생이 두 번 돌던 것, 한 번만 시작하게 고침(내 서브 파트) → Mal-Mi-Jal에게 알림 필요

## 완료
### 2026-11-09
- [x] (P0) 리포 받기, `uv sync`, `npm install`, `.env`(MOCK) 만들기, 시험, 리플레이, 실서버, 화면 실행 확인

## 메모
- 11-09 12:30 PR 초안 둘: #15 음성 표결과 1인 리허설 시험(기능), #16 UI 전체를 결정 벽으로 교체(입장, 회의, 전체 화면, 1인 시험). 둘은 서로 독립. ready는 Eric 검토 뒤.
- 11-09 11:50 이후 기준 변경: `server/agent/prompts.py` 라우터(고르기 질문, 표결 부르기 = capture), 에디터(open_conflict 규칙), Asker(답 60자 이내). 라우터 정확도와 지연 숫자는 이 시각 전후 비교 불가 → 77SONNY77에게 알림 필요.
- `/api/reset`이 표결 상태(`server/gestures/votes.py` 전역 votes)를 지우지 않는다. 표결 중 초기화하면 마감 타이머가 옛 방에 vote.closed를 낸다(서버 파트 app.py, Mal-Mi-Jal).
- 11-09 11:03 로컬 브랜치에 원격 main(태우 Sheets 동기화 PR #1 포함)을 로컬로만 합침. 충돌은 협업 규칙 표 두 줄(각자 git 이름) 뿐, 둘 다 살림. 시험 7/7, 빌드 통과, 결정 벽 픽셀 대조 22/22 다른 화소 0. push 안 함(원격 반영은 PR과 수동 검수).
- (10:38 되돌림) 11-09 10:30 이후 B 화면 기준 변경: 오른쪽 타임라인을 회의록 카드로 바꿈. 카드를 누르거나 `?minutes=1`이면 전문. 벽 색은 기본 남색, `?wall=green`이면 초록. 회색 배경은 쓰지 않음(피드백).
- 서버가 묻기 뒤에 done 단계를 안 낸다(`server/agent/pipeline.py`, 기능 파트). 화면에서는 답이나 변경 결과가 더 늦게 오면 대기로 보이게 처리(`AgentStatus.tsx`). 서버 쪽은 77SONNY77에게 알릴 것.
- 녹화 fixture의 발화 시각이 전부 0초라 회의록 시각이 00:00으로만 보인다. 실제 회의나 새 녹화에서 다시 볼 것.
- `npm install`이 `web/package-lock.json`을 39줄 줄였다(Node 23.11). 되돌려 둠. 팀 Node 판이 다르면 lock 충돌 가능.
- 서버 통계 경로는 `/stats`가 아니라 `/api/stats` (CLAUDE.md 표기와 다름).
