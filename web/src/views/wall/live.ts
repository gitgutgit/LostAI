// 회의방 상태(RoomView: 서버 스냅샷 + 이벤트 로그)를 결정 벽 화면 상태(WallState)로 바꾼다.
// 문서 = 첫 시트 문서, 출처 칩 = provenance의 change와 그 발화 줄 번호, 질문 카드 = 열린 conflict, 표결 = vote.* 이벤트.
// author: ProfessionalSeaweedDevourer
import type { RoomView } from "../../core/reducer";
import type { Change, Conflict, Doc, MeetingEvent, Sheet } from "../../core/types";
import { changeHeadline } from "../../lib/changeText";
import type { CardA, CardB, CellKey, CellVal, Chip, DocRow, Person, Rich, SlotState, Utter, WallState } from "./types";

/** 시트 열 이름 → 벽의 7칸. 한국어, 영어 이름을 모두 받는다. */
const ROLE: Record<"w" | "t" | "o" | "s" | "e" | "d" | "st", RegExp> = {
  w: /^(wbs|id|ticket|티켓|번호|no\.?)$/i,
  t: /^(task|title|제목|작업|할 ?일|항목)$/i,
  o: /^(owner|assignee|담당|담당자)$/i,
  s: /^(start|시작|시작일)$/i,
  e: /^(end|due|종료|끝|마감|종료일)$/i,
  d: /^(days|estimate|추정|기간|일수|포인트)$/i,
  st: /^(state|status|상태|진척)$/i,
};
const KEYS = ["w", "t", "o", "s", "e", "d", "st"] as const;
const HEAD: Record<(typeof KEYS)[number], string> = { w: "WBS", t: "Task", o: "Owner", s: "Start", e: "End", d: "Days", st: "State" };

const str = (x: unknown) => (x === null || x === undefined ? "" : String(x));

function mapColumns(sheet: Sheet): Record<(typeof KEYS)[number], string | null> {
  const out = {} as Record<(typeof KEYS)[number], string | null>;
  const free = [...sheet.columns];
  for (const k of KEYS) {
    const hit = free.find((c) => ROLE[k].test(c.trim()));
    out[k] = hit ?? null;
    if (hit) free.splice(free.indexOf(hit), 1);
  }
  // 이름으로 못 찾은 칸은 남은 열을 앞에서부터 채운다(첫 열 = 번호, 둘째 = 제목).
  for (const k of KEYS) if (!out[k] && free.length && (k === "w" || k === "t")) out[k] = free.shift()!;
  return out;
}

/** 발화 utt_id → 회의 줄 번호(L1부터). 대본의 줄 번호와 같은 규칙: 확정 발화 순서. */
function lineIndex(events: MeetingEvent[]): Map<string, { n: number; who: string; text: string }> {
  const m = new Map<string, { n: number; who: string; text: string }>();
  let n = 0;
  for (const e of events) if (e.type === "utterance.final" && e.refs.utt_id) {
    n += 1;
    m.set(e.refs.utt_id, { n, who: str(e.payload.speaker ?? e.actor), text: str(e.payload.text) });
  }
  return m;
}

export function liveWall(v: RoomView, me?: string): WallState {
  const s = v.state;
  const lines = lineIndex(v.events);
  const L = (ch?: Change | null) => (ch?.utt_id && lines.get(ch.utt_id) ? `L${lines.get(ch.utt_id)!.n}` : "");
  const changes = Object.values(v.changes);
  const applied = changes.filter((c) => c.status === "applied" || c.status === "approved");
  const reverted = changes.filter((c) => c.status === "reverted");
  const lastApplied = [...v.events].reverse().find((e) => e.type === "change.applied");
  const fresh = lastApplied ? v.changes[(lastApplied.payload as Change).change_id] : undefined;

  // ---------------------------------------------------------------- 문서
  // ep: 문서 칸의 주인은 시트(보드)다. 노트 문서(결정, 리스크, 액션, 메모)는 이번 회의에서 고친 항목만 보드 아래에 덧붙인다.
  // 시트가 없는 방이면 마지막으로 고친 노트 문서(없으면 첫 노트 문서)를 통째로 보인다.
  const lastDocKey = s ? [...v.events].reverse()
    .map((e) => (e.type === "change.applied" ? (e.payload as Change).targets[0]?.split("/")[0] : undefined))
    .find((k) => !!k && s.docs[k]?.kind === "doc") : undefined;
  const notesEntry: [string, Doc] | undefined = !s ? undefined
    : lastDocKey ? [lastDocKey, s.docs[lastDocKey] as Doc]
    : (Object.entries(s.docs).find(([, d]) => d.kind === "doc") as [string, Doc] | undefined);
  const sheetEntry = s ? Object.entries(s.docs).find(([, d]) => d.kind === "sheet") : undefined;
  const sheetKey = sheetEntry?.[0] ?? "";
  const sheet = sheetEntry?.[1] as Sheet | undefined;
  const cols = sheet ? mapColumns(sheet) : null;
  const rows: DocRow[] = [];
  if (sheet && cols && s) {
    for (const r of sheet.rows) {
      const val = (k: (typeof KEYS)[number]): CellVal => ({ v: cols[k] ? str(r.cells[cols[k]!]) : "" });
      const row: DocRow = { w: val("w").v, t: val("t").v, o: val("o"), s: val("s"), e: val("e"), d: val("d"), st: val("st"), src: [], fresh: {}, memo: null };
      // 출처 칩: 이 행의 칸과 행 자체를 마지막으로 바꾼 change마다 '누가 L줄'
      const seen = new Set<string>();
      for (const [anchor, cid] of Object.entries(s.provenance)) {
        if (!(anchor === `${sheetKey}/${r.row_id}` || anchor.startsWith(`${sheetKey}/${r.row_id}/`)) || seen.has(cid)) continue;
        seen.add(cid);
        const ch = v.changes[cid];
        if (ch) row.src.push({ t: `${ch.requested_by}${L(ch) ? " " + L(ch) : ""}`, r: L(ch) || undefined });
      }
      // 되돌린 변경이 이 행에 닿았으면 표시
      for (const ch of reverted) if (ch.targets.some((a) => a.startsWith(`${sheetKey}/${r.row_id}`))) {
        const by = ch.approvals.find((a) => a.action === "revert")?.by;
        row.src.push({ t: `undone${by ? " by " + by : ""}`, cls: "undo" });
      }
      // 방금 고친 칸: 노랑 + 옛 값 줄긋기
      if (fresh) for (const d of fresh.diff) {
        if (d.kind === "row" && d.anchor === `${sheetKey}/${r.row_id}` && d.before === null) { row.newrow = true; row.rowfresh = true; }
        if (d.kind === "cell" && d.anchor.startsWith(`${sheetKey}/${r.row_id}/`)) {
          const col = d.anchor.split("/")[2];
          const k = KEYS.find((x) => cols[x] === col);
          if (k && k !== "w" && k !== "t") {
            row.fresh![k as CellKey] = 0;
            const cur = row[k as CellKey];
            if (str(d.before) !== "") row[k as CellKey] = { ...cur, old: str(d.before) };
          }
        }
      }
      rows.push(row);
    }
  }
  // 열린 질문이 걸린 행: 열린 conflict의 topic에 행 번호나 제목이 들어 있으면 그 행에 Q 표지
  const conflicts: Conflict[] = s?.conflicts ?? [];
  const open = conflicts.filter((c) => !c.resolved);
  const qOf = (c: Conflict) => `Q${conflicts.indexOf(c) + 1}`;
  for (const c of open) {
    const row = rows.find((r) => (r.w && c.topic.includes(r.w)) || (r.t && c.topic.includes(r.t)));
    if (row) { row.src.unshift({ t: `${qOf(c)} open`, cls: "tag" }); row.tall = true; }
  }

  // ep: 노트 문서 항목 → 표 행: 첫 칸 = 섹션 종류, 둘째 = 항목 문장, 셋째 = 담당. onlyEdited면 이번 회의에서 고친 항목만.
  const noteRows = (nk: string, nd: Doc, onlyEdited: boolean): DocRow[] => {
    const KIND: Record<string, string> = { decisions: "Decision", risks: "Risk", actions: "Action" };
    const out: DocRow[] = [];
    if (!s) return out;
    for (const sec of nd.sections) for (const it of sec.items) {
      const anchor = `${nk}/${sec.section_id}/${it.item_id}`;
      const cid = s.provenance[anchor];
      if (onlyEdited && !cid) continue;
      const blank = { v: "" };
      const row: DocRow = { w: (sec.binding && KIND[sec.binding]) || sec.heading, t: it.text, o: { v: str(it.meta?.owner) }, s: blank, e: blank, d: blank, st: blank, src: [], fresh: {}, memo: null };
      const ch = cid ? v.changes[cid] : undefined;
      if (ch) row.src.push({ t: `${ch.requested_by}${L(ch) ? " " + L(ch) : ""}`, r: L(ch) || undefined });
      for (const d of fresh?.diff ?? []) if (d.anchor === anchor) { if (d.before === null) row.newrow = true; row.rowfresh = true; }
      out.push(row);
    }
    return out;
  };

  // 시트에 없는 열은 숨기고, 번호 열은 가장 긴 번호에 맞춘다(시안의 64px는 WBS 번호 기준).
  const WIDTH: Record<string, string> = { o: "150px", s: "100px", e: "100px", d: "90px", st: "180px" };
  const firstPx = (rs: DocRow[], minChars: number) => Math.min(180, Math.max(64, 20 + 16 * Math.max(minChars, ...rs.map((r) => r.w.length))));

  let docTitle = sheet?.title ?? "Doc", docSub = "", docCols = cols ? KEYS.map((k) => cols[k] ?? HEAD[k]) : undefined;
  let docHide: CellKey[] = cols ? (["o", "s", "e", "d", "st"] as const).filter((k) => !cols[k]) : [];
  let docRows = rows, docGrid: string | undefined;
  if (sheet && cols) {
    // 보드 아래: 노트 문서마다 이번 회의에서 고친 항목
    if (s) for (const [nk, nd] of Object.entries(s.docs)) if (nd.kind === "doc") docRows = [...docRows, ...noteRows(nk, nd as Doc, true)];
    docGrid = [`${firstPx(docRows, 3)}px`, "minmax(240px, 1fr)", ...(["o", "s", "e", "d", "st"] as const).filter((k) => cols[k]).map((k) => WIDTH[k]), "300px"].join(" ");
  } else if (notesEntry) {
    const [nk, nd] = notesEntry;
    docRows = noteRows(nk, nd, false);
    docTitle = nd.title;
    docCols = ["Section", "Item", "Owner", "Start", "End", "Days", "State"];
    docHide = ["s", "e", "d", "st"];
    docGrid = `${firstPx(docRows, 4)}px minmax(240px, 1fr) 150px 300px`;
  }

  const lastLine = fresh ? L(fresh) : "";
  const note: Rich = fresh
    ? [`Last: ${lastLine ? lastLine + " " : ""}${changeHeadline(fresh, s)}`]
    : ["Each edit shows who said it and the line."];

  // ---------------------------------------------------------------- 질문 카드(열린 conflict)
  const q = open[0];
  const cardA: CardA | null = q ? {
    q: qOf(q), title: q.topic,
    options: q.positions.slice(0, 2).map((p, i) => ({ n: i + 1, name: p.says, src: [p.who] })),
  } : null;

  // ---------------------------------------------------------------- 글자판(카드 B)
  const lastOf = (pred: (e: MeetingEvent) => boolean) => [...v.events].reverse().find(pred);
  const vOpen = lastOf((e) => e.type === "vote.opened");
  const vClosed = lastOf((e) => e.type === "vote.closed");
  const voting = vOpen && (!vClosed || vClosed.seq < vOpen.seq);
  const lastAgent = lastOf((e) => e.type === "agent.progress" || e.type === "ask.answered" || e.type === "change.failed" || e.type === "change.applied" || e.type === "change.reverted");
  const stage = lastAgent?.type === "agent.progress" ? str(lastAgent.payload.stage) : "";
  let cardB: CardB = { flap: "LISTENING", side: stage === "editing" ? "writing" : stage === "routing" ? "heard" : "", msg: { kind: "headline", big: ["Writing what the team says"], sub: ["Small talk is ignored. Any edit can be undone."], subTop: 4 } };
  if (v.paused) cardB = { flap: "PAUSED", msg: { kind: "headline", big: ["Paused"], sub: ["Show the T sign again to resume."], subTop: 4 } };
  else if (voting) {
    const cast = v.events.filter((e) => e.type === "vote.cast" && e.refs.vote_id === vOpen!.refs.vote_id).length;
    cardB = { flap: "3 2 1", off: [0, 4], take: "count", msg: { kind: "countdown", q: q ? qOf(q) : "Q", title: q?.topic ?? "Vote", prompt: `Show fingers to your camera, or say 1 or 2. ${cast} read.` } };
  } else if (vClosed && Object.keys((vClosed.payload.votes ?? {}) as object).length === 0 && (!lastAgent || vClosed.seq > lastAgent.seq)) {
    cardB = { flap: "NO VOTE", msg: { kind: "headline", big: ["No hands read"], sub: ["Say 1 or 2, or show fingers, then call the vote again."], subTop: 4 } };
  } else if (vClosed && (!lastAgent || vClosed.seq > lastAgent.seq)) {
    const votes = Object.values((vClosed.payload.votes ?? {}) as Record<string, number>);
    const tally = new Map<number, number>();
    votes.forEach((n) => tally.set(n, (tally.get(n) ?? 0) + 1));
    const top = [...tally.entries()].sort((a, b) => b[1] - a[1]);
    const split = top.length > 1 && top[0][1] === top[1][1];
    cardB = split
      ? { flap: "SPLIT", take: "split", msg: { kind: "split", q: q ? qOf(q) : "Q", title: q?.topic ?? "Vote", lines: [`${votes.length} read. Counts stay hidden until the revote.`, "Next: the side that changes the plan speaks first."] } }
      : { flap: "CONVERGED", take: "navy conv", msg: { kind: "converged", q: q ? qOf(q) : "Q", moved: 0, from: [top[0]?.[0] ?? 0, ""], to: [top[0]?.[0] ?? 0, ""],
          first: { title: q?.topic ?? "Vote", winner: q?.positions[top[0][0] - 1]?.says ?? `Option ${top[0][0]}`, sub: `${top[0][1]} of ${votes.length} votes for ${top[0][0]}` },
          dist: [...tally.entries()].sort((a, b) => a[0] - b[0]).map(([n, c]) => [n, q?.positions[n - 1]?.says ?? `Option ${n}`, c] as [number, string, number]),
          foot: "Next: objection check." } };
  } else if (lastAgent?.type === "ask.answered") {
    cardB = { flap: "ASK", msg: { kind: "headline", big: [str(lastAgent.payload.answer)], bigCls: "b28 clamp3" } };
  } else if (lastAgent?.type === "change.failed") {
    cardB = { flap: "MISSED", msg: { kind: "headline", big: ["Could not write that"], sub: [str((lastAgent.payload as Change).error)], subTop: 4 } };
  } else if (q) {
    cardB = { flap: "ASK", side: `${q.positions.length} positions`, msg: { kind: "headline", big: ["Two values for one cell"], sub: ["Options come from team words only."], subTop: 4 } };
  }

  // ---------------------------------------------------------------- 발화, 로그, 참가자
  const utters = [...lines.values()];
  const lastU = utters.at(-1);
  const said: Utter[] = lastU ? [{ line: `L${lastU.n}`, who: lastU.who, text: lastU.text }] : [];
  const lastCh = [...v.events].reverse().find((e) => e.type.startsWith("change.") && e.type !== "change.proposed");
  const lastChObj = lastCh ? v.changes[(lastCh.payload as Change).change_id] : undefined;
  const ignored = [...v.events].reverse().find((e) => e.type === "agent.routed" && e.payload.label === "ignore");
  const logParts: string[] = [];
  if (lastChObj) logParts.push(`${L(lastChObj) ? L(lastChObj) + " " : ""}${lastCh!.type === "change.reverted" ? "undone: " : ""}${changeHeadline(lastChObj, s)}.`);
  if (ignored?.refs.utt_id && lines.get(ignored.refs.utt_id)) logParts.push(`L${lines.get(ignored.refs.utt_id)!.n} ignored: small talk.`);
  const log: Rich = [logParts.join(" ") || "Waiting for the first words."];

  const names = [...new Set([...Object.keys(v.participants ?? {}), ...utters.map((u) => u.who)])].filter(Boolean).slice(0, 4);
  const people: Person[] = names.map((n) => ({ name: n, status: lastU?.who === n ? "speaking" : n === me ? "you" : "here", tone: lastU?.who === n ? "ok" : "" }));
  const turn = lastU ? names.indexOf(lastU.who) : -1;

  // ---------------------------------------------------------------- 머리줄
  const total = conflicts.length;
  const slots: SlotState[] = conflicts.slice(0, 4).map((c) => (c.resolved ? "done" : c === q ? "now" : ""));
  const decided = conflicts.filter((c) => c.resolved);
  const lit = [lastLine].filter(Boolean);

  return {
    mark: v.connected ? "Live" : "Offline",
    slots, decided: decided.length, total,
    progText: total ? undefined : "No questions yet",
    now: q ? `${qOf(q)} of ${total}` : "listening",
    doc: {
      title: docTitle, subtitle: docSub, edits: applied.length + reverted.length, undone: reverted.length, note,
      cols: docCols, hide: docHide, grid: docGrid, rows: docRows,
    },
    cardA,
    idle: cardA || cardB.take ? null : ["No open question.", `Listening and writing to ${sheet?.title ?? "the doc"}.`],
    cardB,
    decidedMarks: decided.map(qOf),
    parked: [],
    said, log, people, turn: turn >= 0 ? turn : undefined,
    glyph: voting ? "cam" : "", big: !!voting, lit,
  };
}

/** 문서 탭 중 시트가 아닌 노트 문서(결정, 액션, 리스크)를 회의록으로 볼 때 쓴다. */
export function notesDoc(v: RoomView): Doc | undefined {
  return Object.values(v.state?.docs ?? {}).find((d): d is Doc => d.kind === "doc");
}

export type { Chip };
