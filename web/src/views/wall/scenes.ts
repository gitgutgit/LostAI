// 렌더 v0.4의 장면 11개(d1 d2 s2..s8 r1 s9)를 WallState로 옮긴 견본. 시안 index.html의 docRows와 ST를 그대로 옮겼다.
// 영상 촬영, 화면 개발, 픽셀 대조(시안 PNG와 비교)에 쓴다. 실시간 화면은 live.ts가 같은 모양을 만든다.
// author: ProfessionalSeaweedDevourer
import type { CardA, CardB, CellVal, Chip, DocModel, DocRow, Person, Rich, SlotState, Utter, WallState } from "./types";

export const SCENES = ["d1", "d2", "s2", "s3", "s4", "s5", "s6", "s7", "s8", "r1", "s9"] as const;
export type SceneId = (typeof SCENES)[number];

const v = (x: string): CellVal => ({ v: x });
const struck = (old: string, x: string, br = false): CellVal => ({ old, v: x, br });
const C = (t: string, r?: string, cls?: Chip["cls"]): Chip => ({ t, r, cls });
const R = (r: string) => ({ ref: r });

// 문서에 실제로 쓴 횟수 (장면마다 누적). 시안 NOTES.md 표와 같다.
const EDITS: Record<SceneId, number> = { d1: 6, d2: 9, s2: 9, s3: 9, s4: 9, s5: 9, s6: 9, s7: 9, s8: 13, r1: 20, s9: 22 };

const BASE: [string, string, string, string, string, string, string][] = [
  ["1.3", "Feature spec", "Jiwon", "11-16", "11-20", "5", "60%"],
  ["1.5", "UI wireframe", "Mina", "11-16", "11-20", "5", "40%"],
  ["2.1", "Cloud and network", "Junho", "11-19", "11-23", "3", "To do"],
  ["2.11", "Payment screen", "Mina", "12-16", "12-21", "4", "To do"],
  ["2.12", "Admin page", "Seoyeon", "12-03", "12-10", "6", "To do"],
  ["3.1", "Unit test", "Taeho", "12-16", "12-18", "3", "To do"],
  ["3.2", "Integration test", "Haeun", "12-22", "12-28", "5", "To do"],
  ["3.3", "Perf and load test", "Junho", "12-29", "12-31", "3", "To do"],
  ["3.4", "UAT", "Haeun", "01-01", "01-07", "5", "To do"],
  ["3.5", "Launch prep", "Jiwon", "01-08", "01-14", "5", "To do"],
];

function docRows(id: SceneId): DocRow[] {
  const k = SCENES.indexOf(id);
  const rows: DocRow[] = BASE.map(([w, t, o, s, e, d, st]) => ({ w, t, o: v(o), s: v(s), e: v(e), d: v(d), st: v(st), src: [], fresh: {}, memo: null }));
  const by = (w: string) => rows.find((r) => r.w === w)!;
  // d1: L3, L4 (잘못 들은 18%를 Jiwon이 되돌림), L5, L6, L12
  by("1.3").st = v("90%"); by("1.3").src = [C("Jiwon L3", "L3")];
  by("1.5").st = struck("18%", "80%"); by("1.5").src = [C("Mina L4", "L4"), C("undone by Jiwon", "", "undo")];
  by("2.1").st = v("In progress"); by("2.1").src = [C("Junho L5", "L5")];
  const r32 = by("3.2"); r32.d = v("10"); r32.e = v("01-04"); r32.src = [C("Haeun L6", "L6")];
  if (k === 0) { r32.d = struck("5", "10"); r32.fresh = { d: 0, e: 0 }; }
  const wh: DocRow = { w: "2.13", t: "Payment webhook", o: v("Junho"), s: v(""), e: v(""), d: v("3"), st: v("To do"), src: [C("Junho L12", "L12")], fresh: {}, memo: null, newrow: true, rowfresh: k === 0 };
  rows.splice(rows.indexOf(by("2.12")) + 1, 0, wh);
  if (k === 0) by("3.3").vt = true; // 카드 A가 이 칸에서 떠오른다 (d1 -> d2)
  // d2 이후: 3.3 엇갈림, 3.5 메모 (L11 캠페인)
  if (k >= 1 && k < 8) {
    const r = by("3.3");
    r.cf = { a: { who: "Junho L7", r: "L7", v: "with 3.2", short: "with" }, b: { who: "Jiwon L8", r: "L8", v: "after 3.2", short: "after" } };
    r.src = [C("Q2 open", "", "tag")]; r.tall = true;
    if (k === 5) r.hl = true;
  }
  if (k >= 1) by("3.5").memo = { t: "Campaign 01-14", c: C("Mina L11", "L11"), bad: true };
  if (k === 6) { // 유령 값: 선택지별 끝 날짜 (CPM)
    by("3.2").gh = ["01-04", "01-04"];
    by("3.3").gh = ["12-24", "01-07"];
    by("3.4").gh = ["01-11", "01-14"];
    const r35 = by("3.5"); r35.gh = ["01-18", "01-21"]; r35.ghbad = true; r35.ghref = "L10";
  }
  if (k >= 8) { // Q2 결정: 순차(FS). 3.3, 3.4, 3.5 재계산
    const r = by("3.3"); r.vt = k === 8;
    r.s = v("01-05"); r.e = v("01-07"); r.src = [C("Haeun L16", "L16")];
    r.memo = { t: "Running it alongside integration would launch earlier.", c: C("Junho L7, confirmed", "L7", "ok") };
    const a = by("3.4"), b = by("3.5");
    a.s = v("01-08"); a.e = v("01-14"); b.s = v("01-15"); b.e = v("01-21"); b.src = [C("Haeun L10", "L10")];
    if (k === 8) {
      r.s = struck("12-29", "01-05", true); r.e = struck("12-31", "01-07", true); r.fresh = { s: 0, e: 0 }; r.tall = true;
      r.memo.fresh = true;
      a.s = struck("01-01", "01-08", true); a.e = struck("01-07", "01-14", true); a.fresh = { s: 200, e: 200 }; a.tall = true;
      b.s = struck("01-08", "01-15", true); b.e = struck("01-14", "01-21", true); b.fresh = { s: 400, e: 400 }; b.tall = true;
      rows.splice(0, 1); // 1.3은 위로 넘어감
    }
  }
  if (k >= 9) { // L13~L19 뒤, Q4
    rows.splice(0, 3); // 1.3, 1.5, 2.1은 위로 넘어감
    by("2.12").st = v("v1.1"); by("2.12").src = [C("Jiwon L13", "L13")];
    const p = by("2.11"); p.d = v("3"); p.o = v("Mina, Seoyeon"); p.wrapO = true; p.src = [C("Mina L14", "L14"), C("Jiwon L15", "L15")];
    by("3.5").memo = { t: "Beta 01-14, launch 01-21", c: C("Jiwon L17", "L17") };
    by("3.3").memo = null; by("3.3").src = [C("Haeun L16", "L16"), C("memo L7", "L7", "ok")];
    rows.push({ w: "4.1", t: "Order event logging", o: v("Junho"), s: v(""), e: v(""), d: v("2"), st: v("To do"), src: [C("Junho L19", "L19")], fresh: {}, memo: null, newrow: true });
    rows.push({ w: "4.2", t: "Revenue dashboard", o: v("Junho"), s: v(""), e: v(""), d: v("4"), st: v("Parked"), src: [C("Junho L19", "L19"), C("Jiwon L20", "L20")], fresh: { st: 0 }, newrow: true,
      memo: { t: "After launch. Owner Junho. Q4 parked." }, hl: false });
  }
  return rows;
}

function doc(id: SceneId): DocModel {
  const k = SCENES.indexOf(id);
  const note: Rich = id === "s6"
    ? ["Values from current data (CPM, workdays). ", { bad: "Campaign 01-14" }, " ", R("L11")]
    : id === "d1" ? ["Last: L12 added row 2.13. L2 ignored: small talk."]
    : k >= 9 ? ["Rows 1.x and 2.1 above. Q2 written to 3.3, 3.4, 3.5."]
    : ["Each edit shows who said it and the line."];
  return {
    title: "WBS", subtitle: "Mobile order app v1.0", edits: EDITS[id], undone: 1, note,
    ghost: id === "s6" ? { cols: ["1 parallel", "2 after"] } : undefined,
    rows: docRows(id),
  };
}

// 카드 A
const Q2A = (side1?: { cost: Rich; sub: Rich }, side2?: { cost: Rich; sub: Rich }): CardA => ({
  q: "Q2", title: "Perf test: when?", fromCell: true,
  options: [
    { n: 1, name: "In parallel", src: ["with 3.2. Junho ", R("L7")], side: side1 },
    { n: 2, name: "After integration", src: ["as in WBS. Jiwon ", R("L8")], side: side2 },
  ],
});
const COST1 = { cost: ["Launch 01-18"], sub: [{ bad: "Breaks 01-14" }, R("L11")] } satisfies { cost: Rich; sub: Rich };
const COST2 = { cost: ["Launch 01-21", R("L10")], sub: [{ bad: "Breaks 01-14" }, R("L11")] } satisfies { cost: Rich; sub: Rich };
const Q4A: CardA = { q: "Q4", title: "Revenue dashboard", reframe: { old: "Build it in v1.0?", now: "Needed on launch day?", vt: "Vote 1 scattered. Rewritten. Vote 2 scattered." } };

const SAY: Record<string, Utter> = {
  L2: { line: "L2", who: "Junho", text: "Sure, let me share my laptop screen." },
  L12: { line: "L12", who: "Junho", text: "Add a payment webhook task. Backend, me, 3 days." },
  L7: { line: "L7", who: "Junho", text: "I can run the perf test alongside integration." },
  L10: { line: "L10", who: "Haeun", text: "Then launch lands on January 21." },
  L11: { line: "L11", who: "Mina", text: "Too late. Marketing booked the campaign for January 14." },
  L16: { line: "L16", who: "Haeun", text: "Perf test after integration, as Jiwon said." },
  L20: { line: "L20", who: "Jiwon", text: "The dashboard can wait until after launch. Park it." },
  L24: { line: "L24", who: "Jiwon", text: "That is it for today. Thanks, everyone." },
};

const NAMES = ["Jiwon", "Mina", "Junho", "Haeun"];
const ppl = (xs: [string, Person["tone"]][]): Person[] => xs.map(([status, tone], i) => ({ name: NAMES[i], status, tone }));
const all = (status: string, tone: Person["tone"] = "") => ppl([[status, tone], [status, tone], [status, tone], [status, tone]]);

interface Spec {
  b: CardB; A: CardA | null; said: Utter[]; log: Rich; people: Person[];
  glyph?: WallState["glyph"]; lit: string[]; dec: number; park: number; now?: string; turn?: number; big?: boolean;
}

const ST: Record<SceneId, Spec> = {
  d1: { A: null, b: { flap: "LISTENING", msg: { kind: "headline", big: ["Writing what the team says"], sub: ["Small talk is ignored. Any edit can be undone."], subTop: 4 } },
    said: [SAY.L12], log: ["L12 added row 2.13. L4 18% undone by Jiwon. L2 ignored: small talk."],
    people: all("here"), lit: [], dec: 1, park: 0, now: "listening" },
  d2: { A: Q2A(), b: { flap: "ASK", msg: { kind: "facts", title: "Facts not on the table?", chips: [C("L6 Integration ends 01-04", "L6"), C("L11 Campaign 01-14", "L11")] } },
    said: [SAY.L11], log: ["3.3 has two values (L7, L8), so Q2 opened. Options come from team words only."],
    people: all("here"), lit: ["L6", "L11"], dec: 1, park: 0 },
  s2: { A: Q2A(), big: true, glyph: "cam", b: { flap: "3 2 1", off: [0, 4], take: "count", msg: { kind: "countdown", q: "Q2", title: "Perf test: when?", prompt: "Show 1 or 2 fingers to your own camera, all at once." } },
    said: [SAY.L11], log: ["Counting down. Rule: everyone shows at the same moment."],
    people: all("ready", "ok"), lit: [], dec: 1, park: 0 },
  s3: { A: Q2A(), glyph: "fd", b: { flap: "READING", side: "2 of 4 read", msg: { kind: "headline", big: ["Mina, show again"], underline: true, sub: ["Values stay hidden. Haeun not read yet."], subTop: 8 } },
    said: [SAY.L11], log: ["Reading cameras, values hidden. Low confidence means ask again, never guess."],
    people: ppl([["read", "ok"], ["show again", "again"], ["read", "ok"], ["not read", ""]]), lit: [], dec: 1, park: 0 },
  s4: { A: Q2A(), b: { flap: "SPLIT", take: "split", msg: { kind: "split", q: "Q2", title: "Perf test: when?", lines: ["4 of 4 read. Counts stay hidden until the revote.", "Next: the side that changes the plan speaks first."] } },
    said: [SAY.L11], log: ["Vote 1 is Split. First vote shows the state only."],
    people: all("read", "ok"), lit: [], dec: 1, park: 0 },
  s5: { A: Q2A(), turn: 2, b: { flap: "MINORITY", side: "Junho first", msg: { kind: "sentence", sentence: "Running it alongside integration would launch earlier.", big: ["Junho: thumb yes, palm no"] } },
    said: [SAY.L7], log: ["Split, so the side changing the plan speaks first. No AI recommendation."],
    people: ppl([["read", ""], ["read", ""], ["speaking", "ok"], ["read", ""]]), lit: ["L7"], dec: 1, park: 0 },
  s6: { A: Q2A(COST1, COST2), b: { flap: "COSTS", side: "AI picks none", msg: { kind: "costs", line: ["Both break the campaign ", R("L11"), ". Option 1 is 3 workdays earlier."], sub: "Crux: empty (no source line).", bandSub: "Values from current data." } },
    said: [{ line: "L10", who: "Haeun", text: "Launch lands on January 21." }, { line: "L11", who: "Mina", text: "Campaign is January 14." }],
    log: ["Asked what the AI thinks. Gave end dates per option from 3.2 ", R("L6"), ", picked none."],
    people: all("read"), lit: ["L6", "L10", "L11"], dec: 1, park: 0 },
  s7: { A: Q2A(), b: { flap: "CONVERGED", take: "navy conv", msg: { kind: "converged", q: "Q2", moved: 2, from: [1, "In parallel"], to: [2, "After integration"], dist: [[1, "In parallel", 0], [2, "After integration", 4]], foot: "Vote 1 was Split. Next: objection check." } },
    said: [SAY.L16], log: ["Revote. Votes moved shown before the distribution."],
    people: all("read", "ok"), lit: [], dec: 1, park: 0 },
  s8: { A: null, glyph: "thumb", b: { flap: "THUMBS", side: "no palm", msg: { kind: "headline", big: ["Written to 3.3: after integration"], sub: ["3.4 and 3.5 moved. Junho's reason kept as a memo."], subTop: 6 } },
    said: [SAY.L16], log: ["No palm, so recorded. Wrote 3.3, 3.4, 3.5 and the memo."],
    people: all("thumb", "ok"), lit: ["L16", "L7"], dec: 2, park: 0, now: "Q2 decided" },
  r1: { A: Q4A, b: { flap: "PARKED", side: "Owner Junho, after launch", msg: { kind: "headline", bigCls: "b32", big: ["Scattered twice, so parked with an owner."], sub: ["4.2 set to Parked ", R("L20")], subTop: 6 } },
    said: [SAY.L20], log: ["Q4 rewritten once, still scattered. Parked, not decided."],
    people: ppl([["voted", ""], ["voted", ""], ["owner", "ok"], ["voted", ""]]), lit: ["L20"], dec: 3, park: 1 },
  s9: { A: null, b: { flap: "CLOSED", take: "navy end", msg: { kind: "closed", title: "3 decided, 1 parked",
      cards: [
        { q: "Q1", title: "Integration test: 10 days", lines: [{ rich: ["4 thumbs"], green: true }, { rich: ["0 votes moved ", R("L6")] }] },
        { q: "Q2", title: "Perf test after integration", lines: [{ rich: ["4 thumbs ", R("L16")], green: true }, { rich: ["2 votes moved"] }] },
        { q: "Q3", title: "Beta 01-14, launch 01-21", lines: [{ rich: ["4 thumbs"], green: true }, { rich: [R("L17")] }] },
        { q: "Q4", title: "Revenue dashboard", parked: true, lines: [{ rich: [{ tag: "Parked" }] }, { rich: [{ b: "Owner Junho" }, ", after launch ", R("L20")] }] },
      ],
      stats: [["22", "edits written live", "1 undone"], ["2", "votes moved, all on Q2"], ["1", "parked with an owner"]],
      foot: "Every edit in the WBS carries a speaker and a line. No AI recommendation on any question." } },
    said: [SAY.L24], log: ["Closed. 4 questions, no AI recommendation on any."],
    people: all("voted", "ok"), lit: [], dec: 3, park: 1 },
};

export function scene(id: SceneId): WallState {
  const k = SCENES.indexOf(id);
  const s = ST[id];
  const slots: SlotState[] = [0, 1, 2, 3].map((i) =>
    i < s.dec ? "done" : i === 3 && s.park ? "park" : (i === 1 && k >= 1 && k < 8) || (i === 3 && k === 9) ? "now" : "");
  return {
    mark: "시안 v0.4",
    slots, decided: s.dec, total: 4,
    now: id === "s9" ? "closed" : s.now ?? (k >= 9 ? "Q4 of 4" : "Q2 of 4"),
    doc: doc(id),
    cardA: s.A,
    idle: id === "s8" ? ["Q2 card went back into 3.3.", "Next: Q3 Launch date."] : !s.A && !s.b.take ? ["No open question.", "Listening and writing to the WBS."] : null,
    cardB: s.b,
    decidedMarks: ["Q1", "Q2", "Q3"].slice(0, s.dec),
    parked: s.park ? [{ q: "Q4", text: "Junho, after launch", ref: "L20" }] : [],
    said: s.said, log: s.log, people: s.people, turn: s.turn, glyph: s.glyph ?? "", big: s.big, lit: s.lit,
  };
}
