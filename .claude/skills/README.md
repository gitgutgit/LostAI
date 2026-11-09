# 팀 스킬 목록

이 폴더의 스킬은 저장소를 연 모든 팀원의 Claude Code에 자동으로 잡힌다. 슬래시 명령으로 부르거나, 설명에 맞는 상황이면 Claude가 알아서 쓴다. 이 폴더는 공용 보호 영역이라 고치려면 `init-collab` §4 절차와 팀장(지원, `gitgutgit`) 승인이 필요하다.

| 스킬 | 무엇 | 언제 | 부르는 법 |
|---|---|---|---|
| `init-collab` | 팀원과 파트, 폴더 소유, 브랜치와 커밋 규칙, 담당 외 영역 수정 시 경고와 승인 절차 | 코드, 데이터, 문서를 고치기 전 항상. 특히 계약 파일, 루트, 다른 파트 폴더 | `/init-collab` (CLAUDE.md가 작업 전에 따르게 함) |
| `note-tracking` | `notes/<GitHub 아이디>.md`에 진행 상황, P0/P1/P2, 최근 숫자를 계속 기록 | 세션 시작과 끝, 작업 시작과 완료, 결과가 나왔을 때, 막혔을 때 | `/note-tracking` (작업 중 자동 갱신) |
| `before-you-build` | 큰 과업을 만들기 전에 진짜 목표, 원자료와 높은 목표, 반박, 자기 판단 밖 검증을 정하고 과업을 다시 써서 진행 허가를 받는다 | 계약이나 공용 영역 변경, 여러 파트에 걸친 작업, 프롬프트나 평가 대본 변경, 한 시간 넘는 작업 | `/before-you-build <과업>` 또는 '착수 전 점검' |
| `be-ambitious` | Felix Rieseberg의 글을 옮긴 스킬(영어 원문 유지, MIT). 과업을 Altitude, Depth, Range로 키우고 다시 쓴 프롬프트를 낸다 | 결과가 평범해 보일 때, 더 높은 목표나 더 깊은 방법이 필요할 때 | `/be-ambitious <과업이나 프롬프트>` |

## 플러그인: `pr-review-toolkit`

Anthropic 공식 마켓플레이스(`claude-plugins-official`)의 플러그인이다. 소스는 저장소에 넣지 않고 `.claude/settings.json`의 `enabledPlugins`로 켠다.

- **무엇**: 리뷰 에이전트 여섯(코드 규칙, 테스트, 조용한 실패, 주석, 타입 설계, 단순화)으로 변경분을 나눠 본다.
- **언제**: PR을 열기 전이나 리뷰를 부탁받았을 때.
- **부르는 법**: `/pr-review-toolkit:review-pr` (관점만 고르려면 `code errors tests` 처럼 뒤에 붙인다. 생략하면 해당하는 관점 전부).
- **처음 한 번 설치**: 설정 파일은 플러그인을 켜기만 하고 내려받지는 않는다. 저장소 폴더에서 아래 중 하나를 한 번 실행한다.
  ```bash
  claude plugin install pr-review-toolkit@claude-plugins-official --scope project   # 터미널
  ```
  Claude Code 세션 안에서는 `/plugin install pr-review-toolkit@claude-plugins-official`. 공식 마켓플레이스는 터미널 대화형 세션을 처음 열 때 자동 등록되므로 따로 추가할 필요가 없다. VS Code 확장에서 목록이 비어 있으면 Marketplaces 탭에 `anthropics/claude-plugins-official`을 먼저 추가한다.
- **끄기**: 본인만 끄려면 `.claude/settings.local.json`(gitignore 대상)에 `"enabledPlugins": {"pr-review-toolkit@claude-plugins-official": false}`를 둔다.
