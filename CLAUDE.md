# CLAUDE.md — 회의 에이전트 (c0mpiled-17 Seoul 본선)

> 한 줄 피치: **Say it in the meeting. The doc changes.** 모든 변경에 누가 말했는지 붙는다.
> 팀 원칙: **말은 회의에, 손은 에이전트에.**
> 설계 근거 전체: `docs/ARCHITECTURE.md` (먼저 0절 요약, 4절 데이터 계약, 11절 P0/P1/P2를 읽는다)

## 작업 전에 반드시

1. **`init-collab` 스킬을 따른다** (`.claude/skills/init-collab/SKILL.md`). 현재 작업자 확인 → 파트 확인 → 담당 외 영역이면 **경고 → 승인 → 수정 → 실행 확인 → 보고**.
2. **`note-tracking` 스킬로 `notes/<GitHub 아이디>.md`를 바로바로 갱신한다** (`.claude/skills/note-tracking/SKILL.md`). 세션 시작 시 내 note와 **공용 노트 `notes/TEAM.md`**(일정·P0 현황·결정·계약 변경 기록)를 먼저 읽는다.
3. 비밀 정보(`.env`, `credentials.json`, `token.json`, API 키, Google 문서 ID, 터널 주소)는 출력·기록·커밋하지 않는다.

## 핵심 설계 (바꾸려면 팀장 승인)

- **이벤트 로그가 단일 진실.** 서버는 상태를 바꿀 때마다 이벤트 1개를 append하고 그 delta만 브로드캐스트한다. 접속 시에는 스냅샷 + 최근 이벤트. 화면·리플레이·지연 측정이 전부 이 로그를 읽는다.
- **op는 앵커 기반의 작은 수정.** 칸 앵커 `board/r_pay423/추정`, 문서 항목 앵커 `notes/s_risk/i_12`. 섹션 통째 재작성(`edit_doc`) 금지.
- **Change는 수명주기 객체.** `proposed → applied → approved | reverted`, 실패는 `failed`, 지연 중 취소는 `discarded`. 커밋 정책(`immediate` / `delayed`)은 설정값. 되돌리기는 **특정 change**를 diff 역연산으로.
- **op 정의는 `server/ops/registry.py` 한 곳.** LLM 툴 스키마·검증·적용·역연산·Google 변환이 여기서 파생된다. 새 op를 다른 곳에 흩뿌리지 않는다.
- **손 인식은 LLM을 거치지 않는다.** 입장 관문(서버가 랜덤 손동작 3개 발급·검증) / 로컬 화면 조작(확대·축소·포인터 — **서버로 안 보냄, 이벤트 로그에 안 남김**) / 공유 신호(엄지·표결·T자 → 서버 빠른 길 규칙 처리).
- **손 인식 모드 분리:** 기본(공유 신호만) / 확대(브이로 켬: 포인터+확대·축소+주먹=100% 복귀) / 입장(도전 손동작만). 확대 대상은 문서 영역만.
- **외부 동기화는 Outbox 워커 1개로 줄 세운다.** Google 동시 호출 금지(PoC: 8스레드 16건 중 12건 SSL 실패). 화면은 Google을 기다리지 않는다.
- **라우터 라벨 5개:** `ignore / capture / edit / command / ask`. 라우터 haiku(`claude-haiku-5-5`), 에디터 sonnet(`claude-sonnet-5-5`). 이 모델들은 forced `tool_choice`(any/tool)가 400이므로 `tool_choice: auto` + `strict: true` + 프롬프트 지시로 op를 받는다.
- 발화는 회의방마다 큐 하나로 **순서대로** 처리한다.

## 계약 파일 (한 줄이라도 고치면 팀장 승인, TS 사본 동시 수정)

| 파일 | 내용 | TS 사본 |
|---|---|---|
| `server/events.py` | 이벤트 공통 형식·type 목록·payload | `web/src/core/types.ts` |
| `server/model/docs.py` | Sheet/Doc 중립 모델, 앵커 | `web/src/core/types.ts` |
| `server/ops/registry.py` | op 정의 → 툴 스키마 | `web/src/core/types.ts` |

`server/agent/prompts.py` 변경은 라우터 정확도·지연 기준을 바꾼다 → note `메모`에 "<시각> 이후 기준 변경". **평가 대본 작성자는 `prompts.py`를 읽지 않는다.**

## 레포 구조

```text
server/                Python 3.11+ · FastAPI · WebSocket
  app.py               /join, /join/{id}/step, /ws, /stats, /health          [서버·UI]
  room.py              회의방: 발화 큐, 이벤트 로그(JSONL), 브로드캐스트       [서버·UI]
  replay.py            fixtures/대본 → 회의방 재생, 지연 기록                  [서버·UI]
  events.py            ← 계약
  model/docs.py        ← 계약     model/seeds/  시나리오 시작 문서
  ops/registry.py      ← 계약     ops/engine.py 적용·diff·역연산·provenance   [서버·UI]
                                  ops/changes.py Change 수명주기·커밋 정책     [서버·UI]
  agent/               router · editor · asker · prompts · pipeline           [기능]
  auth/challenge.py    입장 관문                                              [서버·UI]
  gestures/            fastpath(엄지·T자) · votes(표결)                        [기능]
  sync/                outbox · google_sheets · google_docs · linear          [서버·UI]
  common/              공용 유틸 (새 파일은 자유, 남의 파일 수정은 승인)
web/                   Vite + React + TS
  src/core/            ws 클라이언트, 이벤트 store, reducer, types.ts(←계약)  [서버·UI]
  src/capture/stt.ts   Web Speech STT                                        [서버·UI]
  src/capture/gestures/ engine.worker · vocabulary · modes · viewport        [기능]
  src/components/      SheetView, DocView, ChangeCard, AgentStatus …         [서버·UI]
  src/views/           join(공통) · canvas(B, 먼저) · chat(A) · page(C)       [서버·UI]
  src/lib/             공용 유틸
eval/                  평가 대본, 채점 도구                                   [기능]
fixtures/              녹화 이벤트 JSONL (`<GitHub>_<장면>.jsonl`)            [서버·UI]
notes/<GitHub>.md      각자 작업 노트
results/               결과 파일 (gitignore)
```

## 실행

```bash
# 서버 (uv 사용, Python 3.11+)
uv sync
cp .env.example .env            # 키 없으면 AGENT_MODE=MOCK 으로 동작
uv run uvicorn server.app:app --reload --port 8000

# 화면
cd web && npm install && npm run dev      # http://localhost:5173, /api·/ws 는 8000으로 프록시

# 백엔드 없이 화면 개발 / 리플레이
uv run python -m server.replay fixtures/sample_sprint.jsonl
```

- 브라우저 마이크는 localhost나 https에서만 열린다. 다른 노트북 시연은 cloudflared https 터널.
- `AGENT_MODE=MOCK`이면 LLM 없이 규칙 기반 라우터·에디터로 동작한다(화면·엔진 개발용). 숫자를 적을 때는 MOCK/LIVE를 꼭 붙인다.

## 브랜치 · 커밋

- 브랜치 `<GitHub 아이디>/<짧은 주제>`, main은 PR로만.
- 커밋 앞에 태그: `[agent]` `[gesture]` `[eval]` `[server]` `[sync]` `[ui]` `[contract]` `[docs]`
- 사람 prefix(`pa_` 등) 금지. 파일·함수는 하는 일 그대로 이름 짓는다.
- 결과 파일: `results/<GitHub>_<무엇>_<MMDD_HHMM>.json`

## 목표 숫자

| 지표 | 목표 |
|---|---|
| 말 → 화면 p50 | 2.5초 미만 (PoC p50 3.1초 / p95 4.3초) |
| 라우터 단독 | 0.6초 (PoC 0.9초) |
| 에디터 | 1.5초 |
| 적용 + 브로드캐스트 | 50ms 미만 |
| 손 신호 반영 | 1초 이내 |

## 우선순위 (ARCHITECTURE 11절)

- **P0**: 회의방+WS, Web Speech STT, Router/Editor, Op 엔진(set_cell, add_row, insert_item, 결정·액션·충돌), B 화면 보드·노트 탭, Google Sheets 동기화, 리플레이, 입장 관문(손동작 3개), 확대 모드+확대·축소·포인터
- **P1**: 엄지 승인·되돌림, Google Docs 동기화, ask 답변, 칸 팝오버, 머물기 클릭, 손 인식 Web Worker, 라우터·에디터 동시 실행
- **P2**: 손가락 표결, 가리키기, T자 일시정지, 손바닥 쓸기, 입장 랜드마크 재확인, Linear, C 제안 모드, Deepgram

## 미정 사항 (docs/ARCHITECTURE.md 14절)

화면 B 확정 여부, 시연 대본, 입장 실패 시 참관 허용 여부, 확대 모드 켜는 방법(브이/버튼/둘 다), 회의 중 추가 모션 범위.
뼈대는 **Vite + React + TS**, **B(캔버스) 화면 먼저** 기준으로 잡혀 있다.
