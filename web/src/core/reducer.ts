// 이벤트 로그를 접어(reduce) 화면 상태를 만든다 (ARCHITECTURE 3-1, 7절).
import type { Change, DiffEntry, Doc, DocState, MeetingEvent, ServerMessage, Sheet } from "./types";

export interface RoomView {
  connected: boolean;
  state: DocState | null;
  changes: Record<string, Change>;
  events: MeetingEvent[];
  participants: Record<string, any>;
  paused: boolean;
  notice: string | null;
}

export const initialView: RoomView = {
  connected: false, state: null, changes: {}, events: [], participants: {}, paused: false, notice: null,
};

const clone = <T,>(x: T): T => structuredClone(x);

/** diff 한 줄을 정방향(forward) 또는 역방향으로 적용. 서버 server/ops/engine.py 와 같은 의미. */
function applyEntry(s: DocState, d: DiffEntry, forward: boolean) {
  const [from, to] = forward ? [d.before, d.after] : [d.after, d.before];
  const p = d.anchor.split("/");
  const put = <T,>(list: T[], match: (x: T) => boolean) => {
    const i = list.findIndex(match);
    if (to === null) { if (i >= 0) list.splice(i, 1); }
    else if (from === null || i < 0) list.splice(d.index ?? list.length, 0, clone(to));
    else list[i] = clone(to);
  };
  switch (d.kind) {
    case "cell": {
      const row = (s.docs[p[0]] as Sheet).rows.find((r) => r.row_id === p[1]);
      if (row) row.cells[p[2]] = to;
      break;
    }
    case "row": put((s.docs[p[0]] as Sheet).rows, (r) => r.row_id === p[1]); break;
    case "item": {
      const sec = (s.docs[p[0]] as Doc).sections.find((x) => x.section_id === p[1]);
      if (sec) put(sec.items, (it) => it.item_id === p[2]);
      break;
    }
    case "section": put((s.docs[p[0]] as Doc).sections, (x) => x.section_id === p[1]); break;
    case "heading": {
      const sec = (s.docs[p[0]] as Doc).sections.find((x) => x.section_id === p[1]);
      if (sec) sec.heading = to;
      break;
    }
    case "ticket": put(s.tickets, (t) => t.ticket_id === p[1]); break;
    case "conflict": put(s.conflicts, (c) => c.conflict_id === p[1]); break;
  }
}

function applyChange(state: DocState, ch: Change, forward: boolean): DocState {
  const s = clone(state);
  const diff = forward ? ch.diff : [...ch.diff].reverse();
  diff.forEach((d) => applyEntry(s, d, forward));
  ch.targets.forEach((a) => { if (forward) s.provenance[a] = ch.change_id; else delete s.provenance[a]; });
  return s;
}

export function reduceEvent(v: RoomView, ev: MeetingEvent): RoomView {
  const next: RoomView = { ...v, events: [...v.events, ev] };
  if (ev.type.startsWith("change.")) {
    const ch = ev.payload as Change;
    next.changes = { ...v.changes, [ch.change_id]: ch };
    if (next.state && ev.type === "change.applied") next.state = applyChange(next.state, ch, true);
    if (next.state && ev.type === "change.reverted" && ch.diff.length) next.state = applyChange(next.state, ch, false);
  }
  if (ev.type === "participant.verified") next.participants = { ...v.participants, [ev.payload.name]: { verified: true } };
  if (ev.type === "agent.paused") next.paused = true;
  if (ev.type === "agent.resumed") next.paused = false;
  return next;
}

export function reduceMessage(v: RoomView, msg: ServerMessage): RoomView {
  switch (msg.kind) {
    case "snapshot":
      return {
        ...v, connected: true, state: msg.state, events: msg.events, participants: msg.participants, paused: msg.paused,
        changes: Object.fromEntries(msg.changes.map((c) => [c.change_id, c])),
      };
    case "event":
      return reduceEvent(v, msg.event);
    case "notice":
      return { ...v, notice: msg.text };
  }
}
