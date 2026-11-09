// 변경(Change)을 사람이 읽는 한국어 한 줄로 바꾼다. 회의록 카드와 전문 보기가 쓴다.
// author: ProfessionalSeaweedDevourer
import type { Change, ChangeStatus, DiffEntry, Doc, DocState, Sheet } from "../core/types";

export const STATUS_TEXT: Record<ChangeStatus, string> = {
  proposed: "제안",
  applied: "반영",
  approved: "승인됨",
  reverted: "되돌림",
  discarded: "취소",
  failed: "실패",
};

const OP_TEXT: Record<string, string> = {
  set_cell: "칸 수정", add_row: "행 추가", delete_row: "행 삭제",
  insert_item: "항목 추가", update_item: "항목 수정", delete_item: "항목 삭제",
  add_section: "섹션 추가", rename_section: "섹션 이름 변경",
  add_decision: "결정 기록", add_action: "할 일 기록", claim_action: "할 일 담당",
  add_note: "메모", create_ticket: "티켓 생성", open_conflict: "의견 충돌 열림",
  resolve_conflict: "의견 충돌 정리", undo_last: "방금 것 취소",
};

const show = (v: unknown) => (v === null || v === undefined || v === "" ? "빈칸" : String(v));
const clip = (t: string, n = 48) => (t.length > n ? `${t.slice(0, n - 1)}…` : t);

function rowName(sheet: Sheet | undefined, rowId: string, fallback?: Record<string, unknown>): string {
  const row = sheet?.rows.find((r) => r.row_id === rowId);
  const cells = (row?.cells ?? fallback ?? {}) as Record<string, unknown>;
  const first = sheet?.columns.map((c) => cells[c]).find((v) => v !== null && v !== undefined && v !== "");
  return clip(String(first ?? rowId), 24);
}

/** diff 한 줄 → "보드 PAY-423 추정: 5 → 3" 같은 문장. */
export function diffText(d: DiffEntry, s: DocState | null): string {
  const p = d.anchor.split("/");
  const doc = s?.docs[p[0]];
  const docTitle = doc?.title ?? p[0];
  switch (d.kind) {
    case "cell": {
      const sheet = doc?.kind === "sheet" ? (doc as Sheet) : undefined;
      return `${docTitle} ${rowName(sheet, p[1])} ${p[2]}: ${show(d.before)} → ${show(d.after)}`;
    }
    case "row": {
      const sheet = doc?.kind === "sheet" ? (doc as Sheet) : undefined;
      const cells = (d.after ?? d.before)?.cells;
      if (d.before === null) return `${docTitle}에 행 추가: ${rowName(sheet, p[1], cells)}`;
      if (d.after === null) return `${docTitle}에서 행 삭제: ${rowName(sheet, p[1], cells)}`;
      return `${docTitle} 행 수정: ${rowName(sheet, p[1], cells)}`;
    }
    case "item": {
      const sec = doc?.kind === "doc" ? (doc as Doc).sections.find((x) => x.section_id === p[1]) : undefined;
      const where = sec?.heading ?? p[1];
      if (d.before === null) return `${where}에 추가: ${clip(d.after?.text ?? "")}`;
      if (d.after === null) return `${where}에서 삭제: ${clip(d.before?.text ?? "")}`;
      return `${where} 수정: ${clip(d.before?.text ?? "", 20)} → ${clip(d.after?.text ?? "", 24)}`;
    }
    case "section": return d.after ? `섹션 추가: ${d.after.heading}` : `섹션 삭제: ${d.before?.heading ?? p[1]}`;
    case "heading": return `섹션 이름: ${show(d.before)} → ${show(d.after)}`;
    case "ticket": return `티켓: ${clip((d.after ?? d.before)?.title ?? "")}`;
    case "conflict": return d.after?.resolved ? `의견 충돌 정리: ${clip(d.after?.topic ?? "")}` : `의견 충돌: ${clip((d.after ?? d.before)?.topic ?? "")}`;
  }
  return d.anchor;
}

/** 변경 전체를 한 줄로. diff가 없으면(실패 등) op 이름으로. */
export function changeHeadline(ch: Change, s: DocState | null): string {
  if (ch.diff.length > 0) {
    const first = diffText(ch.diff[0], s);
    return ch.diff.length > 1 ? `${first} 외 ${ch.diff.length - 1}건` : first;
  }
  return ch.ops.map((o) => OP_TEXT[o.op] ?? o.op).join(", ");
}

/** 회의 시작 기준 초 → "03:07". */
export function clock(ts: number): string {
  const t = Math.max(0, Math.floor(ts));
  return `${String(Math.floor(t / 60)).padStart(2, "0")}:${String(t % 60).padStart(2, "0")}`;
}
