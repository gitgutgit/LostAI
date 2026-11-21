<h1 align="center">
  <img src="../../web/public/favicon.svg" alt="LostAI" width="56" valign="middle" /> LostAI
</h1>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.11%2B-3776AB?style=flat&logo=python&logoColor=white" alt="Python 3.11+" />
  <img src="https://img.shields.io/badge/FastAPI-WebSocket-009688?style=flat&logo=fastapi&logoColor=white" alt="FastAPI + WebSocket" />
  <img src="https://img.shields.io/badge/React-TypeScript-3178C6?style=flat&logo=typescript&logoColor=white" alt="React + TypeScript" />
  <img src="https://img.shields.io/badge/Claude-Haiku%20%7C%20Sonnet-D97757?style=flat" alt="Claude Haiku and Sonnet" />
</p>

<p align="center">
  <sub><a href="../../README.md">English</a> · <b>한국어</b></sub>
</p>

<p align="center">
  <strong>회의에서 말하면, 문서가 바뀝니다.</strong><br/>
  회의를 들으면서 말한 대로 Google Sheets·Docs를 고치고, 모든 변경에 누가 언제 말했는지 남기는 실시간 회의 에이전트입니다.
</p>

<h3 align="center"><a href="https://lostai-production.up.railway.app/"><ins>데모 사이트 열기</ins></a></h3>

<p align="center">
  <sub>시연용 데모 서버이며 데모 문서가 기본으로 제공됩니다. 개인적이거나 민감한 문서는 연결하지 않는 것을 권장합니다.</sub>
</p>

<!-- TODO: 시연 영상 또는 스크린샷 -->

## 기능

### 말로 고치기
브라우저 탭 하나가 화자 한 명이라 화자 분리가 필요 없습니다. 발화마다 빠른 **라우터**(Claude Haiku)가 `ignore / capture / edit / command / ask` 중 하나로 분류합니다. 수정이 필요하면 **에디터**(Claude Sonnet)가 "이 칸을 바꾼다", "이 항목을 넣는다" 같은 작은 수정(op)을 돌려줍니다. 섹션을 통째로 다시 쓰지 않습니다.

### 모든 변경에 출처가 붙는다
변경은 `proposed → applied → approved | reverted` 수명주기를 가진 객체이고, 누가 언제 말했는지를 함께 기록합니다. 마지막 것만이 아니라 **특정** 변경을 되돌릴 수 있습니다. 엔진이 diff에서 역연산을 만들기 때문입니다.

### Google Sheets·Docs 실시간 반영
화면이 먼저 바뀌고, Google은 워커 하나(Outbox)가 한 번에 하나씩 따라 반영합니다. 프로토타입에서 동시에 호출하면 SSL 오류로 깨졌기 때문입니다. 참석자는 각자 자기 Google 계정으로 로그인합니다. Picker API(`drive.file` 범위)라서 그 사람이 고른 파일만 앱이 볼 수 있습니다. 회의 원본 문서를 바꾸려면 지금 문서 주인의 승인이 필요합니다.

### 클릭 대신 손
손 인식은 브라우저 안(Web Worker의 MediaPipe)에서 돌고 LLM을 거치지 않습니다.
- **입장 관문:** 랜덤 손동작 3개를 통과해야 회의방에 들어옵니다.
- **공유 신호:** 엄지 위·아래로 방금 변경을 승인하거나 되돌리고, 손가락 개수로 표결합니다.
- **내 화면 조작:** 확대·축소와 포인터는 내 화면만 바꾸고 서버로 보내지 않습니다.

### 이벤트 로그 하나
서버는 상태가 바뀔 때마다 이벤트를 하나 덧붙이고 그 변화분만 브로드캐스트합니다. 화면, 리플레이, 지연 측정, 디버깅이 모두 같은 로그를 읽습니다.

### 키 없이도 동작
`AGENT_MODE=MOCK`이면 LLM 대신 규칙 기반 라우터·에디터가 동작합니다. API 키 없이 화면 개발, 테스트, 회의 리플레이를 할 수 있습니다.

## 빠른 시작

필요한 것: Python 3.11+, [uv](https://docs.astral.sh/uv/), Node.js 18+

```bash
git clone https://github.com/gitgutgit/LostAI.git && cd LostAI
uv sync
cp .env.example .env                                  # AGENT_MODE=MOCK이면 키 없이 동작
uv run uvicorn server.app:app --reload --port 8000    # 서버

cd web && npm install && npm run dev                  # 화면 http://localhost:5173 (/api·/ws는 8000으로 프록시)
```

- **화면만 (백엔드 없이):** `http://localhost:5173/?fixture=sample_sprint_events`
- **대본 회의 리플레이 + 지연 측정:** `uv run python -m server.replay fixtures/sample_sprint.jsonl`
- **테스트:** `uv run pytest -q`

> 브라우저 마이크는 `localhost`나 `https`에서만 열립니다. 다른 노트북에서 시연하려면 https 터널을 쓰거나 배포하세요(아래 참고).

## 설정

`.env.example`을 `.env`로 복사합니다. `.env`, `credentials.json`, `token.json`은 절대 커밋하지 마세요.

| 변수 | 하는 일 |
|---|---|
| `AGENT_MODE` | `MOCK`(규칙 기반, 키 불필요) 또는 `LIVE`(Anthropic API 호출) |
| `ANTHROPIC_API_KEY` | `LIVE`일 때만 필요 |
| `ROUTER_MODEL`, `EDITOR_MODEL` | 라우터·에디터 모델 |
| `COMMIT_POLICY`, `DELAYED_COMMIT_SEC` | `immediate`, 또는 `delayed`(몇 초 뒤 반영, 그 사이 반대하면 취소) |
| `SEED` | 시작 문서: `sprint`(예시) 또는 `google`(내 Sheet/Doc) |
| `GOOGLE_SHEET_ID`, `GOOGLE_DOC_ID` | 동기화할 문서. 비우면 동기화 꺼짐 |
| `GOOGLE_OAUTH_CLIENT_*`, `GOOGLE_PICKER_API_KEY`, `GOOGLE_PROJECT_NUMBER` | 개인별 Google 로그인과 문서 선택 창 |
| `JOIN_SECRET` | 입장 토큰 서명용. 서버를 다시 켜도 토큰이 유지됨 |

Google 연결 단계별 안내: [`server/sync/GOOGLE_SETUP.md`](../../server/sync/GOOGLE_SETUP.md)

## 배포

컨테이너 하나가 빌드된 화면과 서버(`/api`, `/ws`)를 함께 냅니다. Railway 배포는 [`server/deploy/RAILWAY.md`](../../server/deploy/RAILWAY.md)를 보세요. Dockerfile은 [`server/deploy/`](../../server/deploy/)에 있습니다.

## 동작 방식

```text
브라우저 탭 (= 화자 한 명)              서버 (FastAPI + WebSocket)                외부
 ├─ Web Speech STT  ── 발화 ──▶  회의방 큐 ─▶ 라우터 ─▶ 에디터/답변 ──────▶ Anthropic API
 ├─ 손 인식         ── 신호 ──▶  빠른 길 (규칙, LLM 없음)
 └─ 화면 (이벤트 → UI) ◀─ 변화분 ─  op 엔진 ─▶ 이벤트 로그 (덧붙이기만)
                                           └─▶ Outbox 워커 ──────────────▶ Google Sheets / Docs
```

전체 설계와 데이터 계약, 각 선택의 이유는 [`docs/ARCHITECTURE.md`](../ARCHITECTURE.md)에 있습니다.

```text
server/   FastAPI 앱, 회의방, op 엔진, 에이전트(라우터·에디터·답변), 손 신호, 동기화
web/      Vite + React + TypeScript: STT, 손 인식, 화면
eval/     평가 스크립트와 블라인드 시나리오
fixtures/ 리플레이용 녹화 이벤트 로그
tests/    pytest 테스트
```

## 기여하기

이슈와 풀 리퀘스트를 환영합니다.

- 최신 `main`에서 브랜치를 땁니다: `git switch -c <GitHub 아이디>/<주제> origin/main`. `main`은 풀 리퀘스트로만 바뀝니다.
- 풀 리퀘스트 하나에는 주제 하나만 담고, 커밋 앞에 `[server]` `[ui]` `[agent]` `[sync]` `[docs]` 같은 태그를 붙입니다.
- 공용 계약 파일(`server/events.py`, `server/model/docs.py`, `server/ops/registry.py`)과 TypeScript 사본(`web/src/core/types.ts`)은 함께 고칩니다.
- 풀 리퀘스트 전에 `uv run pytest -q`를 돌립니다.

이 레포의 작업 규칙: [`CLAUDE.md`](../../CLAUDE.md)

## 기여자

<a href="https://github.com/gitgutgit/LostAI/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=gitgutgit/LostAI" alt="LostAI 기여자" />
</a>

[@gitgutgit](https://github.com/gitgutgit) · [@Mal-Mi-Jal](https://github.com/Mal-Mi-Jal) · [@ProfessionalSeaweedDevourer](https://github.com/ProfessionalSeaweedDevourer) · [@HanseoSONNY](https://github.com/HanseoSONNY) · [@77SONNY77](https://github.com/77SONNY77)

LostAI는 c0mpiled-17 Seoul 해커톤(2026년 11월)에서 시작했고, 지금은 오픈소스로 개발하고 있습니다.

## 개인정보

앱이 Google에서 무엇을 읽고 무엇을 저장하는지는 [`web/public/privacy.html`](../../web/public/privacy.html)에 있습니다.

## 라이선스

<!-- TODO: LICENSE 파일(예: MIT)을 추가하고 이 절을 고치세요. -->
아직 라이선스를 정하지 않았습니다.
