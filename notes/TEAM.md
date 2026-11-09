# 공용 노트 — 팀 전체

> 관리: 지원 (gitgutgit) · 마지막 업데이트: 2026-11-09 10:20
> 개인 진행은 각자 `notes/<GitHub>.md`. 여기는 **팀 전체가 같이 봐야 하는 것**만 적는다.
> 수정 규칙: `결정 사항` · `계약 변경 기록` · `P0 현황`은 팀장만 고친다. 나머지 팀원은 `공지 · 요청`에 **맨 아래 한 줄 추가**만 한다 (git 충돌 방지, 남의 줄 수정 금지).

## 일정
| 항목 | 시각 |
|---|---|
| 계약 고정 | `[HH:MM]` |
| 발표 전 동결 (이후 main merge는 팀장만) | `[HH:MM]` |
| 데모 리허설 | `[HH:MM]` |

## P0 현황
| P0 항목 | 담당 | 상태 |
|---|---|---|
| 회의방 + WebSocket | 태우 | 🟢 뼈대 동작 |
| Web Speech STT | 태우 | ⚪ 뼈대만 |
| Router / Editor | 한서 | 🟢 MOCK 동작, LIVE 미확인 |
| Op 엔진 (set_cell, add_row, insert_item, 결정·액션·충돌) | 태우 | 🟢 뼈대 동작 |
| B 화면 보드·노트 탭 | 태우 | ⚪ 빌드만 확인 |
| Google Sheets 동기화 | 태우·주현 | ⚪ 미구현 |
| 리플레이 | 태우 | 🟢 동작 |
| 입장 관문 (손동작 3개) | 한서 | ⚪ 서버 동작, 화면 미확인 |
| 확대 모드 + 확대·축소·포인터 | 한서 | ⚪ 뼈대만 |

## 결정 사항
- 11-09 프런트 스택: Vite + React + TS
- (14절 나머지는 결정되는 대로 여기에)

## 계약 변경 기록
| 시각 | 파일 | 내용 | 누가 | 승인 |
|---|---|---|---|---|
| 11-09 10:20 | events.py · docs.py · registry.py · types.ts | 초안 | gitgutgit | — |

## 공지 · 요청
- 11-09 10:20 gitgutgit: 뼈대 올라감. `CLAUDE.md` 읽고 시작, 자기 note 만들어 주세요.
- 11-09 10:40 Mal-Mi-Jal: Google 의존성 3개 추가(`pyproject.toml`·`uv.lock`) → `uv sync` 해 주세요. Google 로그인 안내 `server/sync/GOOGLE_SETUP.md`, 확인 `uv run python -m server.sync.google_auth`
- 11-09 12:20 Mal-Mi-Jal: PR #1(Google Sheets 동기화) main에 merge됨 → `uv sync` 필요. Windows Smart App Control 켜진 PC는 `pytest.exe`·rollup 네이티브가 막힘 → `uv run python -m pytest`, web은 Mal-Mi-Jal에게 문의
