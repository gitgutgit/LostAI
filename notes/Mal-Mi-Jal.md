# Note — 태우 (Mal-Mi-Jal) · 서버·UI 메인

> 마지막 업데이트: 2026-11-09 12:20
> 한 줄 상태: 🟢 진행 중 — PR #1 merge 완료, `Mal-Mi-Jal/canvas-view`에서 B 화면 확인 + https 터널 시작
> 실행: `uv run python -m server.sync.google_auth` · `uv run uvicorn server.app:app --reload --port 8000`  ·  모드: MOCK

## 현재 목표
- B 화면 보드·노트 탭을 브라우저에서 실제 서버로 확인 → cloudflared https 터널로 팀원 카메라·마이크 접속

## 최근 결과
| 지표 | 값 | 목표 | 언제 · 모드 | 결과 파일 |
|---|---|---|---|---|
| 테스트 | 7/7 통과 (스모크 2 + Sheets 5) | 전부 통과 | 11-09 11:15 · MOCK | — |
| 말 → 화면 p50 | — | 2.5초 미만 | — | — |
| Google Sheets 동기화 | 시작 전체 1698ms(백그라운드) · 첫 발화 445ms · 리셋 529ms, 모두 sync.ok | — | 11-09 11:38 · MOCK, 개발용 Sheet | — |

## 진행 중
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
- [ ] (P0) 개발용 Sheet → 팀 공용 시연 Sheet로 교체 (`google_auth --sheet <URL> --save`)
- [ ] (P0) B 화면 보드·노트 탭 — 브라우저에서 fixture 재생 확인
- [ ] (P0) Web Speech STT `web/src/capture/stt.ts`
- [ ] (P0) 회의방+WS / Op 엔진 / 리플레이 — 실제 흐름에서 점검

## 다른 영역 관련
- [x] `tests/test_google_sheets.py`, `tests/conftest.py` 새 파일 추가 (tests/는 소유 표에 없음, 새 파일만) → gitgutgit 알림 (상태: PR #1 설명에 적음)
- [x] `pyproject.toml`, `uv.lock` — Google 의존성 3개 **추가** (init-collab §2: 추가는 알리기만) → gitgutgit 알림 (상태: PR #1 설명에 적음)

## 완료
### 2026-11-09
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
