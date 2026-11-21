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
| `API가 꺼져 있음` | GCP 프로젝트에서 Sheets/Docs/Picker API 미사용 | 관리자가 API 사용 설정 (Picker는 문서 고르기용, 6-1절) |
| 문서 고르기 로그인 창이 바로 닫힘 / `idpiframe`·`origin` 오류 | 웹 클라이언트의 JavaScript 원본에 지금 주소가 없음 | 6-1절 1번에 주소 추가 (반영까지 몇 분) |
| 문서 고르기 `access_denied` | 테스트 사용자에 없는 Gmail | 6-1절 5번 |
| `invalid_grant` / 토큰 만료 | 테스트 모드 토큰은 약 7일 뒤 만료 | 자동으로 다시 로그인함. 안 되면 `--relogin` |
| `redirect_uri_mismatch` | 클라이언트 유형이 데스크톱 앱이 아님 | 데스크톱 앱 클라이언트로 다시 발급 |

## 4. 서버에서 쓰기

`google_sheets.py` / `google_docs.py`는 `google_auth.service("sheets", "v4")`, `service("docs", "v1")`로
클라이언트를 받는다. 서버 안에서는 브라우저 로그인을 띄우지 않는다(`interactive=False`) → 토큰이 없으면
`sync.failed` 이벤트로 "로그인 필요"가 보인다. 호출은 Outbox 워커 하나에서만 한다 (동시 호출 금지).

## 5. 원본 문서 모드 (`SEED=google`) — 시연 기본

`.env`에 `SEED=google`을 두면 서버가 **팀 원본 문서를 회의 시작 상태로 불러오고, 원본에 직접** 고친다.

| | 동작 |
|---|---|
| 서버 시작 | `GOOGLE_SHEET_ID` 첫 탭(1행 = 열 이름), `GOOGLE_DOC_ID` 첫 탭(제목 → 섹션 → 문단)을 불러옴 |
| 말로 수정 | **바뀐 칸·문단만** 원본에 반영 (통째로 덮지 않음). 이번 변경은 노란색, 시트는 셀 메모 / 문서는 회색 `· 누가` |
| 결정·액션 | 원본에 '결정 사항'·'액션' 섹션이 없으면 처음 기록될 때 문서 끝에 추가 |
| 리셋 (`/api/reset`) | 회의 중 변경을 역순으로 되돌리고 추가한 섹션을 지움 → **회의 시작 전 원본과 똑같이** |
| 화면 바로가기 | 원본 탭으로 바로 열림 |

- "회의 시작" 기준은 **서버를 켠 순간**이다. 서버를 재시작하면 그때의 원본이 새 기준이 된다 (사람이 고친 내용을 리셋이 지우지 않게).
- 회의 중 사람이 원본 Doc에 섹션·문단을 직접 넣으면 위치가 어긋나므로 `sync.failed`("구조가 바뀜")가 뜬다 → 리셋하거나 서버를 재시작.
- 원본을 못 읽으면 경고 후 `SEED=sprint`(시드 문서)로 연다. 리플레이·테스트는 항상 시드 문서를 쓴다.
- 만일을 위해 원본은 Google 문서 **버전 기록**으로도 되돌릴 수 있다.

## 6. 문서 고르기 · 새로 만들기 (화면 📂 문서 바꾸기) — 각자 Google 로그인

- 참석자가 **자기 Google 계정으로 로그인**하고 자기 Sheet(보드)·Doc(노트)을 골라 회의 원본을 바꾼다. `.env` 수정·재시작이 필요 없다.
- 파일 목록은 **Google Picker**가 그 사람 브라우저에서 Google과 직접 주고받는다 → 다른 사람 Drive는 보이지 않고, 우리 서버는 고른 파일 id만 받는다.
  예전의 서버 계정 Drive 목록(`/api/google/files`)은 서버 계정 문서가 모두에게 보여서 없앴다.
- 권한은 `drive.file` 하나 (+ 계정 이메일 표시). 이 앱은 **그 사람이 Picker에서 고른 파일과 이 앱이 만든 파일만** 열 수 있다. 문서 id를 직접 넣어도 그 사람 권한 밖이면 400.
- 원본 Sheet와 Doc은 항상 **한 사람(문서 주인) 것**이다. 회의 중 Google 쓰기는 주인 토큰으로 한다.
  - 안 고른 쪽: 내가 지금 주인이면 그대로, 아니면 **내 Drive에 새로** 만든다.
  - 바꾸면 지금 원본은 **지금 주인 토큰으로** 회의 전 상태로 복원된 뒤 새 주인으로 넘어간다 (리셋과 같은 길). 모든 참석자 화면이 같이 바뀐다.
- Google 로그인은 입장 토큰이 아니라 로그인 때 서버가 만든 **무작위 열쇠(gsid)** 에 묶인다. 그 탭의 sessionStorage에만 있어서,
  같은 이름으로 들어온 다른 사람(입장 토큰은 이름만으로 만들어져 같다)도 내 Drive를 열 수 없다. 새 탭에서는 다시 로그인한다.
- 개인 토큰은 **서버 메모리에만** 있다 (디스크·로그에 안 남김). 서버를 다시 켜면 각자 다시 로그인하고, 회의는 `.env`의 기본 원본(서버 계정 `token.json`)으로 시작한다.
- 표가 있는 Doc, 첫 줄(열 이름)이 비었거나 겹치는 Sheet는 거절한다 (회의는 그대로).
- 새로 만들기: Sheet `작업·담당·기간(일)·상태·메모`, Doc `제목 + 목표·메모·리스크`. 만든 사람 Drive에 남는다 (지우기는 Drive에서 직접).
- API: `GET /api/google/config`, `POST /api/google/login|logout`, `GET /api/google/access`(Picker용, 내 브라우저에만), `GET·POST /api/google/source` (`server/sync/source_api.py`, `server/sync/user_auth.py`)

### 6-1. 처음 한 번 (GCP 관리자)

1. **API 및 서비스 → 사용자 인증 정보 → OAuth 클라이언트 ID 만들기 → "웹 애플리케이션"** (기존 데스크톱 클라이언트와 별개).
   승인된 JavaScript 원본: `http://localhost:5173`, `http://localhost:8000`, 배포 주소(예: Railway 도메인). 리디렉션 URI는 필요 없다 (팝업 코드 방식).
2. **라이브러리 → Google Picker API 사용**. Sheets·Docs API도 켜져 있어야 한다.
3. **API 키** 만들기 → 애플리케이션 제한 "HTTP 리퍼러"(위 원본 주소들), API 제한 "Google Picker API".
4. **프로젝트 번호** 확인 (대시보드 → 프로젝트 정보). Picker `setAppId`에 쓴다.
5. OAuth 동의 화면이 **테스트** 상태면 로그인할 사람 Gmail을 **테스트 사용자**에 추가한다 (테스트 상태 토큰은 약 7일 뒤 만료).
6. `.env`(배포는 서비스 변수)에 넣는다. **`.env.example`에는 값을 넣지 않는다** (git에 올라간다).
   ```
   GOOGLE_OAUTH_CLIENT_FILE=~/Downloads/client_secret_....json   # 콘솔에서 받은 JSON 파일 경로 (레포 밖 권장)
   # 또는 GOOGLE_OAUTH_CLIENT_JSON={...그 파일 내용...}           # 배포(Railway): 파일을 못 올리니 내용을 변수로
   # 또는 GOOGLE_OAUTH_CLIENT_ID=...apps.googleusercontent.com + GOOGLE_OAUTH_CLIENT_SECRET=GOCSPX-...
   GOOGLE_OAUTH_CLIENT_ID=...apps.googleusercontent.com           # 파일을 쓰면 없어도 된다
   GOOGLE_PICKER_API_KEY=AIza...
   GOOGLE_PROJECT_NUMBER=123456789012
   ```
   secret은 `GOCSPX-`로 시작한다. 파일 이름을 SECRET 칸에 넣으면 로그인 때 `invalid_client`가 난다 (파일 경로는 FILE 칸에).
   넷 중 하나라도 비면 문서 고르기 창에 "아직 설정되지 않았어요"가 뜨고 바꾸기는 막힌다 (409). 서버 계정 원본으로 하는 회의는 그대로 된다.
