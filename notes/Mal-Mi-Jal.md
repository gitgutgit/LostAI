# Note — 태우 (Mal-Mi-Jal) · 서버·UI 메인

> 마지막 업데이트: 2026-11-09 14:00
> 한 줄 상태: 🟢 진행 중 — Google Docs 동기화 동작 + 팀 공용 Sheet/Doc 연결, PR #2 올림
> 실행: `uv run python -m server.sync.google_auth` · `uv run uvicorn server.app:app --reload --port 8000`  ·  모드: MOCK

## 현재 목표
- PR #2 리뷰·merge → 지연 측정(리플레이 → `/api/stats`). Docs 동기화 1.3초 → 탭 길이 캐시로 조회 1회 줄이기

## 최근 결과
| 지표 | 값 | 목표 | 언제 · 모드 | 결과 파일 |
|---|---|---|---|---|
| 테스트 | 11/11 통과 | 전부 통과 | 11-09 11:15 · MOCK | — |
| 말 → 화면 p50 | — | 2.5초 미만 | — | — |
| Google Docs 동기화 | 시작 1867ms · 결정 추가 1286ms, sync.ok | — | 11-09 13:55 · MOCK, 팀 공용 Doc(전용 탭) | — |
| Google Sheets 동기화 | 시작 2203ms · 행 추가 448ms · 취소 393ms, sync.ok | — | 11-09 13:55 · MOCK, 팀 공용 Sheet(별도 탭) | — |

## 진행 중
- [ ] (P0) 회의 화면 텍스트 발화 입력창 + STT 상태 표시 (시작: 12:50)
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
- [ ] (P0) Web Speech STT `web/src/capture/stt.ts`
- [ ] (P0) 회의방+WS / Op 엔진 / 리플레이 — 실제 흐름에서 점검

## 다른 영역 관련
- [ ] `server/agent/editor.py` `_mock_edit` — MOCK에서 '캐시 티켓 추가해줘'가 add_row 제목에 발화 원문 그대로 들어감 → 77SONNY77 (상태: 요청 전. LIVE 에디터면 제목을 뽑아 줄 것으로 예상, 확인 필요)
- [x] `tests/test_google_sheets.py`, `tests/conftest.py` 새 파일 추가 (tests/는 소유 표에 없음, 새 파일만) → gitgutgit 알림 (상태: PR #1 설명에 적음)
- [x] `pyproject.toml`, `uv.lock` — Google 의존성 3개 **추가** (init-collab §2: 추가는 알리기만) → gitgutgit 알림 (상태: PR #1 설명에 적음)

## 완료
### 2026-11-09
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
