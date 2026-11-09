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
  d: /^(days|duration( \(days\))?|estimate|추정|기간(\(일\))?|일수|포인트)$/i,
  st: /^(state|status|상태|진척)$/i,
};
const KEYS = ["w", "t", "o", "s", "e", "d", "st"] as const;
const HEAD: Record<(typeof KEYS)[number], string> = { w: "WBS", t: "Task", o: "Owner", s: "Start", e: "End", d: "Days", st: "State" };

const str = (x: unknown) => (x === null || x === undefined ? "" : String(x));

/** 표결 두 가지 (author: gitgutgit, 서버 server/gestures/votes.py와 같은 규칙).
 *  찬반 카드: 선택지가 1개 이하이거나 '반대'/'No'가 있으면 → 3 = 좋음, 2 = 보통, 1 = 싫음.
 *  선택지 카드: 실제 선택지가 2~4개 → 번호 1~N 고르기. 범위 밖의 값은 세지 않는다. */
const RATING: Record<number, string> = { 3: "Good", 2: "Okay", 1: "No" };
const isRatingCard = (c?: Conflict) => !c || c.positions.length < 2 || c.positions.some((p) => /^(반대|no)$/i.test(p.says.trim()));
const RATING_PROMPT = "3 fingers good, 2 okay, 1 no. Or say good, okay or no (좋아요 · 보통 · 싫어요).";
/** 회의를 끝내는 말과 다시 여는 말. 마지막 확정 발화 기준으로 CLOSED 끝 화면을 띄운다. */
const CLOSE_RE = /(회의(를|는)?\s*(종료|마치|마무리|끝내|끝냅|끝)|회의\s*끝|오늘(은)?\s*여기까지|\bend (the )?meeting\b|\blet'?s (wrap|close)( it)? up\b|\bthat'?s a wrap\b|\bmeeting (is )?(over|closed)\b)/i;
const REOPEN_RE = /(회의\s*(계속|재개|다시)|다시\s*시작|\b(reopen|resume) the meeting\b)/i;

/** 마지막 '회의 끝' 발화의 seq (다시 연 말이 뒤에 있으면 -1). 끝 화면을 접을 때 기준. */
export function lastCloseSeq(v: RoomView): number {
  const finals = v.events.filter((e) => e.type === "utterance.final");
  const closeEv = [...finals].reverse().find((e) => CLOSE_RE.test(str(e.payload.text)));
  if (!closeEv || finals.some((e) => e.seq > closeEv.seq && REOPEN_RE.test(str(e.payload.text)))) return -1;
  return closeEv.seq;
}

/** 표결 결과 집계. values = 이 카드에서 세는 값(찬반 [3,2,1], 선택지 [1..N]). tie = 1위가 둘 이상. */
function tally(raw: Record<string, number>, values: number[]) {
  const votes = Object.values(raw).filter((n) => values.includes(n));
  const count = Object.fromEntries(values.map((n) => [n, 0])) as Record<number, number>;
  votes.forEach((n) => (count[n] += 1));
  const ranked = values.map((n) => [n, count[n]] as [number, number]).sort((a, b) => b[1] - a[1]);
  const tie = votes.length > 0 && ranked.length > 1 && ranked[0][1] === ranked[1][1];
  return { votes, count, top: ranked[0]?.[0] ?? 0, topCount: ranked[0]?.[1] ?? 0, tie, tieWith: ranked.filter((r) => r[1] === ranked[0][1]).map((r) => r[0]) };
}
const valuesFor = (c?: Conflict) => (isRatingCard(c) ? [3, 2, 1] : c!.positions.slice(0, 4).map((_, i) => i + 1));
const optName = (c: Conflict | undefined, n: number) => (isRatingCard(c) ? RATING[n] : c?.positions[n - 1]?.says ?? `Option ${n}`);
const voteLine = (c: Conflict | undefined, t: ReturnType<typeof tally>) =>
  // gitgutgit 11-09: 표 수는 ×N 으로 쓴다. "2 good"은 손가락 2개로 읽혀서 3·2·1 규칙과 헷갈렸다.
  isRatingCard(c) ? `good ×${t.count[3]} · okay ×${t.count[2]} · no ×${t.count[1]}` : valuesFor(c).map((n) => `${n} ${optName(c, n)} ×${t.count[n]}`).join(" · ");

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

/** 가장 최근 표결 이벤트(vote.opened, vote.closed)의 seq. 전체화면 표결 화면(카운트다운, 결과)은 이 이벤트에서 나온다. */
export function lastVoteSeq(v: RoomView): number {
  return [...v.events].reverse().find((e) => e.type === "vote.opened" || e.type === "vote.closed")?.seq ?? -1;
}

/** hideTakeUpTo: 이 seq까지의 표결 이벤트로 생긴 전체화면 표결 화면은 닫힌 것으로 보고 평소 카드로 그린다 (평상시 화면 버튼, 5초 카운트다운). */
export function liveWall(v: RoomView, me?: string, hideTakeUpTo = -1, hideCloseUpTo = -1, voteLeftSec?: number | null): WallState {
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

  // ep: 열 폭은 글자에 맞춘다(28px 글꼴에서 한글 같은 넓은 글자 약 28px, 나머지 약 16px, 좌우 여백 16px). 상한을 넘는 글자는 칸 안에서 줄을 바꾼다(wall.css).
  const textPx = (t: string) => [...t].reduce((a, c) => a + (/[ᄀ-ᇿ⺀-鿿가-힯＀-￯]/.test(c) ? 28 : 16), 0) + 16;
  const fitPx = (texts: string[], min: number, max: number) => Math.min(max, Math.max(min, ...texts.map(textPx)));
  const fit = (texts: string[], min: number, max: number) => `${fitPx(texts, min, max)}px`;
  const LIMIT: Record<"o" | "s" | "e" | "d" | "st", [number, number]> = { o: [120, 220], s: [90, 190], e: [90, 190], d: [70, 120], st: [130, 240] };
  // 날짜, 기간 같은 짧은 값은 끊으면 읽기 어렵다(2026- / 11-20) → 이 열들은 글자 폭 그대로를 최소 폭으로 지키고, 줄 바꿈은 글이 긴 열(작업, 담당, 상태)이 맡는다.
  const NO_WRAP = new Set(["s", "e", "d"]);
  // 종이 안쪽 폭 1174px(1222 - 좌우 24). 모든 열의 합이 이 폭을 넘지 않게 나눈다(넘으면 오른쪽 열이 종이 밖에서 잘린다).
  // 1) 항목 열에 360px를 남기고, 가운데 열이 넘치면 가장 넓은 열부터 같은 상한까지 깎되 열마다 제 최소 폭 아래로는 깎지 않는다.
  // 2) 그래도 모자라면 출처 열을 SRC_MIN까지, 다음으로 항목 열을 240px까지 줄인다. 깎인 열의 글은 칸 안에서 줄을 바꾼다.
  const SRC_MIN = 120, TASK_MAX = 360, TASK_MIN = 240, PAPER = 1174;
  const gridOf = (first: number, mid: [number, number][], src: number) => {
    const sum = (cap: number) => mid.reduce((a, [w, min]) => a + Math.max(min, Math.min(w, cap)), 0);
    let cap = Math.max(...mid.map(([w]) => w), 0);
    while (sum(cap) > PAPER - TASK_MAX - first - src && cap > 60) cap -= 2;
    let srcW = Math.max(SRC_MIN, Math.min(src, PAPER - TASK_MAX - first - sum(cap)));
    const left = () => PAPER - first - sum(cap) - srcW;
    if (left() < TASK_MIN) srcW = Math.max(SRC_MIN, srcW - (TASK_MIN - left()));
    const task = Math.max(TASK_MIN, Math.min(TASK_MAX, left()));
    return [`${first}px`, `minmax(${task}px, 1fr)`, ...mid.map(([w, min]) => `${Math.max(min, Math.min(w, cap))}px`), `${srcW}px`].join(" ");
  };
  // 출처 열 폭: 칩이 둘 이상인 행은 높은 행(96px)이라 칩이 두 줄까지 들어간다. 가장 긴 칩과 칩 폭 합의 절반 중 큰 쪽(칸 왼쪽 여백 8px).
  const srcFit = (rs: DocRow[]) => Math.min(300, Math.max(SRC_MIN, ...rs.map((r) => {
    const ws = r.src.map((c) => textPx(c.t));
    return Math.max(0, ...ws, Math.ceil((ws.reduce((a, w) => a + w + 6, 0)) / 2)) + 8;
  })));

  let docTitle = sheet?.title ?? "Doc", docSub = "", docCols = cols ? KEYS.map((k) => cols[k] ?? HEAD[k]) : undefined;
  let docHide: CellKey[] = cols ? (["o", "s", "e", "d", "st"] as const).filter((k) => !cols[k]) : [];
  let docRows = rows, docGrid: string | undefined;
  if (sheet && cols) {
    // 보드 아래: 노트 문서마다 이번 회의에서 고친 항목
    if (s) for (const [nk, nd] of Object.entries(s.docs)) if (nd.kind === "doc") docRows = [...docRows, ...noteRows(nk, nd as Doc, true)];
    const colText = (k: (typeof KEYS)[number]) => [cols[k] ?? HEAD[k], ...docRows.map((r) => (k === "w" ? r.w : str((r[k as CellKey] as CellVal).v)))];
    const mid = (["o", "s", "e", "d", "st"] as const).filter((k) => cols[k]).map((k): [number, number] => { const w = fitPx(colText(k), ...LIMIT[k]); return [w, NO_WRAP.has(k) ? w : LIMIT[k][0]]; });
    docGrid = gridOf(fitPx(colText("w"), 64, 200), mid, srcFit(docRows));
  } else if (notesEntry) {
    const [nk, nd] = notesEntry;
    docRows = noteRows(nk, nd, false);
    docTitle = nd.title;
    docCols = ["Section", "Item", "Owner", "Start", "End", "Days", "State"];
    docHide = ["s", "e", "d", "st"];
    docGrid = `${fit(["Section", ...docRows.map((r) => r.w)], 64, 200)} minmax(240px, 1fr) ${fit(["Owner", ...docRows.map((r) => r.o.v)], ...LIMIT.o)} 300px`;
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
  /** 이 표결이 다루는 질문 카드: vote.opened의 question과 같은 topic, 없으면 화면의 열린 질문. */
  const cardOf = (ev: MeetingEvent): Conflict | undefined => {
    const opened = ev.type === "vote.opened" ? ev : v.events.find((o) => o.type === "vote.opened" && o.refs.vote_id === ev.refs.vote_id);
    const topic = str(opened?.payload.question);
    return conflicts.find((c) => c.topic === topic) ?? q;
  };
  const vClosed = lastOf((e) => e.type === "vote.closed");
  const voting = vOpen && (!vClosed || vClosed.seq < vOpen.seq);
  const countShown = !!voting && vOpen!.seq > hideTakeUpTo;
  const lastAgent = lastOf((e) => e.type === "agent.progress" || e.type === "ask.answered" || e.type === "change.failed" || e.type === "change.applied" || e.type === "change.reverted");
  const stage = lastAgent?.type === "agent.progress" ? str(lastAgent.payload.stage) : "";
  let cardB: CardB = { flap: "LISTENING", side: stage === "editing" ? "writing" : stage === "routing" ? "heard" : "", msg: { kind: "headline", big: ["Writing what the team says"], sub: ["Small talk is ignored. Any edit can be undone."], subTop: 4 } };
  // ---------------------------------------------------------------- 회의 끝(CLOSED)
  // 마지막으로 '회의를 종료하죠'류 발화가 나온 뒤 '회의 계속'류가 없으면 끝 화면. 결정된 질문, 남은 결정, 마지막 변경, 숫자.
  const closeSeq = lastCloseSeq(v);
  const closed = closeSeq > hideCloseUpTo;
  if (closed) {
    const decidedQs = conflicts.filter((c) => c.resolved);
    // 질문(topic)별 마지막 표결 결과
    const voteOf = new Map<string, string>();
    for (const e of v.events) if (e.type === "vote.closed") {
      const opened = v.events.find((o) => o.type === "vote.opened" && o.refs.vote_id === e.refs.vote_id);
      const card = conflicts.find((c) => c.topic === str(opened?.payload.question));
      if (!card) continue;
      const t = tally((e.payload.votes ?? {}) as Record<string, number>, valuesFor(card));
      if (t.votes.length) voteOf.set(card.topic, voteLine(card, t));
    }
    const votesHeld = v.events.filter((e) => e.type === "vote.closed").length;
    const qCards = [...open, ...decidedQs].slice(0, 3).map((c) => {
      const vl = voteOf.get(c.topic);
      const voteRow = vl ? [{ rich: [`Vote: ${vl}`] as Rich }] : [];
      return c.resolved
        ? { q: qOf(c), title: c.topic, lines: [{ rich: [c.resolution || "Decided"] as Rich, green: true }, ...voteRow] }
        : { q: qOf(c), title: c.topic, parked: true, lines: [{ rich: [{ tag: "Decision needed" }] as Rich },
            ...c.positions.slice(0, 2).map((p, i) => ({ rich: [`${i + 1}. ${p.says} `, { ref: p.who }] as Rich })), ...voteRow] };
    });
    const lastEdits = [...v.events].reverse().filter((e) => e.type === "change.applied" || e.type === "change.reverted").slice(0, 3)
      .map((e) => { const ch = v.changes[(e.payload as Change).change_id] ?? (e.payload as Change);
        return { rich: [`${e.type === "change.reverted" ? "undone: " : ""}${changeHeadline(ch, s)} `, ...(L(ch) ? [{ ref: L(ch) }] : [])] as Rich }; });
    const cards = [...qCards, ...(lastEdits.length ? [{ q: "Last", title: "Last edits", lines: lastEdits }] : [])];
    const title = conflicts.length ? `${decidedQs.length} decided, ${open.length} open` : "Meeting closed";
    cardB = { flap: "CLOSED", take: "navy end", msg: { kind: "closed", title, cards,
      stats: [[String(applied.length + reverted.length), "edits written live", `${reverted.length} undone`],
              [String(votesHeld), votesHeld === 1 ? "vote held" : "votes held"],
              [String(open.length), open.length === 1 ? "decision still needed" : "decisions still needed"]],
      foot: "Every edit in the doc carries a speaker and a line. No AI recommendation on any question." } };
  } else if (v.paused) cardB = { flap: "PAUSED", msg: { kind: "headline", big: ["Paused"], sub: ["Show the T sign again to resume."], subTop: 4 } };
  else if (countShown) {
    // gitgutgit 11-09: 표결 중에도 집계를 공개한다 — 누가 냈는지(✓)와 지금까지의 표. 내 손이 읽혔는지 바로 보이게.
    const castBy: Record<string, number> = {};
    for (const e of v.events) if (e.type === "vote.cast" && e.refs.vote_id === vOpen!.refs.vote_id) castBy[e.actor] = Number(e.payload.value);
    const cast = Object.keys(castBy).length;
    const vq = cardOf(vOpen!);
    const now = tally(castBy, valuesFor(vq));
    const who = Object.entries(castBy).map(([n, val]) => `${n}${n === me ? " (you)" : ""} ✓ ${optName(vq, val).toLowerCase()}`).join(", ");
    const live = cast ? ` Now: ${voteLine(vq, now)}. Voted: ${who}.` : "";
    const prompt = isRatingCard(vq) ? RATING_PROMPT : `Pick a number: ${valuesFor(vq).map((n) => `${n} ${optName(vq, n)}`).join(", ")}. Show fingers, or say "two" or "option two" (2번).`;
    // gitgutgit: 남은 초를 글자판에 숫자로 (서버가 준 closes_in 기준). 모르면 예전처럼 "3 2 1".
    const left = voteLeftSec != null ? Math.max(0, voteLeftSec) : null;
    cardB = left != null
      ? { flap: String(left), take: "count", msg: { kind: "countdown", q: vq ? qOf(vq) : "Q", title: vq?.topic ?? "Vote", prompt: `${prompt}${live || ` ${cast} read.`} Closes in ${left}s.` } }
      : { flap: "3 2 1", off: [0, 4], take: "count", msg: { kind: "countdown", q: vq ? qOf(vq) : "Q", title: vq?.topic ?? "Vote", prompt: `${prompt}${live || ` ${cast} read.`}` } };
  } else if (vClosed && tally((vClosed.payload.votes ?? {}) as Record<string, number>, valuesFor(cardOf(vClosed))).votes.length === 0 && (!lastAgent || vClosed.seq > lastAgent.seq)) {
    const vq = cardOf(vClosed);
    cardB = { flap: "NO VOTE", msg: { kind: "headline", big: ["No hands read"], sub: [`${isRatingCard(vq) ? RATING_PROMPT : "Show fingers or say a number."} Then call the vote again.`], subTop: 4 } };
  } else if (vClosed && vClosed.seq > hideTakeUpTo && (!lastAgent || vClosed.seq > lastAgent.seq)) {
    // 찬반 카드: 3 = 좋음, 2 = 보통, 1 = 싫음 (바늘 숨김). 선택지 카드: 번호 고르기(바늘 그대로). 1위가 둘 이상(동점)이면 SPLIT.
    const vq = cardOf(vClosed), rating = isRatingCard(vq), values = valuesFor(vq);
    const t = tally((vClosed.payload.votes ?? {}) as Record<string, number>, values);
    const NEXT: Record<number, string> = { 3: "Mostly good. Confirm it, or say what still worries you.", 2: "Mostly okay. Ask what would make it good.", 1: "Mostly no. Rework the proposal or park it." };
    const title = vq?.topic ?? "Vote", qn = vq ? qOf(vq) : "Q";
    cardB = t.tie
      ? { flap: "SPLIT", take: "split", msg: { kind: "split", q: qn, title,
          lines: [`Tie: ${t.tieWith.map((n) => (rating ? RATING[n].toLowerCase() : `${n} ${optName(vq, n)}`)).join(" and ")}, ${t.topCount} each (${t.votes.length} read).`,
                  "Next: the side that changes the plan speaks first, then revote."] } }
      : { flap: "CONVERGED", take: rating ? "navy conv rate" : "navy conv", msg: { kind: "converged", q: qn, moved: 0, from: [t.top, ""], to: [t.top, ""],
          first: { title, winner: optName(vq, t.top), sub: rating ? `${t.topCount} of ${t.votes.length}: ${voteLine(vq, t)}` : `${t.topCount} of ${t.votes.length} votes for ${t.top}` },
          dist: (rating ? values : [...values].sort((a, b) => a - b)).map((n) => [n, optName(vq, n), t.count[n]] as [number, string, number]),
          foot: rating ? NEXT[t.top] : "Next: objection check." } };
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

  // gitgutgit 11-09: 회의에서 나간 사람(마지막 participant.left가 마지막 입장보다 뒤, 지금 참석자 아님)은 뺀다.
  // 예전엔 '참석자 + 한 번이라도 말한 사람'이라 나가도 계속 남았다. 입장한 적 없는 대본 화자는 그대로 보인다.
  const lastIn = new Map<string, number>(), lastOut = new Map<string, number>();
  for (const e of v.events) {
    const n = e.payload?.name as string | undefined;
    if (!n) continue;
    if (e.type === "participant.verified" || e.type === "participant.joined") lastIn.set(n, e.seq);
    if (e.type === "participant.left") lastOut.set(n, e.seq);
  }
  const present = v.participants ?? {};
  const gone = (n: string) => !(n in present) && (lastOut.get(n) ?? -1) > (lastIn.get(n) ?? -1);
  const names = [...new Set([...Object.keys(present), ...utters.map((u) => u.who)])].filter((n) => n && !gone(n)).slice(0, 4);
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
    glyph: voting ? "cam" : "", big: countShown, lit,
  };
}

/** 문서 탭 중 시트가 아닌 노트 문서(결정, 액션, 리스크)를 회의록으로 볼 때 쓴다. */
export function notesDoc(v: RoomView): Doc | undefined {
  return Object.values(v.state?.docs ?? {}).find((d): d is Doc => d.kind === "doc");
}

export type { Chip };
