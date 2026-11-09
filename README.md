# 회의 에이전트 — Say it in the meeting. The doc changes.

c0mpiled-17 Seoul 해커톤 본선. 설계: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) · 작업 규칙: [`CLAUDE.md`](CLAUDE.md)

## 빠른 시작

```bash
uv sync && cp .env.example .env                       # AGENT_MODE=MOCK 이면 키 없이 동작
uv run uvicorn server.app:app --reload --port 8000    # 서버
cd web && npm install && npm run dev                  # 화면 http://localhost:5173
```

- 백엔드 없이 화면만: `http://localhost:5173/?fixture=sample_sprint_events`
- 대본 리플레이 + 지연: `uv run python -m server.replay fixtures/sample_sprint.jsonl`
- 테스트: `uv run pytest -q`

## 파트별 현황 (각자 자기 칸만 채운다)

| 파트 | 담당 | 상태 |
|---|---|---|
| 기능 (agent · gestures · eval) | 한서(메인) · 주현(서브) | |
| 서버·UI (app · room · ops · sync · web) | 태우(메인) · 주현(서브) | |
| 공용 계약 | 지원(팀장) | |
