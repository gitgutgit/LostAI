# 데모 대본 (`▶ 대본 자동 재생`)

회의 화면 왼쪽 아래 **🧪 테스트 대본**에서 고른 시나리오(시드)의 대본을 한 줄씩 회의방에 넣는다. (`server/demo.py`)

## 어디에, 어떤 이름으로

| 무엇 | 파일 | 형식 |
|---|---|---|
| 시나리오 시작 문서 (시드) | `server/model/seeds/<이름>.json` | 시트 + 노트 문서 JSON (예: `poc_wbs_v1_0_en.json`) |
| 그 시나리오의 대본 | `server/model/scripts/<같은 이름>.jsonl` | **JSONL**: 한 줄에 JSON 하나 |

이름이 같아야 이어진다. 예시 대본: `poc_wbs_v1_0_en.jsonl`(표결 → 동점 → 재표결 → 회의 종료). 예: 시드 `poc_wbs_v1_0_en.json` ↔ 대본 `poc_wbs_v1_0_en.jsonl`. 대본이 없으면 ▶ 버튼이 줄 수 0으로 꺼져 있다.

## 줄 형식

```jsonl
{"speaker": "Jiwon", "text": "Okay, let's start the WBS check.", "delay": 2.0}
{"speaker": "Haeun", "text": "Integration testing needs more time. Make it ten days.", "delay": 3.0}
{"speaker": "Mina", "gesture": "Fingers_3"}
{"speaker": "Junho", "gesture": "Fingers_1"}
{"wait": 9}
{"speaker": "Jiwon", "text": "Okay, that's it for today. Let's end the meeting.", "delay": 2.0}
```

- `speaker`: 말하는 사람 이름. 시트의 Owner 이름과 맞추면 칩이 자연스럽다.
- `text`: 말. 회의 언어로 쓴다(영어 시드면 영어).
- `delay`: 선택. **자동 재생은 이 값을 쓰지 않는다.** 자동 재생은 글자 수만큼 읽는 시간(최대 3초)을 기다렸다 말하고, 에이전트가 그 줄을 다 처리한 뒤 다음 줄로 간다. `delay`는 `server.replay`를 실시간으로 돌릴 때만 쓴다.
- `gesture`: 말 대신 손 신호. `Fingers_1`~`Fingers_4`(표결), `Thumb_Up`(승인), `Thumb_Down`(되돌림), `T_Shape`(일시정지).
  손 신호 줄은 직전 줄 처리가 끝나면 0.3초 간격으로 바로 이어 보낸다. 표결은 **2초 안에 두 사람 이상**이 손가락을 보여야 열린다 → 표결 손가락 줄은 붙여 쓴다.
- `wait`: 화면을 보여 줄 초. 앞 줄 처리가 끝난 뒤 그만큼 쉰다. 표결 결과(마지막 표 뒤 10초에 마감 + 볼 시간, 예시 대본은 14초), 끝 화면에 쓴다. `{"wait": 9}`만 있는 줄도 된다.
- 표결 값: 찬반 카드(선택지가 Yes/No뿐)는 3 = good, 2 = okay, 1 = no. 선택지 카드는 번호 고르기. 말로도 된다("good", "two", "option two").
- 회의 끝 화면(CLOSED)은 "Let's end the meeting", "That's it for today" 같은 줄로 띄운다.

## 확인

```bash
uv run python -m server.replay server/model/scripts/<이름>.jsonl   # 대본을 서버 없이 돌려 보고 변경 수를 본다
```
