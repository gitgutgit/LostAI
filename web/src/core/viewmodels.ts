// 화면별 뷰 모델 (ARCHITECTURE 7절). B(canvas)부터.
import type { RoomView } from "./reducer";
import type { Change, MeetingEvent } from "./types";

export interface TimelineEntry {
  utt: MeetingEvent;
  label?: string;
  changes: Change[];
  answer?: string;
  stage?: string;
}

/** B: 발화마다 그 발화가 만든 변경·답변·진행 상태를 묶는다. */
export function timeline(v: RoomView): TimelineEntry[] {
  const byUtt = new Map<string, TimelineEntry>();
  const out: TimelineEntry[] = [];
  for (const ev of v.events) {
    const id = ev.refs.utt_id;
    if (ev.type === "utterance.final" && id) {
      const e: TimelineEntry = { utt: ev, changes: [] };
      byUtt.set(id, e);
      out.push(e);
      continue;
    }
    const e = id ? byUtt.get(id) : undefined;
    if (!e) continue;
    if (ev.type === "agent.routed") e.label = ev.payload.label;
    if (ev.type === "agent.progress") e.stage = ev.payload.stage;
    if (ev.type === "ask.answered") e.answer = ev.payload.answer;
  }
  for (const ch of Object.values(v.changes)) {
    const e = ch.utt_id ? byUtt.get(ch.utt_id) : undefined;
    if (e) e.changes.push(ch);
  }
  return out;
}

/** B: 앵커 → 최근 변경 (칸 하이라이트, 칸 팝오버). */
export function cellIndex(v: RoomView): Record<string, Change> {
  const out: Record<string, Change> = {};
  if (!v.state) return out;
  for (const [anchor, cid] of Object.entries(v.state.provenance)) {
    const ch = v.changes[cid];
    if (ch) out[anchor] = ch;
  }
  return out;
}

/** B: 문서 탭별 변경 수 (마지막 확인 이후). */
export function docTabCounts(v: RoomView, seenSeq: Record<string, number>): Record<string, number> {
  const out: Record<string, number> = {};
  for (const ev of v.events) {
    if (ev.type !== "change.applied") continue;
    for (const a of (ev.payload as Change).targets) {
      const doc = a.split("/")[0];
      if (ev.seq > (seenSeq[doc] ?? 0)) out[doc] = (out[doc] ?? 0) + 1;
    }
  }
  return out;
}
