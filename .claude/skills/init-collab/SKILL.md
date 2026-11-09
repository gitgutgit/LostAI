---
name: init-collab
description: 회의 에이전트 본선 저장소의 4인 협업 규칙. 팀원·역할·GitHub 아이디, 파트별 폴더 소유(기능 파트 / 서버·UI 파트 / 공용 계약), 브랜치·커밋 규칙, 담당 외 영역 수정 시 경고→승인 절차를 정의한다. 이 저장소에서 코드·데이터·문서를 작성·수정·삭제하기 전에 사용하고, 특히 계약 파일(server/events.py, server/model/docs.py, server/ops/registry.py), 루트 파일, 다른 파트 폴더를 건드려야 할 때는 반드시 사용.
---

# init-collab — 회의 에이전트 본선 협업 규칙

이 저장소는 c0mpiled-17 Seoul 해커톤 본선용이다. 4명이 **파트 2개 + 공용 계약**으로 나눠서 하루 안에 만든다.
구조와 계약의 근거는 `docs/ARCHITECTURE.md`에 있다. 먼저 그 문서의 0절(요약), 4절(데이터 계약), 11절(P0/P1/P2)을 읽는다.

모든 파트가 **같은 계약(이벤트 · 문서 모델 · op)** 위에서 움직인다. 그래서 계약 파일 하나를 고치면 서버, 화면, 에이전트, 평가가 한꺼번에 깨질 수 있다. 이 규칙은 그걸 막기 위한 것이다.
Claude(및 모든 작업자)는 작업 전에 이 문서를 읽고 따른다.

---

## 1. 팀 · 역할 · GitHub

| 이름 | GitHub | 역할 | 파트 | git `user.name` |
|---|---|---|---|---|
| 지원 (Jeewon) · 팀장 | `gitgutgit` | 메인 PM, 큰 아키텍처 설계, 계약 최종 승인 | 총괄 · 공용 계약 | `Kim` |
| 한서 (Hanseo) | `77SONNY77` | 메인 기능 파트 **메인** (모델링: 에이전트·손 인식) | 기능 | _(본인이 채움)_ |
| 태우 (Taewoo) | `Mal-Mi-Jal` | 백엔드/서버 구성 · UI **메인** | 서버·UI | `Mal-Mi-Jal` |
| 주현 (Eric Park) | `ProfessionalSeaweedDevourer` | 메인 기능 파트 **서브** + 백엔드/서버 · UI **서브** | 기능, 서버·UI | `ProfessionalSeaweedDevourer` |

- **메인**은 그 파트의 설계를 결정하고 PR을 확인한다. **서브**는 같은 폴더를 자유롭게 고치되, 설계가 갈리면 메인의 결정을 따른다.
- 맨 오른쪽 칸(`git config user.name` 값)은 각자 처음 작업할 때 자기 행만 채운다. 자기 행 채우기는 승인이 필요 없다.

### 현재 작업자 확인

작업을 시작할 때 아래 순서로 현재 작업자를 확인하고, 표에서 그 사람의 파트를 찾는다.

```bash
gh api user --jq .login 2>/dev/null   # GitHub CLI 로그인 시 GitHub 아이디
git config user.name
git config user.email
```

- 셋 중 어느 것도 표와 맞지 않으면 **작업 전에 "누구인지(이름 또는 GitHub 아이디)" 물어본다.** 답을 받으면 표의 git `user.name` 칸을 채운다.
- git 저장소가 아니어도(`git status` 실패) 규칙은 똑같이 적용한다.

---

## 2. 폴더 소유

| 폴더 · 파일 | 무엇 | 파트 | 메인 | 서브 |
|---|---|---|---|---|
| `server/agent/` | 라우터 · 에디터 · Asker · 프롬프트 | 기능 | 한서 | 주현 |
| `server/gestures/` | 손 신호 빠른 길(엄지 승인·되돌림, 표결, T자) | 기능 | 한서 | 주현 |
| `web/src/capture/gestures/` | MediaPipe 엔진, 손동작 정의, 모드(기본/확대/입장), 확대·축소 | 기능 | 한서 | 주현 |
| `eval/` | 평가 대본, 채점 도구 | 기능 | 한서 | 주현 |
| `server/app.py`, `server/room.py`, `server/replay.py` | 서버, 회의방, 리플레이 | 서버·UI | 태우 | 주현 |
| `server/ops/engine.py`, `server/ops/changes.py` | op 적용, 되돌림, 변경 수명주기 | 서버·UI | 태우 | 주현 |
| `server/auth/` | 입장 관문(도전 발급·검증·토큰) | 서버·UI | 태우 | 주현 |
| `server/sync/` | Outbox, Google Sheets/Docs, Linear | 서버·UI | 태우 | 주현 |
| `web/src/core/`, `web/src/components/`, `web/src/views/` | 이벤트 store, 공용 화면 부품, 입장·회의 화면 | 서버·UI | 태우 | 주현 |
| `web/src/capture/stt.ts` | 음성 인식 | 서버·UI | 태우 | 주현 |
| `fixtures/` | 녹화된 이벤트(화면 개발용) | 서버·UI | 태우 | 주현 |
| **계약**: `server/events.py`, `server/model/docs.py`, `server/ops/registry.py`, `web/src/core/types.ts` | 이벤트 · 문서 모델 · op 정의와 그 TS 사본 | **공용 계약** | 지원(팀장) | — |
| **루트·문서**: `README.md`, `docs/`, `.env.example`, `.gitignore`, `.claude/`, `pyproject.toml` 또는 `requirements.txt`, `web/package.json` | 공용 보호 영역 | 공용 | 지원(팀장) | — |
| `notes/<GitHub>.md` | 각자 작업 노트 (`note-tracking`) | 각자 | 본인 | — |
| `server/common/`, `web/src/lib/` | 여러 파트가 쓰는 작은 유틸 | 공용 후보 | 만든 사람 | — |

### 무엇을 승인 없이 해도 되나

| 영역 | 승인 없이 해도 되는 것 | §4 경고→승인이 필요한 것 |
|---|---|---|
| 내 파트 폴더 (메인·서브 둘 다) | 생성 · 수정 · 삭제 전부 | — (설계가 갈리면 메인이 결정) |
| 다른 파트 폴더 | 읽기, import | 수정 · 삭제 전부 |
| 계약 파일 | 읽기, import | **모든 수정** (한 줄이라도) + 팀장 확인 |
| 루트·문서 | README의 내 파트 칸 채우기, 의존성 **추가** (알리기만) | 그 외 모든 수정, 의존성 버전 변경·삭제 |
| `fixtures/` | 내 이름으로 새 파일 추가 (`<GitHub>_<장면>.jsonl`) | 남이 만든 fixture 수정 |
| `server/common/`, `web/src/lib/` | 새 파일 추가 | 남이 만든 코드 수정 |
| `notes/` | 내 note | 남의 note 수정 (금지) |

### 계약을 고치면 누가 영향을 받나 (§4 영향 범위에 쓴다)

| 파일 | 쓰는 곳 | 고치면 생기는 일 |
|---|---|---|
| `server/events.py` | 서버 전체, `web/src/core/`, `fixtures/` | 이벤트 이름·필드가 바뀌면 화면과 녹화 fixture가 깨진다. `web/src/core/types.ts`도 같이 바꿔야 한다 |
| `server/model/docs.py` | op 엔진, sync, 에이전트 프롬프트의 상태 요약, `SheetView`/`DocView` | 앵커 형식이 바뀌면 출처(provenance)와 하이라이트가 깨진다 |
| `server/ops/registry.py` | 에이전트 툴 스키마, op 엔진, sync 변환, eval 채점 | op 이름·필드가 바뀌면 eval 채점과 이전 정확도 숫자를 비교할 수 없다 |
| `web/src/core/types.ts` | 화면 전체 | 위 세 파일의 TS 사본. 서버 쪽과 항상 같이 바뀐다 |

계약은 아니지만 **숫자에 영향을 주는 파일**도 있다. `server/agent/prompts.py`를 고치면 라우터 정확도와 지연 숫자의 기준이 바뀐다. 기능 파트 안에서는 자유롭게 고치되, 고친 시각을 note의 `메모`에 "<시각> 이후 기준 변경"으로 남긴다.

### 평가 대본 규칙
평가 대본을 쓰는 사람은 `server/agent/prompts.py`를 읽지 않는다(`eval/WRITING_SPEC.md` 1절). 시험에 맞춰 답을 가르치지 않기 위해서다. **대본 작성과 프롬프트 수정은 같은 사람이 하지 않는다.** 누가 무엇을 맡을지는 기능 파트 메인이 정한다.

---

## 3. 브랜치 · 커밋 · 파일 이름

1. **브랜치는 `<GitHub 아이디>/<짧은 주제>`로 만든다.** 예: `77SONNY77/join-gate`, `Mal-Mi-Jal/canvas-view`.
2. **main 브랜치에는 PR로만 들어간다.** 파트 메인(또는 서브) 한 명이 확인하면 merge한다. 계약 파일이 들어간 PR은 팀장이 확인한다. 예외로 문서 오타, 자기 note는 main에 바로 push해도 된다.
3. **커밋 메시지 앞에 영역 태그를 붙인다.** `[agent]` `[gesture]` `[eval]` `[server]` `[sync]` `[ui]` `[contract]` `[docs]`
   예: `[gesture] 확대 모드를 브이 0.5초 유지로 켜기`
4. **사람 prefix는 붙이지 않는다.** PoC 때는 `pa_`, `pa_hs_`처럼 붙였지만, 이번에는 폴더 소유로 구분한다. 파일·함수 이름은 하는 일 그대로 짓는다.
5. **결과 파일**은 `results/<GitHub>_<무엇>_<MMDD_HHMM>.json`으로 저장한다. `results/`는 `.gitignore`에 넣는다. 공유할 숫자는 note에 적는다.
6. **발표 전 동결**: 동결 시각 `[HH:MM, 팀장이 정함]` 이후에는 main merge를 팀장만 한다. 그 뒤에는 데모를 깨지 않는 수정만 받는다.

---

## 4. 담당 외 영역을 수정해야 할 때 (경고 → 승인 절차)

다른 파트 폴더, 계약 파일, 루트·문서, 남이 만든 fixture·공용 유틸은 **꼭 필요할 때만** 손댄다.
그럴 때 Claude는 **아무것도 바꾸기 전에** 아래 순서를 따른다.

### 4-1. 먼저 상세 경고를 보여준다

```
⚠️ 담당 외 영역 수정 경고
- 현재 작업자 : 한서 (77SONNY77) · 기능 파트 메인
- 수정 대상    : server/events.py  (소유: 공용 계약 · 승인: 팀장 지원)
- 수정 이유    : 입장 관문에서 손동작별 유지 시간을 서버가 검증하려면 gesture 이벤트에 hold_ms가 필요함
- 변경 내용    :
    1) GesturePayload에 hold_ms: int 추가 (기본값 0, 기존 이벤트 그대로 읽힘)
    2) web/src/core/types.ts의 GesturePayload에도 같은 필드 추가
- 영향 범위    : server/auth/challenge.py, server/gestures/fastpath.py, web/src/core/store.ts
                 fixtures/ 3개 파일 (필드가 없어도 기본값으로 읽힘)
                 결과 숫자 영향: 없음
- 대안         : 입장 단계 결과를 별도 HTTP 요청 본문으로만 보내면 events.py 수정 없이 가능 (권장: X, 이벤트 로그에 안 남음)
- 승인 필요    : 팀장(지원) · 영향 파트 메인(태우)
- 진행할까요? (예 / 아니오 / 대안으로 진행)
```

경고에는 반드시 아래가 들어가야 한다.
- **누가**, **어떤 파일**을, 그 파일이 **누구 소유인지** (계약이면 팀장, 파트 폴더면 그 파트 메인)
- **왜** 고쳐야 하는지
- **무엇이 바뀌는지** (diff, 또는 바뀌는 필드·함수·시그니처 목록)
- **영향 범위**: 그 코드를 쓰는 파일 + fixture + **결과 숫자(정확도·지연·통과율)에 영향이 있는지**
- **고치지 않고 해결할 대안**이 있는지
- **누구의 승인이 필요한지**

영향 범위는 추측하지 말고 검색으로 확인한다.

```bash
grep -rn "<이름>" server web/src eval fixtures
```

### 4-2. 명시적인 승인을 받은 뒤에만 진행한다
- 작업자가 **"예"/"진행"처럼 분명하게 허용한 경우에만** 고친다. 대답이 애매하거나 없으면 **고치지 않는다.**
- 계약 파일이나 다른 파트 폴더라면, 작업자에게 **"<승인자>에게 확인받았나요?"**라고 한 번 더 묻는다. 확인받지 않았다고 하면 고치지 않고, 승인자에게 보낼 요청 메시지를 써 준다.
- 승인은 **그 변경 한 건에만** 유효하다. 다른 파일이나 추가 변경은 다시 경고하고 승인을 받는다.

### 4-3. 고친 뒤 보고한다
- 실제로 바뀐 내용(diff 요약)을 알려준다.
- 계약을 고쳤으면 서버와 화면을 **한 번씩 실행해 깨지지 않는지** 확인한다. `fixtures/` 재생으로 화면을 돌려 봐도 된다. 못 돌렸으면 못 돌렸다고 적는다.
- 소유자에게 공유할 메시지(커밋 메시지 · PR 설명용)를 써준다.
  ```
  [contract] server/events.py by 77SONNY77
  - GesturePayload에 hold_ms 추가 (기본값 0, 기존 이벤트 그대로 읽힘)
  - web/src/core/types.ts 같이 수정
  - 사유: 입장 관문에서 유지 시간 검증
  - 영향: auth, gestures, web core / 숫자 영향 없음 / 서버 실행 + fixture 재생 확인
  - 확인 요청: gitgutgit(계약), Mal-Mi-Jal(서버·UI)
  ```
- 내 note의 `다른 영역 관련`에 기록한다. (`note-tracking`)

### 고치기 전에 먼저 생각할 대안
1. 내 파트 폴더 안에서 **감싸는 함수나 어댑터**로 해결한다.
2. 다른 파트도 쓸 만하면 `server/common/` 또는 `web/src/lib/`에 **새 파일**로 만든다. 기존 파일은 그대로 둔다.
3. 소유자에게 **수정을 요청**한다. note의 `다른 영역 관련`에 "요청함"으로 남긴다.

---

## 5. 공용 유틸 (`server/common/`, `web/src/lib/`)

작업하다 **다른 파트도 쓸 것 같은 작은 코드**(지연 측정, 퍼센타일, 로그 포맷, 앵커 문자열 처리 등)는 여기 새 파일로 만든다.

- 파일 맨 위 docstring이나 주석에 만든 사람의 GitHub 아이디를 적는다.
  ```python
  """지연 퍼센타일 계산 (p50/p95). author: Mal-Mi-Jal"""
  ```
- **새 파일 추가는 누구나 자유롭게** 한다. 남이 만든 파일을 고치는 것은 §4를 따른다.
- 계약에 들어갈 만한 것(이벤트 필드, op 이름, 앵커 형식)은 여기 두지 않는다. 계약은 계약 파일에만 둔다.

---

## 6. 비밀 정보

- `.env`, `credentials.json`, `token.json`은 **커밋하지 않고**(`.gitignore`에 있어야 함), **내용을 출력하거나 note · 커밋 메시지 · PR에 적지 않는다.** Anthropic, Deepgram, Linear 키와 Google OAuth 파일이 모두 해당한다.
- 키가 있는지 확인할 때는 값 대신 설정 여부만 본다.
  ```bash
  awk -F= '/^[A-Z_]+=/{print $1, (length($2)>0?"(set)":"(empty)")}' .env
  ```
- 새 환경 변수가 필요하면 `.env.example`에 **빈 값으로** 추가한다. 루트 파일이므로 §4를 따른다.
- Google 문서 ID·URL, 시연용 터널 주소는 note에 적지 않는다.

---

## 7. Claude 작업 체크리스트

작업할 때마다 확인한다.

- [ ] 현재 작업자를 확인하고 §1 표에서 파트를 찾았는가? (없으면 물어봤는가?)
- [ ] 만들거나 고치는 파일이 내 파트 폴더 안에 있는가? (§2 표)
- [ ] 브랜치 이름이 `<GitHub>/<주제>`이고, 커밋 메시지에 영역 태그를 붙였는가?
- [ ] 다른 파트도 쓸 코드라면 `server/common/` · `web/src/lib/`에 새 파일로 만들었는가?
- [ ] 계약 파일, 루트·문서, 다른 파트 폴더를 건드린다면 **경고 → 승인(승인자 확인 포함) → 수정 → 실행 확인 → 보고** 순서를 지켰는가?
- [ ] 계약을 고쳤으면 `web/src/core/types.ts`도 같이 바꿨는가?
- [ ] 숫자에 영향을 주는 변경(프롬프트, 평가 대본, op 이름)이면 note에 기준 변경을 적고 팀에 알렸는가?
- [ ] 비밀 정보를 출력하거나 기록하지 않았는가?
- [ ] 진행 상황을 내 note에 기록했는가? (`note-tracking` 스킬)
