# Note — 태우 (Mal-Mi-Jal) · 서버·UI 메인

> 마지막 업데이트: 2026-11-09 11:55
> 한 줄 상태: 🟢 진행 중 — 원본 문서 모드(`SEED=google`) 동작: 팀 원본 Sheet/Doc 직접 수정 + 리셋 복원 확인, PR 올림
> 실행: `uv run python -m server.sync.google_auth` · `uv run uvicorn server.app:app --reload --port 8000`  ·  모드: MOCK

## 현재 목표
- PR 리뷰 대기. 예전 별도 탭('스프린트 24 보드', '회의 노트') 정리 여부 확인 → 다음 P0 (STT 실기기 확인 / 입장 화면)

## 최근 결과
| 지표 | 값 | 목표 | 언제 · 모드 | 결과 파일 |
|---|---|---|---|---|
| 원본 문서 모드 실측 | 리스크 추가 Doc 859ms · 결정(섹션 생성) 830ms · 행 추가 Sheet 589ms · 취소 507ms, 리셋 후 원본과 **완전히 같음** | — | 11-09 11:55 · MOCK, 팀 원본 Sheet/Doc | `results/Mal-Mi-Jal_original_backup_1109_1154.json`(원본 백업) |
| 말 → 화면 (대기 포함) | p50 8.0초 / 최대 12.8초 (n=10) | 2.5초 미만 ❌ | 11-09 11:35 · LIVE haiku-5-5 → sonnet-5-5, 대본 1~2초 간격 2회 | `results/Mal-Mi-Jal_replay_live_1109_1140.json`, `_1145.json` |
| 순수 처리 (라우터+에디터+적용) | p50 3.7초 (워밍 후 n=9), 첫 호출 4.9~9.5초 | 2.5초 미만 ❌ (PoC 3.1초) | 같음 | 같음 |
| 첫 발화 라우터 (워밍업 후) | 1213ms (워밍업 자체 3086ms, 백그라운드) | 콜드 스타트 제거 ✅ | 11-09 11:45 · LIVE haiku-5-5 | — |
| 라우터 / 에디터 | p50 1.2초 / 2.2초 | 0.6초 / 1.5초 ❌ | 같음 | 같음 |
| 처리 대기 (앞 발화 기다림) | p50 4.9~6.5초 | — | 같음 | 같음 |
| 테스트 | 24/24 통과 | 전부 통과 | 11-09 11:15 · MOCK | — |
| 말 → 화면 p50 | — | 2.5초 미만 | — | — |
| 말 → 화면 (서버) | p50 3ms / p95 6ms (n=7) | 2.5초 미만 (LIVE 기준) | 11-09 11:31 · MOCK | `results/Mal-Mi-Jal_latency_live_google_1109_1135.json` |
| 말 → Google Doc | p50 548ms / p95 607ms (n=5), 호출 자체 544ms | — | 11-09 11:31 · MOCK, 팀 공용 Doc | 같은 파일 |
| 말 → Google Sheet | p50 440ms / p95 518ms (n=2) | — | 11-09 11:31 · MOCK, 팀 공용 Sheet | 같은 파일 |

## 진행 중
- [ ] (새 기능, 태우 요청) 문서 고르기를 각자 Google 로그인으로 분리 — PR1 (시작: 11-21, 브랜치 Mal-Mi-Jal/user-google-login)
  - 의도와 검증: 입장한 사람이 태우 Drive 목록을 보거나 아무 문서나 원본으로 고르지 못하게. 각자 로그인(drive.file) + Google Picker(본인 파일만, 서버 안 거침), 쓰기는 문서 주인 토큰, 한쪽만 고르면 그 사람 Drive에 새 문서. 기준선: 서버 계정 목록 20개가 누구에게나 보임
  - 문턱: 가짜 Google 시험(옛 원본은 옛 주인 토큰으로 복원 / 새 문서는 새 주인 토큰 / 로그인 없으면 거절 / 목록 API 없음) + 기존 시험 통과(기준선 103 통과, Windows SIGALRM 19 오류 제외). 실제: 다른 Gmail로 Picker에 그 계정 파일만, 바꾸기 6초 안팎(MOCK)
  - 결정(태우): PR1 = 로그인+Picker+한쪽 자동 생성 / PR2 = 바꾸기 요청 → 주인 승인 / PR3 = 엄지 승인 + 저장·저장 안 함. `.env.example`은 팀장 확인 전이라 `server/sync/GOOGLE_SETUP.md`에만 적음
  - [x] GCP: 웹 OAuth 클라이언트, Picker API, API 키, 프로젝트 번호, 테스트 사용자 (태우)
  - [x] 서버: `server/sync/user_auth.py`(code → 토큰, 메모리에만), `google_auth.set_owner/as_owner`(쓰기는 주인 토큰), `source_api` config·login·logout·access·바꾸기, 목록 API·`list_files` 삭제, `google_source.clear_choice`
  - [x] 화면: `DocPicker.tsx` Google 로그인(GIS 코드 팝업) + Google Picker(`drive.file`, setAppId), 안 고른 쪽 = 주인이면 그대로 / 아니면 새로
  - [x] 시험: `tests/test_source_switch.py` 사람마다 가짜 Drive(권한 밖 파일 404) 9개 — 전체 107 통과 (SIGALRM 19 오류는 기준선과 같음). 일부러 '주인 토큰 일찍 켜기' 버그 → 5개 실패로 잡음
  - [x] `server/sync/GOOGLE_SETUP.md` 6절 다시 씀 (6-1 GCP 설정)
  - [x] 실제 확인 1 (태우 계정, MOCK, localhost:8000): 로그인 → Picker로 내 Sheet 불러오기 OK. 처음 `invalid_client` = SECRET 칸에 JSON 파일 이름 → `GOOGLE_OAUTH_CLIENT_FILE`(콘솔 JSON 경로) 지원 추가
  - [x] 구멍 막기: 입장 토큰이 이름만으로 만들어져(`challenge.make_token`) 같은 이름이면 내 Google 로그인을 같이 씀 → 로그인마다 무작위 열쇠 gsid(탭 sessionStorage), 요청마다 이름+gsid 확인. 시험: 같은 이름 다른 사람 401, 동시 바꾸기 둘 → 하나만·하나 409. 일부러 '이름만 보는' 버그 → 시험이 잡음. 전체 110 통과
  - [ ] 다른 Gmail 실제 확인 (태우가 지금 못 함) — 시크릿 창 + 테스트 사용자
  - `.env.example` 변경은 태우가 써 둔 안내 문구(실제 값 아님, 내 착각) → 루트 파일이라 이번 PR에서 뺌
  - PR1엔 승인·저장 없음: 로그인한 누구나 바로 바꿀 수 있고 옛 주인 문서는 회의 전으로 되돌아감 → PR2·PR3
- [ ] (P0 시연) Railway 배포 — 2시까지 (시작: 13:05, 브랜치 Mal-Mi-Jal/railway)
  - 의도와 검증: 회의 서버 하나를 https로 → 팀원·다른 노트북이 같은 회의·원본 문서·마이크. 문턱: /health OK, 원본 로그, 다른 노트북에서 말 → 원본 반영
  - 결정(태우): Railway만 원본(SEED=google), 내 PC 서버는 sprint로 / LIVE
  - [x] `server/deploy/Dockerfile`(화면 빌드 + 서버, requirements는 uv.lock에서 고정 버전 export), `RAILWAY.md`
  - [x] 서버가 화면(web/dist)도 냄, GOOGLE_TOKEN_JSON 변수 → token.json, 종료 신호 때 원본 복원(restore_on_shutdown, 테스트 추가 50/52)
  - railway.exe는 이 PC 보안 정책이 막음 → 대시보드 + GitHub 연결
  - [ ] 태우: 대시보드 프로젝트·변수·도메인 → 배포 로그 확인
- [ ] (새 기능, 태우 요청) 문서 고르기·새로 만들기 (시작: 12:45, 브랜치 Mal-Mi-Jal/doc-picker)
  - 의도와 검증: `.env`·재시작 없이 화면에서 회의 원본 Sheet/Doc을 고르거나 새로 만든다. 문턱: 바꾸기 5초 안, 옛 원본은 백업과 동일하게 복원, 표 있는 문서·머리 행 없는 시트는 거절하고 회의 그대로. 기준선: .env 수정 + 재시작 (1분+)
  - 결정(태우): Drive 목록 권한 추가 → 재로그인 / Sheet·Doc 따로 고르기 / 입장한 누구나 + 확인창
  - [x] 서버: `server/sync/google_files.py`(목록·만들기), `server/sync/source_api.py`(API 3개), google_source load/commit 분리 + 고른 문서 기록(results/), Outbox `run_exclusive`·`hold`
  - [x] 화면: `components/DocPicker.tsx` (캔버스 헤더). 결정 벽(주현)에는 `<DocPicker />` 한 줄 부탁 예정
  - [x] 테스트: 가짜 Google로 바꾸기→옛 원본 복원→새 원본에 쓰기→되돌아오기, 못 쓰는 문서 거절, 새 문서 틀 (5개). 전체 49/51 (Windows 권한 2개 제외)
  - [x] 태우 재로그인 (Drive 목록 권한 받음)
  - [x] 실제 Google(MOCK): 새로 만들기로 바꾸기 6.0초, 말 → 새 Doc 리스크에 기록, 원본으로 돌아오기 4.2초, 새 Doc은 틀 그대로 복원, 팀 원본 백업과 동일
  - [ ] 목록: GCP 프로젝트에 Google Drive API가 꺼져 있음 (403) → 태우가 콘솔에서 사용 설정 후 재확인
  - 테스트로 만든 '[테스트] 문서 고르기 — 보드 / 회의 노트'가 태우 Drive에 남음 (지우기 권한 없음 → 직접 삭제)
- [ ] (P0) STT 실제 마이크 확인 (시작: 12:05, 브랜치 Mal-Mi-Jal/stt-check)
  - [x] 오류 뒤 재시작 늦추기(0.5→4초, 5번 연속 실패면 멈춤), interim은 바뀔 때만·최대 4번/초 로그에 보냄, 오류 문구 한국어
  - [x] 지연 지표 `stt_interim_to_final` 추가 (첫 interim → final). 테스트 15/15 (SEED=sprint)
  - [x] 1차 실제 확인(MOCK, 11:55 서버): 재시작 OK. 'PAY-423 추정' → '회의사이삼 수정'으로 받아씀. 말 끝 → final 대부분 1초, 가끔 3.5·5초. final 안 와서 한 문장 사라짐
  - [x] 보정: `capture/normalize.ts` 보드에 있는 키와 번호가 맞으면 '페이사이삼'·'사백이십삼' → PAY-423 (node 14케이스)
  - [x] early final: interim이 1.2초 그대로면 먼저 final, 늦은 Chrome final은 중복 안 보냄, 끊길 때 들은 데까지 보냄 (가짜 인식기 6케이스)
  - [x] 지표 `stt_endpoint` (마지막 interim → final). 1차 측정 p50 2.0초 (early final 전)
  - [x] 2차 실제 확인(12:28 서버): **버그** '경쟁 서비스 분석 일주일만 미뤄 줘' → '줘'만 보냄. Chrome이 말하는 중인 문장을 여러 결과 칸으로 쪼개 주는데 early final이 마지막 칸만 봄
  - [x] 고침: Chrome final 전인 칸 전부를 이어 한 덩어리로 처리 (가짜 인식기, Chrome식 쪼갠 결과 7케이스)
  - [ ] 3차 실제 확인 → PR
- [x] (P0) 원본 문서 직접 쓰기 — #11 merge됨 (시작: 11:48, 사용자 결정: 원본 읽기·원본 쓰기 / 리셋=회의 전 복원 / 결정·액션 섹션은 처음 기록 때 끝에 추가)
  - [x] `server/sync/google_source.py` 원본 → DocState (시트1 23행×14열, Tab 1 목표·범위·마일스톤·리스크)
  - [x] Sheets 원본 칸 단위 쓰기 (값·메모·하이라이트, 행 추가·삭제), 기존 칸 서식 보존
  - [x] Docs 원본 문단 단위 쓰기 (삽입·수정·삭제, '· 누가' 회색, 없는 섹션은 끝에 추가)
  - [x] 리셋 = 회의 중 변경 역순 되돌리기 + 추가한 섹션 제거
  - [x] 바로가기 링크를 원본 탭으로
- [ ] (P0) 지연 측정 (시작: 14:30)
  - [x] `server/common/event_latency.py` 이벤트 로그 → 단계별·전체 지연 (CLI 포함)
  - [x] `server/replay.py` 요약 · `/api/stats`에 연결 (mode, vs_goal 포함)
  - [x] MOCK 리플레이 숫자 / 실서버 숫자 (Google 포함)
  - [x] LIVE 리플레이 2회 (사용자 승인)
  - [x] `queue_wait` / `proc_to_applied` 분리
  - [x] Docs 동기화 조회 1회 줄이기 (탭 길이 캐시): 1286ms → 544ms
- [x] (P0) 회의 화면 텍스트 발화 입력창 + STT 상태 표시 — PR #6 merge
  - [x] `web/src/capture/stt.ts` 상태 콜백(듣는 중/권한 거부/미지원/오류), 언어 ko-KR 기본
  - [x] `web/src/views/canvas/CanvasView.tsx` 입력창 (Enter 전송, 연결 끊김 안내) + `core/ws.ts` `send()`가 성공 여부 반환 + `styles.css`
  - [x] typecheck · build 통과 (13:00)
  - [x] 브라우저에서 입력창으로 발화 → 추가 확인 (사용자, 13:10)
- [x] (P0) 화면 상단 Google Sheet/Doc 바로가기 — `/api/links`(입장 토큰 필요, Google 새 호출 없음), `web/src/components/DocLinks.tsx`. Sheet는 보드 탭(gid)으로 열림. Doc은 동기화 구현 전이라 '준비 중'
- [ ] (P0) Google 인증 세팅 (시작: 10:30)
  - [x] PoC OAuth 클라이언트 `credentials.json` 루트로 복사 (PoC `token.json`은 계정 불명이라 안 가져옴)
  - [x] 의존성 추가: google-api-python-client, google-auth-oauthlib, google-auth-httplib2 (`pyproject.toml`, `uv.lock`)
  - [x] `server/sync/google_auth.py` — 로그인·토큰 갱신·서비스 생성·접근 확인 CLI
  - [x] `server/sync/GOOGLE_SETUP.md` — 팀원용 안내
  - [x] `.env` 생성 (`.env.example` 복사, MOCK)
  - [x] 브라우저 로그인 → `token.json` 생성 (10:45)
  - [ ] 팀원 문서 공유받아 접근 확인
  - [ ] 팀원 Gmail 테스트 사용자 등록 여부 확인 (GCP 관리자)

## 할 일
- [ ] (P0) 회의방+WS / Op 엔진 / 리플레이 — 실제 흐름에서 점검

## 다른 영역 관련
- [ ] LIVE 에디터 op 선택 — '불안정한 결제 테스트 티켓 하나 추가해 줘'가 add_row(보드) 대신 create_ticket(Linear)로 감 → 보드에 안 보임. 제목 뽑기는 잘 됨('불안정한 결제 테스트') → 77SONNY77 (상태: PR 설명에 적음)
- [ ] LIVE 지연 목표 미달 공유: 라우터 1.2초·에디터 2.2초, 첫 호출 콜드 스타트 3.5~8초 → 77SONNY77, gitgutgit (상태: PR 설명에 적음)
- [x] `server/agent/editor.py` `_mock_edit` — (LIVE에선 제목 잘 뽑힘, MOCK만 해당) MOCK에서 '캐시 티켓 추가해줘'가 add_row 제목에 발화 원문 그대로 들어감 → 77SONNY77 (상태: 요청 전. LIVE 에디터면 제목을 뽑아 줄 것으로 예상, 확인 필요)
- [x] `tests/test_google_sheets.py`, `tests/conftest.py` 새 파일 추가 (tests/는 소유 표에 없음, 새 파일만) → gitgutgit 알림 (상태: PR #1 설명에 적음)
- [x] `pyproject.toml`, `uv.lock` — Google 의존성 3개 **추가** (init-collab §2: 추가는 알리기만) → gitgutgit 알림 (상태: PR #1 설명에 적음)

## 완료
### 2026-11-09
- [x] (11:55) 원본 문서 모드 `SEED=google` — `server/sync/google_source.py`(불러오기·칸/문단 단위 쓰기·복원), `google_sheets`/`google_docs` 위임, `outbox.enqueue_restore`, `app.py` 시작·리셋·링크, `room.py`, `replay.py --seed`. `tests/test_google_source.py` 7개 (가짜 Docs가 '서식은 줄바꿈에 붙음' 규칙대로 동작)
- [x] (11:45) 서버 시작·`/api/reset` 때 LIVE LLM 워밍업 — `server/common/warmup.py`, `server/app.py`. 첫 발화 라우터 3.5~8초 → 1.2초 (LIVE). PR #9 merge됨
- [x] (P1) Google Docs 동기화 — `server/sync/google_docs.py`: Doc 안 전용 탭 '회의 노트'(addDocumentTab)만 미러링, 기존 탭 안 건드림. 제목2·글머리·변경 항목 노랑·'· 누가' 회색. `tests/test_google_docs.py` 3개. 화면 📝 버튼은 전용 탭으로 바로 열림
- [x] 팀 공용 Sheet/Doc으로 `.env` 교체 (편집 권한 확인). Sheet는 별도 탭 '스프린트 24 보드'에만 씀
- [x] (P0) B 화면 보드·노트 탭 브라우저 확인 (사용자 확인: 잘 뜸, 12:45). 카메라·마이크는 테스트 환경 없어 미확인
- [x] (P0) cloudflared quick tunnel → web(5173, /api·/ws 프록시) https 접속 확인: 페이지 200, 입장 pass, wss snapshot → 발화 → change.applied (MOCK). 주소는 `results/tunnel_url.txt`(gitignore)에만
- [x] PR #1 main merge (12:20)
- [x] 로컬 폴더를 `gitgutgit/LostAI`에 연결, 브랜치 `Mal-Mi-Jal/sheets-sync` 커밋 4개 → PR #1 (리뷰어 ProfessionalSeaweedDevourer)
- [x] (P0) 서버 시작·`/api/reset` 때 Outbox로 전체 미러링 (`outbox.enqueue_full_sync`, `app.py`) — 첫 발화 동기화 1849ms → 445ms (MOCK). `tests/conftest.py`로 테스트가 실제 Google에 안 쓰게 막음
- [x] (P0) Google Sheets `push` 구현 — `server/sync/google_sheets.py` (탭 통째 미러링 batchUpdate 1회, 셀 메모=출처, 이번 변경 노란색), `tests/test_google_sheets.py` 4개. 발화 → `change.applied` → `sync.ok` 1849ms, 취소 → `change.reverted` → `sync.ok` 505ms (MOCK)
- [x] `notes/Mal-Mi-Jal.md` 생성

## 메모
- 12:21 PR #11을 main(#8 room.reset 구조)으로 rebase. reset 흐름: room.reset()이 멈춘 뒤의 옛 변경 반환 → enqueue_restore(같은 방) → full_sync → warmup. 복원 sync 이벤트는 utt_id 지움(새 회의 u1과 안 섞이게). 실제 팀 문서: 변경 4개 → 리셋 → 백업과 동일 (Doc·Sheet)
- 주의: 원본 모드에서 서버를 리셋 없이 끄면 회의 중 변경이 원본에 남고, 다음 시작 때 그게 원본으로 읽힌다 (12:05~12:15 STT 테스트 한 줄이 남아 손으로 지움)
- tests/test_server_robustness.py는 Windows에서 SIGALRM 없음 → shim으로 돌림, join_secret 0600 권한 테스트 2개는 Windows라 실패 (main과 같음)
- 이 PC: uv는 `python -m uv`로 실행 (pip --user 설치, PATH에 없음). `pytest.exe`는 Windows 앱 제어 정책에 막힘 → `uv run python -m pytest`
- 환경변수 `GOOGLE_CREDENTIALS` / `GOOGLE_TOKEN`으로 파일 경로를 바꿀 수 있음 (선택, `.env.example`에는 안 넣음 — 루트 파일이라 승인 필요)
- 개발용 Sheet `[meeting-agent] dev sync test (Mal-Mi-Jal)`를 내 Drive에 만들어 `.env` GOOGLE_SHEET_ID에 연결함 (ID는 기록 안 함)
- 동기화 방식: diff 단위 부분 수정 대신 탭 통째 미러링 — Outbox가 늦어도 최신 state로 덮으니 행 추가·삭제·되돌림 순서가 안 꼬임. 행 수가 수백 개 넘으면 다시 볼 것
- 전체 동기화도 Outbox 큐로만 보냄 (app.py에서 직접 Google 호출 금지 → 동시 호출 규칙 유지). payload는 기존 `{target, ms}` 그대로라 계약 변경 없음
- 이전 스모크 테스트는 `.env`의 GOOGLE_SHEET_ID 때문에 실제 Sheet에 쓰고 있었음 → conftest로 수정
- 이 레포 git 작성자: repo-local `Mal-Mi-Jal` + GitHub noreply 이메일 (전역 `namwoo0303`은 안 건드림). gh는 `C:\Program Files\GitHub CLI\gh.exe`
- 이 PC는 Smart App Control On → rollup 네이티브 차단. `npm install --no-save "rollup@npm:@rollup/wasm-node@4.68.0"`로 node_modules만 우회 (package.json 안 바꿈. `npm ci` 다시 하면 재적용 필요). Node는 `C:\Program Files
odejs`
- 터널 띄우기: 서버 `uv run python -m uvicorn server.app:app --port 8000` → web `npx vite --host 0.0.0.0` → `"C:/Program Files (x86)/cloudflared/cloudflared.exe" tunnel --url http://localhost:5173`. quick tunnel은 재시작마다 주소 바뀜
- STT 기본 언어 en-US → ko-KR로 바꿈 (시드가 한국어). `?lang=en-US`로 변경 가능. 영어 시연이면 URL에 붙일 것
- 고친 버그: Room/Outbox 워커가 첫 이벤트 루프에 묶여 TestClient를 두 번 띄우면 두 번째 발화가 멈춤 → `start()`에서 루프가 다르면 다시 만듦 (실서버 영향 없음)
- JOIN_SECRET이 비어 있으면 서버 프로세스마다 토큰 키가 달라짐 → 서버 재시작하면 기존 화면은 다시 입장해야 함
- 팀 공용 Sheet/Doc은 기존 PoC A 내용(WBS, 프로젝트 계획)이 있음 → 우리는 전용 탭에만 쓰고 기존 탭(`시트1`, `Tab 1`)은 안 건드림. 테스트 후 `/api/reset`으로 원상복구함
- ⚠️ 이 노트의 11-09 10:40 ~ 14:30 시각 표기는 실제 시계를 안 보고 적은 추정값이라 틀림 (실제로는 10:26 ~ 11:29 사이 작업). 11:31부터는 `date` 확인 시각
- 회의방 시계 `time.monotonic` → `time.perf_counter` (Windows monotonic 해상도 15.6ms라 지연이 0/16/31ms로만 찍혔음). 이전 로그의 utt_to_* 숫자는 15ms 단위로 부정확
- 리플레이를 `--realtime` 없이 돌리면 발화가 한꺼번에 들어가 앞 발화 대기 시간이 utt_to_*에 섞임 → 지연 숫자는 `--realtime`으로
- 11:35 LIVE 측정: 대본 간격(1~2초)보다 처리(3~4초)가 길어서 뒤 발화가 계속 밀림 → 말 → 화면이 대기 때문에 8초. 실제 회의 간격이 더 길면 줄겠지만 시연 대본 간격을 정할 때 고려
- 11:55 Docs 규칙: 문단 서식은 그 문단 끝 줄바꿈에 붙어 있음 → 마지막 문단을 지우려고 앞 줄바꿈을 지우면 앞 문단이 지운 문단 서식을 받음. `_del_range_to_end`에서 앞 문단 서식을 다시 줌
- `.env` SEED=google로 바꿈 (로컬). `.env.example`은 루트 파일이라 안 바꿈 → 안내는 `server/sync/GOOGLE_SETUP.md` 5절
