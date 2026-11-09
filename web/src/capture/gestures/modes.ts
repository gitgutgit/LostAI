// 모드 분리 (ARCHITECTURE 5-2-4): 손동작끼리 겹치지 않게.
// - join:    도전 손동작만
// - default: 공유 신호만 (엄지, 손가락 표결, T자) → 서버로
// - zoom:    포인터 + 확대·축소 + 주먹(100% 복귀)만 → 내 화면만, 서버로 안 보냄
import type { GestureKind } from "../../core/types";

export type Mode = "join" | "default" | "zoom";

export const HOLD_MS = 500;          // 오인식 방지: 0.5초 이상 유지
export const COOLDOWN_MS = 2000;     // 같은 신호 2초 쿨다운
export const MIN_CONFIDENCE = 0.6;
export const ZOOM_TOGGLE: GestureKind = "Victory"; // 브이 0.5초 유지로 확대 모드 켜기·끄기
export const ZOOM_AUTO_OFF_MS = 3000;              // 손이 3초 안 보이면 자동으로 꺼짐

const SHARED: GestureKind[] = ["Thumb_Up", "Thumb_Down", "T_Shape",
  "Fingers_0", "Fingers_1", "Fingers_2", "Fingers_3", "Fingers_4", "Fingers_5"];
const ZOOM: GestureKind[] = ["Pointing_Up", "Closed_Fist", "Open_Palm", "Victory"];

export function listens(mode: Mode, g: GestureKind, challenge?: GestureKind): boolean {
  if (mode === "join") return g === challenge;
  if (mode === "zoom") return ZOOM.includes(g);
  return SHARED.includes(g) || g === ZOOM_TOGGLE;
}

/** 공유 신호인가 (서버로 보낼 것인가) */
export const isShared = (mode: Mode, g: GestureKind) => mode === "default" && SHARED.includes(g);
