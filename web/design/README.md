# web/design: 결정 벽과 MOAI 브랜드의 디자인 원본

앱 화면(web/src/views)을 만들 때 기준으로 삼는 원본과 그것을 앱과 대조하는 도구다. 빌드에는 들어가지 않는다.
2026-11-09까지는 PoC 저장소(meeting-agent-poc)의 design 폴더에만 있었고, 이 폴더가 정본이 되면서 옮겨 왔다.
아래 문서 안의 `meeting-agent-poc/design/...` 경로는 옮기기 전 기록이다. 지금 위치는 이렇게 읽는다.

| 옛 위치 (meeting-agent-poc/design) | 지금 위치 (LostAI) |
|---|---|
| `wireframes/facilitator_v0_3/render_v04/` | `web/design/render_v04/` |
| `brand/` | `web/design/brand/` |
| `tools/wall_judge/` | `web/design/wall_judge/` |

## 무엇이 있나

- `render_v04/index.html`: 결정 벽 장면 11개(d1 ~ s9)의 원본. 앱 장면 재생(`?view=wall`)은 이것과 화소 단위로 같아야 한다.
  - 원본을 먼저 고치고 앱에 옮긴다.
  - MOAI 표시등 CSS는 `web/src/views/brand/moai.css`를 그대로 복사해 둔 것이다. moai.css를 고치면 `python3 web/design/render_v04/sync_moai_css.py`로 다시 붙인다.
- `wall_judge/`: 원본과 앱을 헤드리스 Chrome으로 22장(장면 11개, 질문 띠 켬과 끔) 찍어 화소를 대조한다.
  - `wall_judge/run_all.sh 'http://localhost:5173/?view=wall&shot'`: 앱을 찍고 대조한다. 원본(ref)이 없으면 먼저 찍는다. 원본을 고쳤으면 `wall_judge/ref/`를 지우고 다시 돌린다.
  - `selftest.sh`(잡음 바닥 측정)는 PNG 내보내기 `render_v04/png/`가 있어야 돈다. 그 폴더는 넣지 않았다.
  - 판정 기준은 차이 0.5% 이하이고, 지금 목표는 22장 모두 0 px이다.
  - 찍은 PNG와 대조 결과는 git에 넣지 않는다(.gitignore).
- `brand/`: MOAI 이름, 마스코트, 로고 작업 기록.
  - `moai_brand_apply_plan_ko_20261109.md`: 앱 반영 기획과 판정 기록 (11절이 현행).
  - `logo/README.md`: 로고 판본 정리. v2가 정본이고, v1(`logo/` 바로 아래 SVG)은 은퇴했다.
  - `logo/v2/build.py`: 마스코트 SVG 생성. `logo/v2/render.sh`로 PNG를 다시 만든다.
  - `logo/v2/check_geometry.py`: build.py와 `web/src/views/brand/Moai.tsx`의 도형 상수가 같은지 확인한다.
  - `logo/v2/judge/`: 무맥락 판독(claude -p) 스크립트와 결과 숫자. 판독 원자료 PNG는 넣지 않았다.

## 넣지 않은 것

PNG 내보내기(스크립트로 다시 만든다), 배제안(`_rejected`, 글로우 판), 판독 원자료, 캡처는 PoC 저장소 쪽에만 남아 있다.
