# Google Sheets / Docs 연결 (본선 레포)

> 관리: 태우 (Mal-Mi-Jal) · 서버·UI. PoC `GOOGLE_SETUP.md`를 본선용으로 줄인 것.
> 코드: `server/sync/google_auth.py`

## 파일 · 값

| 파일 / 값 | 무엇 | 공유 |
|---|---|---|
| `credentials.json` (루트) | GCP 프로젝트의 OAuth 클라이언트 (데스크톱 앱) | 팀 안에서 DM으로만. git·공개 채널 금지 |
| `token.json` (루트) | **내 Google 계정** 로그인 결과. 처음 실행 시 자동 생성 | ❌ 절대 공유 금지 |
| `.env` `GOOGLE_SHEET_ID` / `GOOGLE_DOC_ID` | 서버가 동기화할 문서. 비우면 동기화 꺼짐 | note·커밋·채팅에 적지 않음 |

셋 다 `.gitignore`에 있다. 커밋되지 않는 게 정상이다.

## 1. 처음 한 번 (각자)

1. **테스트 사용자 등록**: 앱이 테스트(Testing) 상태라 GCP 프로젝트 관리자가 내 Gmail을
   *OAuth 동의 화면 → 대상 → 테스트 사용자*에 넣어 줘야 한다. 없으면 `403: access_denied`.
2. **`credentials.json`** 을 관리자에게 DM으로 받아 레포 루트에 둔다. (PoC와 같은 클라이언트를 재사용)
3. 로그인:
   ```bash
   uv sync
   uv run python -m server.sync.google_auth
   ```
   브라우저가 열리면 테스트 사용자 계정으로 로그인 → "확인되지 않은 앱" 경고는 **고급 → 이동** → 허용.
   루트에 `token.json`이 생기면 끝.

## 2. 다른 사람 문서에 접속하기

문서는 **로그인한 계정 권한**으로 열린다. `credentials.json`이 같아도 문서 권한은 계정마다 따로다.

1. 문서 주인이 Google Drive에서 **공유 → 내 Gmail을 편집자로** 추가한다.
2. 접근 확인 후 `.env`에 저장:
   ```bash
   uv run python -m server.sync.google_auth --sheet "<Sheet URL>" --doc "<Doc URL>" --save
   ```
   ✅ 제목이 나오면 접근 가능. `--save`는 성공했을 때만 `.env`에 ID를 쓴다 (ID는 화면에 안 나옴).
3. 이후 `.env`에 들어간 문서만 확인: `uv run python -m server.sync.google_auth`

## 3. 자주 나는 에러

| 에러 | 원인 | 해결 |
|---|---|---|
| `403: access_denied` (앱이 테스트 중) | 내 Gmail이 테스트 사용자가 아님 | 관리자에게 등록 요청 |
| `❌ 권한 없음` | 문서가 나에게 공유 안 됨 | 문서 주인에게 편집자 공유 요청 |
| `❌ 문서를 찾을 수 없음` | ID/URL 오타, 또는 삭제된 문서 | URL 다시 복사 |
| `API가 꺼져 있음` | GCP 프로젝트에서 Sheets/Docs API 미사용 | 관리자가 API 사용 설정 |
| `invalid_grant` / 토큰 만료 | 테스트 모드 토큰은 약 7일 뒤 만료 | 자동으로 다시 로그인함. 안 되면 `--relogin` |
| `redirect_uri_mismatch` | 클라이언트 유형이 데스크톱 앱이 아님 | 데스크톱 앱 클라이언트로 다시 발급 |

## 4. 서버에서 쓰기

`google_sheets.py` / `google_docs.py`는 `google_auth.service("sheets", "v4")`, `service("docs", "v1")`로
클라이언트를 받는다. 서버 안에서는 브라우저 로그인을 띄우지 않는다(`interactive=False`) → 토큰이 없으면
`sync.failed` 이벤트로 "로그인 필요"가 보인다. 호출은 Outbox 워커 하나에서만 한다 (동시 호출 금지).
