// 결정 벽(렌더 v0.4) 화면의 뷰 모델. 장면 견본(scenes.ts)과 실시간 이벤트(live.ts)가 모두 이 모양을 만든다.
// author: ProfessionalSeaweedDevourer
import type { MoaiState } from "../brand/moaiState";

/** 글 조각: 문자열, 출처 줄 참조(L6), 굵게, 빨강, 칩. */
export type Seg =
  | string
  | { ref: string }
  | { b: string }
  | { bad: string }
  | { chip: Chip }
  | { tag: string };
export type Rich = Seg[];

export interface Chip { t: string; r?: string; cls?: "undo" | "tag" | "ok" | "red" | "" }

/** 칸 값: 옛 값(줄긋기)과 새 값. br이면 옛 값 아래 줄에 새 값. */
export interface CellVal { v: string; old?: string; br?: boolean }

export type CellKey = "o" | "s" | "e" | "d" | "st";

export interface DocRow {
  w: string; t: string;
  o: CellVal; s: CellVal; e: CellVal; d: CellVal; st: CellVal;
  src: Chip[];
  /** 방금 고친 칸: 키 → 빛나기 지연(ms). */
  fresh?: Partial<Record<CellKey, number>>;
  memo?: { t: string; c?: Chip; bad?: boolean; fresh?: boolean } | null;
  hl?: boolean; newrow?: boolean; rowfresh?: boolean; tall?: boolean;
  /** 엇갈린 칸: 두 사람이 다른 값을 말함. */
  cf?: { a: CfSide; b: CfSide };
  /** 카드 A가 이 칸에서 떠오르거나 내려앉는다(View Transition 이름 공유). */
  vt?: boolean;
  /** 유령 값: 선택지별 끝 날짜. */
  gh?: [string, string]; ghbad?: boolean; ghref?: string;
  wrapO?: boolean;
}

export interface CfSide { who: string; r: string; v: string; short: string }

export interface DocModel {
  title: string; subtitle: string;
  edits: number; undone: number;
  note: Rich;
  ghost?: { cols: [string, string] };
  /** 열 머리 7개(WBS, Task, Owner, Start, End, Days, State). 없으면 시안 머리. 실시간 시트는 시트 열 이름을 쓴다. */
  cols?: string[];
  /** 실시간 시트용: 없는 열은 숨기고(hide) 열 폭을 내용에 맞춘다(grid). 시안 장면은 쓰지 않는다. */
  hide?: CellKey[];
  grid?: string;
  rows: DocRow[];
}

export interface CardOption { n: number; name: string; src: Rich; side?: { cost: Rich; sub: Rich } }
export interface CardA {
  q: string; title: string;
  /** 문서 칸(3.3)에서 떠오른 질문이면 칸과 View Transition 이름을 주고받는다. */
  fromCell?: boolean;
  options?: CardOption[];
  reframe?: { old?: string; now: string; vt: string };
}

export type CardBMsg =
  | { kind: "headline"; big: Rich; bigCls?: "b40" | "b32" | "b28 clamp3"; underline?: boolean; sub?: Rich; subTop?: number }
  | { kind: "facts"; title: string; chips: Chip[] }
  | { kind: "sentence"; sentence: string; big: Rich }
  | { kind: "costs"; line: Rich; sub: string; bandSub: string }
  | { kind: "countdown"; q: string; title: string; prompt: string }
  | { kind: "split"; q: string; title: string; lines: string[] }
  | { kind: "converged"; q: string; moved: number; from: [number, string]; to: [number, string]; dist: [number, string, number][]; foot: string;
      /** 실화면 첫 표결: 재투표 문구 대신 질문, 이긴 선택지, 표 수. */ first?: { title: string; winner: string; sub: string } }
  | { kind: "closed"; title: string; cards: EndCard[]; stats: [string, string, string?][]; foot: string };

export interface EndCard { q: string; title: string; lines: { rich: Rich; green?: boolean }[]; parked?: boolean }

export type Take = "count" | "split" | "navy conv" | "navy end";

export interface CardB { flap: string; off?: number[]; take?: Take; side?: string; msg: CardBMsg }

export type SlotState = "" | "now" | "done" | "park";

export interface Person { name: string; status: string; tone: "" | "ok" | "again" }

export interface Utter { line: string; who: string; text: string }

export interface WallState {
  mark: string;
  /** MOAI status light in #mark for scripted scenes; when set it replaces the mark text. */
  moai?: MoaiState;
  slots: SlotState[];
  decided: number; total: number;
  /** 머리줄 진행 문구. 없으면 'N of M decided'. */
  progText?: string;
  now: string;
  doc: DocModel;
  cardA: CardA | null;
  idle: string[] | null;
  cardB: CardB;
  decidedMarks: string[];
  parked: { q: string; text: string; ref?: string }[];
  said: Utter[];
  log: Rich;
  people: Person[];
  turn?: number;
  glyph?: "cam" | "fd" | "thumb" | "";
  big?: boolean;
  lit: string[];
}
