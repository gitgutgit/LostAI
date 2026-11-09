// MOAI mascot state, derived from the room view only (no new events, no contract change).
// Priority: open vote > open conflict or paused agent > editing, proposed or just applied > listening.
// "decided" is a one-shot pulse: the seq of the latest change.applied that resolved a conflict.
// The component holds it on screen for a moment; this function stays clock-free so it can be replayed.
import type { MeetingEvent } from "../../core/types";
import type { RoomView } from "../../core/reducer";

export type MoaiBase = "listening" | "writing" | "paused" | "vote";
export type MoaiState = MoaiBase | "decided";

export interface MoaiSignal {
  base: MoaiBase;
  /** seq of the latest conflict resolution, or null if none yet */
  decidedSeq: number | null;
  /** paused because of an open conflict (true) or by a pause command (false) */
  conflict: boolean;
}

const lastOf = (ev: MeetingEvent[], pred: (e: MeetingEvent) => boolean): MeetingEvent | undefined => {
  for (let i = ev.length - 1; i >= 0; i--) if (pred(ev[i])) return ev[i];
  return undefined;
};

const resolves = (e: MeetingEvent) =>
  e.type === "change.applied" && Array.isArray(e.payload?.ops) && e.payload.ops.some((o: any) => o?.op === "resolve_conflict");

export function moaiSignal(v: Pick<RoomView, "events" | "state" | "paused">): MoaiSignal {
  const ev = v.events;
  const decidedSeq = lastOf(ev, resolves)?.seq ?? null;

  const opened = lastOf(ev, (e) => e.type === "vote.opened");
  if (opened) {
    const id = opened.refs?.vote_id;
    const closed = lastOf(ev, (e) => e.type === "vote.closed" && e.refs?.vote_id === id && e.seq > opened.seq);
    if (!closed) return { base: "vote", decidedSeq, conflict: false };
  }

  const conflict = (v.state?.conflicts ?? []).some((c) => !c.resolved);
  if (conflict || v.paused) return { base: "paused", decidedSeq, conflict };

  const work = lastOf(ev, (e) => e.type === "agent.progress" || e.type.startsWith("change."));
  // editing -> proposed -> applied all count as writing, so the face does not flicker between steps
  if (work && ((work.type === "agent.progress" && work.payload?.stage === "editing") || work.type === "change.proposed" || work.type === "change.applied")) {
    return { base: "writing", decidedSeq, conflict: false };
  }
  return { base: "listening", decidedSeq, conflict: false };
}

export const MOAI_LABEL: Record<MoaiState, string> = {
  listening: "Listening",
  writing: "Writing",
  paused: "Paused: conflict",
  vote: "Vote",
  decided: "Decided",
};
