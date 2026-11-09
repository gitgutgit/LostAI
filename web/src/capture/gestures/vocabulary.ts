// 손동작 정의: MediaPipe 기본 제스처 + 랜드마크 규칙(손가락 개수, T자).
import type { GestureKind } from "../../core/types";

export const BUILTIN: GestureKind[] = ["Thumb_Up", "Thumb_Down", "Pointing_Up", "Victory", "Open_Palm", "Closed_Fist", "ILoveYou"];

export interface Landmark { x: number; y: number; z: number }

const TIPS = [8, 12, 16, 20];
const PIPS = [6, 10, 14, 18];

/** 21개 랜드마크로 펴진 손가락 개수 (손바닥이 카메라를 향한다고 가정). */
export function countFingers(lm: Landmark[]): number {
  let n = 0;
  TIPS.forEach((tip, i) => { if (lm[tip].y < lm[PIPS[i]].y) n++; });
  if (Math.abs(lm[4].x - lm[17].x) > Math.abs(lm[3].x - lm[17].x)) n++; // 엄지
  return n;
}

/** 손을 편 정도 0..1 (손목→손끝 거리 / 손 크기). 확대·축소에 쓴다. 보정값은 입장 직후 저장. */
export function openness(lm: Landmark[], calib = { fist: 0.9, palm: 2.0 }): number {
  const d = (a: Landmark, b: Landmark) => Math.hypot(a.x - b.x, a.y - b.y);
  const size = d(lm[0], lm[9]) || 1e-6;
  const raw = TIPS.reduce((s, t) => s + d(lm[0], lm[t]), 0) / TIPS.length / size;
  return Math.min(1, Math.max(0, (raw - calib.fist) / (calib.palm - calib.fist)));
}

/** T자 (두 손, P2): TODO */
export function isTShape(_hands: Landmark[][]): boolean {
  return false;
}

/** 같은 도전에 같이 넣지 않는 헷갈리는 쌍 — 서버 server/auth/challenge.py CONFUSABLE 와 맞춘다. */
export const CONFUSABLE: [GestureKind, GestureKind][] = [["Victory", "Fingers_2"], ["Open_Palm", "Fingers_5"], ["Pointing_Up", "Fingers_1"]];
