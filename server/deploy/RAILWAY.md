# Railway 배포 (회의 서버 하나를 https로) — author: Mal-Mi-Jal

컨테이너 하나가 화면(`web/dist`)과 서버(`/api`, `/ws`)를 같이 낸다. https 주소가 생겨서 다른 노트북에서도 마이크가 열린다.
**원본 문서(`SEED=google`)를 쓰는 서버는 하나만.** Railway를 회의 서버로 쓰면 각자 PC 서버는 `SEED=sprint`로.

## 1. 프로젝트 만들기 (대시보드)

1. railway.com → **New Project → Deploy from GitHub repo** → `gitgutgit/LostAI`
   - 목록에 없으면 Railway GitHub 앱이 이 레포에 권한이 없는 것 → 레포 주인(gitgutgit)이 *Configure GitHub App*에서 허용
2. 서비스 **Settings → Source → Branch**: 배포할 브랜치 (main 또는 작업 브랜치)
3. **Settings → Networking → Generate Domain** → `https://<이름>.up.railway.app`

## 2. 변수 (Settings → Variables). 값은 대시보드에 직접 넣는다 (채팅·커밋·로그에 남기지 않기)

| 변수 | 값 |
|---|---|
| `RAILWAY_DOCKERFILE_PATH` | `server/deploy/Dockerfile` |
| `RAILWAY_DEPLOYMENT_DRAINING_SECONDS` | `30` (재배포 때 원본 문서 되돌릴 시간) |
| `AGENT_MODE` | `LIVE` 또는 `MOCK` |
| `ANTHROPIC_API_KEY` | LIVE일 때 |
| `SEED` | `google` (원본 문서) / `sprint` (예시 문서) |
| `GOOGLE_SHEET_ID`, `GOOGLE_DOC_ID` | 원본 Sheet/Doc 주소나 ID |
| `GOOGLE_TOKEN_JSON` | 서버 계정 `token.json` **내용 전체** (한 줄 JSON). refresh token과 클라이언트 정보가 들어 있어 이것만 있으면 된다 |
| `JOIN_SECRET` | 아무 긴 무작위 문자열 (재배포해도 입장 토큰이 안 끊기게) |

`PORT`는 Railway가 준다. 나머지(`COMMIT_POLICY` 등)는 비우면 기본값.

## 3. 확인

- `https://<도메인>/health` → `{"ok":true}`
- 배포 로그에 `원본 문서 불러옴: 시트 N행, 문서 섹션 M개` (못 읽으면 경고 후 `SEED=sprint`)
- 화면 접속 → 입장 → 🎙 → 말 → 원본 Sheet/Doc 반영

## 주의

- 재배포·중지 때 서버가 종료 신호를 받으면 회의 중 변경을 원본에서 되돌린다 (`server/app.py` `restore_on_shutdown`). 확실히 하려면 **재배포 전에 화면에서 리셋**.
- 컨테이너 디스크는 재배포 때 비워진다: 이벤트 로그(`results/`)와 화면에서 고른 문서 기록은 사라지고 `GOOGLE_*_ID`로 다시 시작한다.
- Google 앱이 테스트 모드라 refresh token은 약 7일 뒤 만료 → PC에서 `--relogin` 후 `GOOGLE_TOKEN_JSON`을 새 내용으로.
- 이 PC(Windows)는 보안 정책이 `railway.exe`를 막아서 CLI 대신 대시보드를 쓴다.
- 의존성을 바꾸면 `uv export --frozen --no-dev --no-hashes --no-emit-project > server/deploy/requirements.txt` 다시.
