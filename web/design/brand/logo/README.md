# MOAI 로고 폴더 안내 (2026-11-09 13:05)

- **정본은 v2/ 이다.** 그림은 v2/build.py 가 만들고, 앱(LostAI web/src/views/brand/Moai.tsx)이 같은 도형 상수를 쓴다. 두 곳이 같은지는 `python3 v2/check_geometry.py <Moai.tsx 경로>` 로 대조한다.
  - 라이트판(먹색 석상 + 상태 빛 + 소품): moai_<상태>.svg, 워드마크 moai_wordmark_ink.svg, moai_wordmark_reverse.svg, 파비콘 moai_favicon.svg. 프론트에 실린 판.
  - 다크판(상태 색 석상): dark_moai_<상태>.svg. 설계 정본이지만 프론트 반영은 저우선(Eric 12:53).
  - 배제안: v2/_rejected/ (다크 바탕 위 밝은 석상 + 빛, Eric 12:45).
- **이 폴더 바로 아래 SVG 7종, png/, sheet_v1.html 은 퇴역한 v1 이다.** 얼굴(눈 두 칸)과 비례가 v2와 다르니 새 작업에 쓰지 않는다. 다른 문서가 경로로 참조하고 있어 옮기지 않았다.
- 경위와 판독 숫자: ../moai_brand_apply_plan_ko_20261109.md
