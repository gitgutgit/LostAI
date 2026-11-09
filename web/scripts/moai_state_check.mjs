// MOAI state check: replays events and compares the derived mascot state with a hand-written table.
// Run: node --experimental-strip-types scripts/moai_state_check.mjs   (Node 22.6+, no test runner needed)
import { readFileSync } from "node:fs";
import { moaiSignal } from "../src/views/brand/moaiState.ts";

let fail = 0;
const check = (label, got, want) => { if (got !== want) { fail++; console.log(`FAIL ${label}: got ${got}, want ${want}`); } };

// 1) recorded fixture (no conflicts, no votes): writing only from editing to applied, listening otherwise
const ev = readFileSync(new URL("../public/fixtures/sample_sprint_events.jsonl", import.meta.url), "utf8")
  .trim().split("\n").map((l) => JSON.parse(l));
const writing = new Set([11, 12, 13, 16, 17, 18, 21, 22, 23, 26, 27, 28, 31, 32, 33, 39]);
for (let i = 0; i < ev.length; i++) {
  const seq = ev[i].seq;
  check(`fixture seq ${seq} ${ev[i].type}`, moaiSignal({ events: ev.slice(0, i + 1), state: null, paused: false }).base, writing.has(seq) ? "writing" : "listening");
}

// 2) synthetic conflict and vote sequence
const e = (seq, type, payload = {}, refs = {}) => ({ seq, ts: seq, type, actor: "x", refs, payload });
const open = { conflicts: [{ conflict_id: "cf1", topic: "SSO estimate", positions: [], resolved: false, resolution: null }] };
const done = { conflicts: [{ ...open.conflicts[0], resolved: true, resolution: "5" }] };
const seqs = [
  [e(1, "agent.progress", { stage: "editing" }), null, "writing", null],
  [e(2, "change.applied", { ops: [{ op: "open_conflict", topic: "SSO estimate" }] }), open, "paused", null],
  [e(3, "vote.opened", {}, { vote_id: "v1" }), open, "vote", null],
  [e(4, "vote.cast", { n: 3 }, { vote_id: "v1" }), open, "vote", null],
  [e(5, "vote.closed", { votes: {} }, { vote_id: "v1" }), open, "paused", null],
  [e(6, "agent.progress", { stage: "editing" }), open, "paused", null],
  [e(7, "change.applied", { ops: [{ op: "resolve_conflict", conflict: "cf1", resolution: "5" }] }), done, "writing", 7],
  [e(8, "agent.progress", { stage: "routing" }), done, "listening", 7],
];
const acc = [];
for (const [event, state, want, wantDecided] of seqs) {
  acc.push(event);
  const s = moaiSignal({ events: [...acc], state, paused: false });
  check(`synthetic seq ${event.seq} ${event.type}`, s.base, want);
  check(`synthetic seq ${event.seq} decidedSeq`, s.decidedSeq, wantDecided);
}
const p = moaiSignal({ events: [...acc], state: done, paused: true });
check("pause command", `${p.base}/${p.conflict}`, "paused/false");

console.log(fail ? `${fail} mismatch(es)` : `ok: ${ev.length} fixture events + ${seqs.length + 1} synthetic checks, 0 mismatches`);
process.exit(fail ? 1 : 0);
