// ← 계약 파일. server/events.py · server/model/docs.py · server/ops/registry.py 의 TS 사본.
// 서버 쪽을 바꾸면 반드시 같이 바꾼다 (init-collab §2).

// ---- events.py ----
export type EventType =
  | "participant.joined" | "participant.verified" | "participant.rejected" | "participant.left"
  | "utterance.interim" | "utterance.final"
  | "gesture"
  | "vote.opened" | "vote.cast" | "vote.closed"
  | "agent.routed" | "agent.progress"
  | "change.proposed" | "change.applied" | "change.approved" | "change.reverted" | "change.discarded" | "change.failed"
  | "ask.answered"
  | "sync.ok" | "sync.failed" | "doc.pulled"
  | "agent.paused" | "agent.resumed" | "room.reset";

export type RouteLabel = "ignore" | "capture" | "edit" | "command" | "ask";

export type GestureKind =
  | "Thumb_Up" | "Thumb_Down" | "Pointing_Up" | "Victory" | "Open_Palm" | "Closed_Fist" | "ILoveYou"
  | "Fingers_0" | "Fingers_1" | "Fingers_2" | "Fingers_3" | "Fingers_4" | "Fingers_5"
  | "T_Shape";

export interface Refs { utt_id?: string | null; change_id?: string | null; vote_id?: string | null }

export interface MeetingEvent {
  seq: number;
  ts: number;
  type: EventType;
  actor: string;
  refs: Refs;
  payload: Record<string, any>;
}

export type ClientMessage =
  | { kind: "utterance.interim" | "utterance.final"; payload: { text: string } }
  | { kind: "gesture"; payload: { kind: GestureKind; confidence: number; hold_ms: number } }
  | { kind: "change.approve" | "change.revert"; payload: { change_id: string } };

// ---- model/docs.py ----
export interface Row { row_id: string; cells: Record<string, string | number | null> }
export interface Sheet { kind: "sheet"; title: string; columns: string[]; rows: Row[] }
export interface Item { item_id: string; text: string; meta: Record<string, any> }
export type Binding = "decisions" | "risks" | "actions" | "notes";
export interface Section { section_id: string; heading: string; binding: Binding | null; items: Item[] }
export interface Doc { kind: "doc"; title: string; sections: Section[] }
export type AnyDoc = Sheet | Doc;
export interface Conflict { conflict_id: string; topic: string; positions: { who: string; says: string }[]; resolved: boolean; resolution: string | null }
export interface Ticket { ticket_id: string; title: string; assignee: string | null; external_id: string | null }
export interface DocState {
  docs: Record<string, AnyDoc>;
  conflicts: Conflict[];
  tickets: Ticket[];
  provenance: Record<string, string>; // anchor → change_id
}

// ---- ops/registry.py · ops/changes.py ----
export type OpName =
  | "set_cell" | "add_row" | "delete_row"
  | "insert_item" | "update_item" | "delete_item" | "add_section" | "rename_section"
  | "add_decision" | "add_action" | "claim_action" | "add_note" | "create_ticket" | "open_conflict" | "resolve_conflict"
  | "undo_last";
export interface Op { op: OpName; [k: string]: any }

export type DiffKind = "cell" | "row" | "item" | "section" | "heading" | "ticket" | "conflict";
export interface DiffEntry { kind: DiffKind; anchor: string; before: any; after: any; index?: number }

export type ChangeStatus = "proposed" | "applied" | "approved" | "reverted" | "discarded" | "failed";
export interface Change {
  change_id: string;
  utt_id: string | null;
  requested_by: string;
  via: "voice" | "gesture" | "button";
  ops: Op[];
  targets: string[];
  diff: DiffEntry[];
  status: ChangeStatus;
  policy: "immediate" | "delayed";
  reason: string | null;
  error: string | null;
  approvals: { by: string; via: string; ts: number; action?: string }[];
  latency_ms: Record<string, number>;
  applied_ts: number | null;
}

// ---- 서버 → 클라이언트 메시지 ----
export type ServerMessage =
  | { kind: "snapshot"; room_id: string; state: DocState; changes: Change[]; events: MeetingEvent[]; participants: Record<string, any>; paused: boolean }
  | { kind: "event"; event: MeetingEvent }
  | { kind: "notice"; text: string };
