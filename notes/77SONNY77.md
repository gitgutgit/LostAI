# 77SONNY77 — hs 작업 기록

> 마지막 업데이트: 2026-11-09
> 담당: hanseoson (hs)
> 작업 영역: 제스처 인증 UI (JoinView), 포인터/줌/최소화/최대화 (viewport)

---

## 변경 파일 목록

### 수정한 파일 (남의 파일 — `// hs:` 코멘트 표시)

| 파일 | 변경 내용 | 코멘트 위치 |
|---|---|---|
| `web/src/views/join/JoinView.tsx` | 제스처 이모지 표시, 10초 타이머, UI 개선, unmount 시 엔진+스트림 정리 | `// hs:` 코멘트 |
| `web/src/styles.css` | JoinView 제스처 인증 UI 스타일 추가 | `/* hs: */` 코멘트 블록 |
| `server/auth/challenge.py` | CANDIDATES를 기본 제스처 7개로 축소, CONFUSABLE 비움 | `# hs:` 코멘트 |
| `web/src/capture/gestures/engine.ts` | `stop()`에서 `rec = null` 처리 (재시작 허용) | `// hs:` 코멘트 |
| `web/src/capture/gestures/viewport.ts` | 포인터 커서 DOM, 줌 스무딩, snapMax/snapMin, moveCursor/showCursor | `// hs:` 코멘트 |
| `web/src/views/canvas/CanvasView.tsx` | PoC 방식 카메라 재초기화, 검지 커서+줌 항상 동작 | `// hs:` 코멘트 |

### 아직 수정 안 한 파일 (예정)

| 파일 | 예정 변경 | 상태 |
|---|---|---|
| `web/src/capture/gestures/viewport.ts` | Closed_Fist→최소화, Open_Palm→최대화 | 대기 |

---

## 상세 변경 내역

### 2026-11-09 — JoinView 제스처 인증 UI 개선

**`web/src/views/join/JoinView.tsx`**
- `GESTURE_INFO` 상수 추가: 제스처 이름 → 이모지 + 한국어 라벨 매핑 (`~/hand-liveness-beta` 참고)
  - Victory → ✌️ 브이, Closed_Fist → ✊ 주먹, Open_Palm → 🖐️ 손바닥 펴기 등 7개
- `STEP_TIMEOUT_MS = 5000` 추가: 단계별 5초 제한 시간
- `startTimer()` 함수: 각 단계 시작 시 5초 카운트다운, 초과 시 챌린지 리셋 + 에러 메시지
- `timerRef` + cleanup: 타이머 누수 방지 (useEffect cleanup)
- 단계 칩(steps): 텍스트 → 이모지 표시로 변경
- `gesture-prompt` 영역: 큰 이모지(120px) + 한국어 라벨 표시 (hand-liveness-beta 스타일)
- `hold-bar`: 인식 진행률 바 (초록색)
- `time-bar`: 5초 타이머 바 (노란색) + 남은 시간 텍스트
- 다음 단계 넘어갈 때 타이머 리셋 (`startTimer()` 재호출)
- 통과 시 `clearInterval`로 타이머 정리

**`web/src/styles.css`**
- `.gesture-prompt`, `.gesture-emoji`, `.gesture-label`: 큰 이모지 프롬프트 스타일
- `.step-chip`, `.step-chip.done`, `.step-chip.now`: 단계 칩 (이모지, 완료/현재 상태)
- `.hold-bar`, `.time-bar`: 진행/타이머 바 스타일
- `.time-text`: 남은 시간 숫자
- `.join-msg`: 에러/상태 메시지
- `.form`, `.challenge`: 레이아웃 정리

### 코멘트를 달 수 없는 부분

- **CSS 속성값 내부**: CSS에서는 개별 속성에 인라인 코멘트를 달 수 없어서, `/* hs: */` 블록 코멘트를 섹션 시작에 한 번 표시함

---

### 2026-11-09 — 검지 커서 + 줌/확대/축소 (CanvasView, PoC 방식)

**`web/src/capture/gestures/viewport.ts`**
- `MAX_SCALE`: 2.5 → 2.0 (PoC 검증값)
- `ZOOM_SMOOTH = 0.06` 상수 추가: 확대 스무딩 계수 (PoC 검증값)
- `targetScale` 필드: 스무딩용 목표 배율 (기존 `scale`과 분리)
- `initCursor()`: 초록색 원(20px) DOM 요소 생성 (`#gesture-pointer`), body에 append
- `showCursor(visible)`: 커서 표시/숨기기
- `moveCursor(p)`: 검지 위치로 커서 DOM 이동 (항상 호출)
- `setOpenness()`: 즉시 반영 → 스무딩 (`scale += 0.06 * (target - scale)`)
- `snapMax()`: Open_Palm → 최대 확대 (빠른 스냅 0.25)
- `snapMin()`: Closed_Fist → 최소 축소 (빠른 스냅 0.25)
- `resetScale()`: `targetScale`도 같이 리셋

**`web/src/capture/gestures/engine.ts`**
- `stop()`에서 `this.rec = null` 추가: 재시작 시 GestureRecognizer 새로 생성되도록

**`web/src/views/join/JoinView.tsx`** (추가 수정)
- `streamRef` 추가: 카메라 스트림을 ref로 관리
- unmount cleanup: `engine.stop()` + `stream.getTracks().forEach(stop)` — JoinView 떠날 때 카메라+엔진 완전 해제

**`web/src/views/canvas/CanvasView.tsx`**
- PoC `pa_hs_gesture_api.js` start() 방식 그대로 이식:
  - `document.createElement("video")` 로 video 직접 생성, **숨김**(화면에 안 보임)
  - `getUserMedia` → `loadeddata` 대기 → `engine.start(vid)` 순서
  - `cancelled` 플래그로 React StrictMode 이중 실행 방어
  - unmount 시 `engine.stop()` + 스트림 정리 + video DOM 제거
- PoC 모드 로직 적용:
  - **Pointing_Up** → 커서 이동 (`moveCursor`), 줌 크기 유지
  - **Closed_Fist** → 커서 고정, `snapMin()` 최소(1x)
  - **Open_Palm** → 커서 고정, `snapMax()` 최대(2x)
  - **그 외(손 벌림)** → 커서 고정(마지막 위치), `setOpenness()` 연속 줌
- 줌 모드 토글 버튼 제거 (제스처로 항상 동작)
- 웹캠 미리보기 제거 (화면에 안 보임)
- Closed_Fist(confidence>0.6) → `snapMin()` (최소)
- Open_Palm(confidence>0.6) → `snapMax()` (최대)
- 그 외 → `setOpenness()` (손 벌림/오므림 → 연속 줌)
- 줌 기준점은 항상 커서 위치 (`setPointer()`)
- 기존 공유 신호(엄지 등 → 서버) 로직 유지

## 메모

- `~/hand-liveness-beta`의 `GESTURES` 객체(이모지+한국어 라벨)를 React 상수로 이식
- 타이머는 `setInterval` + `performance.now()` 기반 (정확도 위해)
- 5초 초과 시 `setCh(null)` + `engine.stop()`으로 완전 리셋 → 사용자가 "카메라 켜고 시작"부터 다시
- 기존 `STEP_HOLD_MS = 600` (0.6초 유지)는 그대로 유지
