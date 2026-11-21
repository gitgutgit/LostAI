<h1 align="center">
  <img src="web/public/favicon.svg" alt="LostAI" width="56" valign="middle" /> LostAI
</h1>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.11%2B-3776AB?style=flat&logo=python&logoColor=white" alt="Python 3.11+" />
  <img src="https://img.shields.io/badge/FastAPI-WebSocket-009688?style=flat&logo=fastapi&logoColor=white" alt="FastAPI + WebSocket" />
  <img src="https://img.shields.io/badge/React-TypeScript-3178C6?style=flat&logo=typescript&logoColor=white" alt="React + TypeScript" />
  <img src="https://img.shields.io/badge/Claude-Haiku%20%7C%20Sonnet-D97757?style=flat" alt="Claude Haiku and Sonnet" />
</p>

<p align="center">
  <sub><b>English</b> · <a href="docs/readme/README.ko.md">한국어</a></sub>
</p>

<p align="center">
  <strong>Say it in the meeting. The doc changes.</strong><br/>
  A real-time meeting agent that listens, edits your Google Sheets and Docs as people talk, and records who said what behind every change.
</p>

<h3 align="center"><a href="https://lostai-production.up.railway.app/"><ins>Try the demo</ins></a></h3>

<p align="center">
  <sub>This server is a public demo and comes with sample documents. Please do not connect private or sensitive documents to it.</sub>
</p>

<!-- TODO: demo video or screenshot -->

## Features

### Speak to edit
Each browser tab is one speaker, so no diarization is needed. Every utterance goes through a fast **router** (Claude Haiku) that labels it `ignore / capture / edit / command / ask`. Edits go to an **editor** (Claude Sonnet) that returns small, anchored operations such as "set this cell" or "insert this item". It never rewrites a whole section.

### Every change has a source
A change is an object with a lifecycle: `proposed → applied → approved | reverted`. Each one records who said it and when. You can undo a **specific** change, not only the last one, because the engine builds the inverse from the diff.

### Google Sheets & Docs, live
The screen updates first. Google catches up through a single outbox worker that runs calls one at a time; in the prototype, parallel calls broke with SSL errors. Each participant signs in with their own Google account. The Picker API (`drive.file` scope) means the app only sees files that person picks. Switching the meeting's source document needs the current owner's approval.

### Hands, not clicks
Hand tracking runs in the browser (MediaPipe in a Web Worker) and never goes through an LLM.
- **Join gate:** pass 3 random hand gestures to enter the room.
- **Shared signals:** thumbs up or down approves or reverts the latest change, and finger counts cast a vote.
- **Local view control:** zoom and pointer change only your own screen and are never sent to the server.

### One event log
The server appends one event for every state change and broadcasts only that delta. The screen, replay, latency measurements and debugging all read the same log.

### Works without keys
With `AGENT_MODE=MOCK`, a rule-based router and editor replace the LLM. You can build the UI, run tests and replay meetings with no API key at all.

## Quick start

Requirements: Python 3.11+, [uv](https://docs.astral.sh/uv/), Node.js 18+.

```bash
git clone https://github.com/gitgutgit/LostAI.git && cd LostAI
uv sync
cp .env.example .env                                  # AGENT_MODE=MOCK runs without any key
uv run uvicorn server.app:app --reload --port 8000    # server

cd web && npm install && npm run dev                  # UI at http://localhost:5173 (proxies /api and /ws to :8000)
```

- **UI only (no backend):** `http://localhost:5173/?fixture=sample_sprint_events`
- **Replay a scripted meeting with latency:** `uv run python -m server.replay fixtures/sample_sprint.jsonl`
- **Tests:** `uv run pytest -q`

> Browsers only open the microphone on `localhost` or `https`. To demo on another laptop, use an https tunnel or deploy it (see below).

## Configuration

Copy `.env.example` to `.env`. Never commit `.env`, `credentials.json` or `token.json`.

| Variable | What it does |
|---|---|
| `AGENT_MODE` | `MOCK` (rule-based, no key) or `LIVE` (calls the Anthropic API) |
| `ANTHROPIC_API_KEY` | Needed only for `LIVE` |
| `ROUTER_MODEL`, `EDITOR_MODEL` | Models for the router and the editor |
| `COMMIT_POLICY`, `DELAYED_COMMIT_SEC` | `immediate`, or `delayed` (apply after a few seconds unless someone objects) |
| `SEED` | Starting documents: `sprint` (sample) or `google` (your own Sheet/Doc) |
| `GOOGLE_SHEET_ID`, `GOOGLE_DOC_ID` | Documents to sync. Leave empty to turn sync off |
| `GOOGLE_OAUTH_CLIENT_*`, `GOOGLE_PICKER_API_KEY`, `GOOGLE_PROJECT_NUMBER` | Per-person Google sign-in and the document picker |
| `JOIN_SECRET` | Signs join tokens, so they survive a restart |

Step-by-step Google setup: [`server/sync/GOOGLE_SETUP.md`](server/sync/GOOGLE_SETUP.md).

## Deploy

A single container serves both the built UI and the server (`/api`, `/ws`). See [`server/deploy/RAILWAY.md`](server/deploy/RAILWAY.md) for Railway; the Dockerfile is in [`server/deploy/`](server/deploy/).

## How it works

```text
browser tab (= one speaker)            server (FastAPI + WebSocket)              external
 ├─ Web Speech STT  ── utterance ──▶  per-room queue ─▶ router ─▶ editor/asker ──▶ Anthropic API
 ├─ hand tracking   ── signals   ──▶  fast path (rules, no LLM)
 └─ view (events → UI) ◀─ deltas ──   op engine ─▶ event log (append-only)
                                                 └─▶ outbox worker ─────────────▶ Google Sheets / Docs
```

The full design, data contracts and the reasons behind each choice are in [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

```text
server/   FastAPI app, meeting room, op engine, agent (router · editor · asker), gestures, sync
web/      Vite + React + TypeScript: STT, hand tracking, views
eval/     evaluation scripts and blind scenarios
fixtures/ recorded event logs for replay
tests/    pytest suite
```

## Contributing

Issues and pull requests are welcome.

- Branch from the latest `main`: `git switch -c <github-id>/<topic> origin/main`. `main` changes only through pull requests.
- Keep one topic per pull request, and prefix commits with a tag such as `[server]`, `[ui]`, `[agent]`, `[sync]` or `[docs]`.
- The shared contracts (`server/events.py`, `server/model/docs.py`, `server/ops/registry.py` and their TypeScript copy `web/src/core/types.ts`) must change together.
- Run `uv run pytest -q` before you open a pull request.

More rules for working in this repo: [`CLAUDE.md`](CLAUDE.md).

## Contributors

<a href="https://github.com/gitgutgit/LostAI/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=gitgutgit/LostAI" alt="LostAI contributors" />
</a>

[@gitgutgit](https://github.com/gitgutgit) · [@Mal-Mi-Jal](https://github.com/Mal-Mi-Jal) · [@ProfessionalSeaweedDevourer](https://github.com/ProfessionalSeaweedDevourer) · [@HanseoSONNY](https://github.com/HanseoSONNY) · [@77SONNY77](https://github.com/77SONNY77)

LostAI started at the c0mpiled-17 Seoul hackathon (November 2026) and is now developed in the open.

## Privacy

[`web/public/privacy.html`](web/public/privacy.html) explains what the app reads from Google and what it stores.

## License

<!-- TODO: add a LICENSE file (e.g. MIT) and update this section. -->
No license has been chosen yet.
