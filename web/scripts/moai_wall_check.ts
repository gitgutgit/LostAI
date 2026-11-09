// V3: the MOAI status light and the decision wall cards must never disagree. Replays the recorded fixture and a
// synthetic conflict, vote and pause sequence through both moaiSignal (the light) and liveWall (the cards).
// Run from web/:
//   node_modules/.bin/esbuild scripts/moai_wall_check.ts --bundle --platform=node --format=cjs --loader:.css=empty --outfile=/tmp/w.cjs && node /tmp/w.cjs
import { readFileSync } from "node:fs";
import { moaiSignal } from "../src/views/brand/moaiState";
import { liveWall } from "../src/views/wall/live";
import { initialView, type RoomView } from "../src/core/reducer";

const seed = JSON.parse(readFileSync("public/fixtures/seed_sprint.json", "utf8"));
const base = seed.state ?? seed;
let fail = 0, n = 0;
const seen: Record<string, number> = {};

function judge(label: string, v: RoomView) {
  n++;
  const s = moaiSignal(v);
  const key = s.base === "paused" ? (s.conflict ? "paused:conflict" : "paused:command") : s.base;
  seen[key] = (seen[key] ?? 0) + 1;
  const w = liveWall(v);
  const voting = w.cardB?.take === "count";
  const question = !!w.cardA;
  const paused = w.cardB?.flap === "PAUSED";
  const rules: [string, boolean, boolean][] = [
    ["vote light <=> countdown card", s.base === "vote", voting],
    ["conflict light <=> question card (not voting, not paused)", s.base === "paused" && s.conflict, question && !voting && !paused],
    ["pause light <=> PAUSED card", s.base === "paused" && !s.conflict, paused],
  ];
  for (const [rule, a, b] of rules) if (a !== b) { fail++; console.log(`MISMATCH ${label}: ${rule} (light ${s.base}/${s.conflict}, cards A=${question} B=${w.cardB?.flap})`); }
}

// 1) recorded fixture
const ev = readFileSync("public/fixtures/sample_sprint_events.jsonl", "utf8").trim().split("\n").map((l) => JSON.parse(l));
for (let i = 0; i < ev.length; i++) judge(`fixture seq ${ev[i].seq}`, { ...initialView, connected: true, state: base, events: ev.slice(0, i + 1) });

// 2) synthetic conflict, vote, resolution and pause
const e = (seq: number, type: string, payload: any = {}, refs: any = {}) => ({ seq, ts: seq, type, actor: "x", refs, payload }) as any;
const cf = { conflict_id: "cf1", topic: "SSO estimate", positions: [{ who: "Mina", says: "3 days" }, { who: "Junho", says: "5 days" }], resolved: false, resolution: null };
const open = { ...base, conflicts: [cf] };
const done = { ...base, conflicts: [{ ...cf, resolved: true, resolution: "5 days" }] };
const steps: [any, any, boolean][] = [
  [e(101, "agent.progress", { stage: "editing" }), base, false],
  [e(102, "change.applied", { targets: [], ops: [{ op: "open_conflict", topic: "SSO estimate" }] }), open, false],
  [e(103, "vote.opened", {}, { vote_id: "v1" }), open, false],
  [e(104, "vote.cast", { n: 2 }, { vote_id: "v1" }), open, false],
  [e(105, "vote.closed", { votes: { Mina: 2, Junho: 2 } }, { vote_id: "v1" }), open, false],
  [e(106, "agent.progress", { stage: "editing" }), open, false],
  [e(107, "change.applied", { targets: [], ops: [{ op: "resolve_conflict", conflict: "cf1", resolution: "5 days" }] }), done, false],
  [e(108, "agent.progress", { stage: "routing" }), done, false],
  [e(109, "agent.progress", { stage: "done" }), done, true],
];
const acc: any[] = [...ev];
for (const [event, state, pausedCmd] of steps) {
  acc.push(event);
  judge(`synthetic seq ${event.seq} ${event.type}`, { ...initialView, connected: true, state, events: [...acc], paused: false });
  if (pausedCmd) judge(`synthetic seq ${event.seq} + pause command`, { ...initialView, connected: true, state, events: [...acc], paused: true });
}
console.log(fail ? `${fail} mismatch(es) in ${n} states` : `ok: ${n} states (${ev.length} fixture + synthetic), light and cards agree. Light states seen: ${JSON.stringify(seen)}`);
process.exit(fail ? 1 : 0);
