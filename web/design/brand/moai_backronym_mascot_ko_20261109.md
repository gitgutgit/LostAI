# MOAI 역두문자와 마스코트 (2026-11-09 10:20)

> 요청: Eric 10:14, 모아이(moai)와 비슷한 소리의 철자로 영미권 심사진을 위한 역두문자 브레인스토밍, 비즈니스 냄새가 강한 것은 제외, 모아이를 아이콘과 에이전트 마스코트로 반영.
> 후보 표: /Users/eric.j.park/Documents/GitHub/meeting-agent-poc/design/brand/candidates_ko_20261109.md
> 판독 원문: /Users/eric.j.park/Documents/GitHub/meeting-agent-poc/design/brand/judge_backronym/out/

## 1. 판단 밖 검증 (결과를 보기 전 10:20 고정)

- 판독자: `claude -p --model sonnet`, 맥락 없음, 역두문자마다 3회. 질문 셋: 이 제품이 무엇을 할 것 같은가(한 문장), 사업 용어 냄새 1(장난스럽고 사람 같음)~5(기업 사업 용어), 2분 영상에서 한 번 듣고 풀이를 기억하겠는가.
- 통과: 냄새 점수 중앙값 2 이하, 그리고 3회 중 2회 이상이 회의(논의, 팀)와 정하기 또는 기록하기를 함께 말함.
- 보조 지표: 기억 yes 수(3회 중).
- 대조군: B16 'Maximize Operational Alignment Insights'(일부러 사업 용어로 지음). 판독자가 이것을 4 이상으로 매기지 않으면 판독자 자체가 냄새를 못 가리는 것으로 보고 결과를 쓰지 않는다.
- 추가 시험: 소리만 듣고 적기('MOH-eye'로 들린 이름의 철자, 3회), 단어 연상('Moai'에서 떠오르는 것, 3회).

## 2. 만드는 방식

- 글자별 단어 목록에서 조합했다. 사업 용어(Align, Insight, Optimize, Operations, Agenda, Minutes, Intelligence, Assistant, Action)는 처음부터 뺐다.
  - M: Meet, Many, Mouths, Mumble, Mull, Mic, Mark, Make, Moments, Mostly, My, Minority
  - O: Object, Opinions, Open, Out loud, Our, On, Of, Observes, Opens
  - A: Agree, Ayes, Answers, Arguments, Asks, Acknowledged, All, Agreement, AI
  - I: Ink, Inked, Inline, Instead, In, Inks
- 세 갈래로 나눴다.
  - 흐름형: 제품이 하는 일을 네 동사로(B02, B03, B15). 말한다, 반대한다, 정한다, 적는다.
  - 태도형: 에이전트가 정하지 않는다는 원칙을 이름에 넣음(B01 Mostly Observes, Asks Instead, B10 Minority Opens, All In, B06 My Objection, Acknowledged, Inked).
  - MO + AI형: 끝 두 글자를 AI 그대로 둠(B12, B13).
- 비슷한 소리의 다른 철자(Mowai, Moeye, Mo-AI)는 석상 마스코트와의 연결이 끊겨 목록에서 뺐다. 소리만 듣고 적기 시험 결과로 이 판단을 확인한다.

## 3. 결과

- 10:19 1차 판독 54회 폐기: 판독자를 저장소 폴더 안에서 띄워 프로젝트 맥락이 실렸다(단어 연상 답 3개가 'this repo', 'this project'를 언급, 1개는 한국어 답). 원문은 judge_backronym/out_contaminated_cwd_in_repo/ 에 남김. 저장소 밖 빈 폴더에서, 영어로 답하라는 지시를 붙여 같은 54회를 다시 돌림.
- 10:23 2차 판독 54회도 폐기: 빈 폴더가 세션 임시 폴더 아래라 경로에 'meeting-agent-poc'가 들어 있었다. 판독자가 경로를 보고 회의 도구로 짐작했다(대조군 B16 한 답이 'captures team meetings', 단어 연상 한 답이 'a product named Moai that mostly listens'). 원문은 judge_backronym/out_contaminated_cwd_path_name/. 경로에 이름이 없는 시스템 임시 폴더(mktemp)에서 맥락 점검(회의, Moai 관련 맥락 없음 확인) 뒤 3차 실행. 전역 사용자 지시는 여전히 실리므로 영어 답 지시를 유지.

### 3차 판독 결과 (10:26, 유효)

- 판독자 유효성: 대조군 B16 냄새 4, 4, 5(기준 4 이상 충족). 사업 용어를 가려낸다.
- 통과 기준(1절): 냄새 중앙값 2 이하 그리고 회의(논의, 팀)와 정하기 또는 기록하기를 함께 말한 답 2/3 이상.

| 번호 | 풀이 | 냄새 3회 | 중앙값 | 회의+정함/기록 | 기억 yes | 판정 | 판독자 한 줄(대표 답) |
|---|---|---|---|---|---|---|---|
| B01 | Mostly Observes, Asks Instead | 3, 2, 3 | 3 | 1/3 | 0/3 | 탈락 | watches, asks you questions instead of acting |
| B02 | Meet, Object, Agree, Ink | 4, 2, 3 | 3 | 3/3 | 1/3 | 탈락(냄새) | team meets, raises objections, reaches agreement, records the decision |
| **B03** | **Mumble, Object, Agree, Ink** | 3, 2, 2 | **2** | **3/3** | 1/3 | **통과** | people voice rough ideas, raise objections, agree, record the final decision |
| B04 | Many Opinions, Agreed In ink | 3, 2, 4 | 3 | 3/3 | 1/3 | 탈락(냄새) | gathers opinions, records the agreed decision |
| **B05** | **Mouths Open, Answers Inked** | 2, 2, 2 | **2** | **2/3** | **2/3** | **통과** | captures spoken conversation into written records (받아쓰기 도구로 읽힘) |
| B06 | My Objection, Acknowledged, Inked | 4, 3, 3 | 3 | 3/3 | 0/3 | 탈락(냄새) | logs objections, formally signed off |
| B07 | Make Our Arguments Ink | 3, 3, 3 | 3 | 3/3 | 0/3 | 탈락(냄새) | turns debates into written decisions |
| B08 | Mark Our Agreements Inline | 2, 3, 3 | 3 | 2/3 | 0/3 | 탈락(냄새) | mark up agreed decisions inside documents |
| B09 | Mouths, Opinions, Ayes, Ink | 3, 3, 3 | 3 | 3/3 | 0/3 | 탈락(냄새) | collects opinions and approvals, records decisions |
| B10 | Minority Opens, All In | 3, 3, 3 | 3 | 1/3 | 0/3 | 탈락 | a dissenter opens, the whole team commits |
| **B11** | **Mic On, Arguments Inked** | 2, 3, 2 | **2** | **3/3** | 1/3 | **통과** | records meetings, turns the arguments into written decisions |
| **B12** | **Many Opinions, AI Inks** | 2, 2, 2 | **2** | **3/3** | 0/3 | **통과** | many people's opinions, AI writes them into one document (1회는 'summary or decision', AI가 정한다는 읽힘 위험) |
| B13 | Mouths Open, AI Inks | 2, 3, 3 | 3 | 2/3 | 0/3 | 탈락(냄새) | spoken input turned into written records by AI |
| B14 | Moments Of Agreement, Inked | 3, 3, 2 | 3 | 3/3 | 1/3 | 탈락(냄새) | records the moments everyone agrees |
| B15 | Mull, Object, Agree, Ink | 3, 3, 3 | 3 | 3/3 | 0/3 | 탈락(냄새) | mull, raise objections, record the agreed result |
| B16 | (대조군) Maximize Operational Alignment Insights | 4, 4, 5 | 4 | 0/3 | 0/3 | 대조군 | aligned operations, actionable insights |

- 통과 넷: B03 Mumble, Object, Agree, Ink / B05 Mouths Open, Answers Inked / B11 Mic On, Arguments Inked / B12 Many Opinions, AI Inks.
- 통과 넷 중 '엇갈리면 멈추고 방이 정한다'를 읽어 낸 것은 B03(Object, Agree)뿐이다. B05와 B11은 회의 받아쓰기 도구로 읽혀 경쟁 제품과 같은 줄에 선다. B12는 1회가 AI가 결정을 쓴다고 읽었다.
- 기억 yes는 모두 낮다(최고 B05 2/3). 한 번 듣고 풀이까지 기억시키기는 어렵다는 뜻이고, 영상에서는 풀이를 소리로 말하기보다 끝 카드에 글로 보여 주는 쪽이 판독과 맞는다(W3 세로 두문자).
- 소리 듣고 적기('MOH-eye'): Moai 2, Moi 1.
- 단어 연상 'Moai': 3/3 이스터섬 석상, 그중 2회는 '말없이 지켜본다(silent, watching)'. 🗿 밈을 말한 답은 0/3. 1회는 한국어로 답함(전역 지시 탓, 내용은 같음).
- 원문: /Users/eric.j.park/Documents/GitHub/meeting-agent-poc/design/brand/judge_backronym/out/

## 4. 마스코트 방향 (그리기 전 메모)

- 모아이가 맞는 이유(제품 원칙과의 대응):
  - 말이 없다: 에이전트는 소리 내 말하지 않는다(정체성 초안 4절 약속 1).
  - 귀가 길다: 실제 모아이 석상은 귀가 길게 조각되어 있다. 듣는 쪽이 일이다.
  - 사람이 아니다: 인종, 성별이 드러나지 않는 픽토그램 조건(지시서 4절 T5)을 자연스럽게 지킨다.
  - 줄지어 선다: 석상은 여러 개가 한 줄로 서 있다. 회의 참가자 줄, 표결 화면에 그대로 쓸 수 있다.
- **10:20 Eric 판정: 표정 아이디어 채택('매우 좋다, 기록해야 한다').** 아래 다섯 상태를 마스코트 표정 정본으로 둔다. 렌더와 영상 반영은 주 세션 몫이다(지시서 7절).
- 상태 표정(화면 상태와 1대1, 얼굴은 눈썹과 눈 두 획만 바꾼다):
  - 듣는 중: 기본 무표정
  - 쓰는 중: 눈 아래로(문서를 봄)
  - 엇갈림 감지, 쓰기 멈춤: 한쪽 눈썹 올림
  - 표결 중: 눈 감음(보지 않는다, 추천하지 않는다)
  - 결정 기록: 고개 끄덕임 한 번(움직임 1회)
- 색: 실측 화면 색만 쓴다. 먹 #17212B 실루엣, 노랑 #F3C316 강조(엇갈림 때 눈썹), 바탕 흰색 또는 회녹 #CDD6D0. 단색판은 먹 한 색.
- 16 px: 머리 실루엣(길쭉한 사각에 무거운 이마와 코) 하나만 남는다. 얼굴 표정은 32 px 이상에서만.

## 4-1. 영어 철자를 살린 타이포그래피 (10:20 Eric 제안)

- 제안: MOAI라는 영어 철자 자체를 살린 글자 표시(워드마크)를 만든다.
- 시안 방향(실행 세션이 그려 보는 것, 서체는 화면과 같은 Barlow Condensed 700):
  - W1 끝 두 글자 강조: MO 먹색 + AI 노랑 칩. 이름 안에 AI가 들어 있다는 것이 보인다.
  - W2 I 자리에 석상: 마지막 I를 길쭉한 모아이 마크로 바꾼다. 석상의 세로로 긴 몸이 I와 닮았다.
  - W3 세로 두문자: 끝 카드용. 첫 글자만 굵게 M, O, A, I를 세로로 쌓고 옆에 풀이(판독 통과한 역두문자)를 붙인다.
- 파일: /Users/eric.j.park/Documents/GitHub/meeting-agent-poc/design/brand/logo/

## 5. 위험

- 밈: 이모지 U+1F5FF(🗿)는 영어권에서 무표정, 어이없음 반응으로 쓰인다. 영상에서 웃음을 줄 수도, 장난감처럼 보일 수도 있다. 단어 연상 시험으로 본다.
- 문화: 모아이는 라파누이 사람들에게 조상을 뜻하는 신성한 조각이다. 2024년 칠레에서 모아이 그림을 쓴 술 상표가 상표 다툼에서 졌다는 보도가 있다(The Clinic 2024-01-01, https://www.theclinic.cl/2024/01/01/pisco-capel-moai-inapi-derecho-marca/ , 본문은 403으로 못 열고 검색 요약만 봄. 판결 내용은 확인 못 함). 해커톤 범위에서는 막는 사유가 아니지만, 마스코트를 우스꽝스럽게 망가뜨리는 연출(넘어뜨리기, 부수기)은 피한다.
