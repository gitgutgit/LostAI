// 이벤트 store: WebSocket 또는 fixture 재생에서 메시지를 받아 RoomView 하나를 유지한다.
import { useSyncExternalStore } from "react";
import { initialView, reduceMessage, type RoomView } from "./reducer";
import type { ServerMessage } from "./types";

let view: RoomView = initialView;
const listeners = new Set<() => void>();

export function dispatch(msg: ServerMessage) {
  view = reduceMessage(view, msg);
  listeners.forEach((l) => l());
}

export function resetView() {
  view = initialView;
  listeners.forEach((l) => l());
}

export function useRoom(): RoomView {
  return useSyncExternalStore(
    (l) => { listeners.add(l); return () => listeners.delete(l); },
    () => view,
  );
}
