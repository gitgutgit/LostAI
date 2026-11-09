// hs: 제스처 카메라 초기화 + 포인터/줌 핸들러 커스텀 훅
// hs: CanvasView, LiveWallView 등 어디서든 import해서 쓸 수 있음
import { useEffect, useMemo } from "react";
import { engine } from "./engine";
import { isShared, HOLD_MS } from "./modes";
import { Viewport } from "./viewport";
import { send } from "../../core/ws";

/**
 * hs: 제스처 제어 훅. enabled가 true일 때만 카메라+엔진+포인터+줌이 동작한다.
 * @param getEl 줌 대상 HTMLElement를 반환하는 함수 (없으면 null)
 * @param enabled 제스처 활성화 여부 (기본 true)
 */
export function useGesture(getEl: () => HTMLElement | null, enabled = true) {
  const viewport = useMemo(() => new Viewport(getEl), []);

  // hs: enabled가 true일 때만 카메라+엔진 시작, false면 정리
  useEffect(() => {
    if (!enabled) {
      viewport.showCursor(false);
      viewport.resetScale();
      return;
    }
    let stream: MediaStream | null = null;
    let vid: HTMLVideoElement | null = null;
    let cancelled = false;
    (async () => {
      vid = document.createElement("video");
      vid.autoplay = true;
      vid.playsInline = true;
      vid.muted = true;
      vid.style.cssText = "position:fixed;width:1px;height:1px;opacity:0;pointer-events:none;";
      document.body.appendChild(vid);

      stream = await navigator.mediaDevices.getUserMedia(
        { video: { width: 640, height: 480, facingMode: "user" } }
      );
      if (cancelled) { stream.getTracks().forEach(t => t.stop()); return; }
      vid.srcObject = stream;
      await new Promise<void>(r => vid!.addEventListener("loadeddata", () => r(), { once: true }));
      if (cancelled) { stream.getTracks().forEach(t => t.stop()); return; }

      engine.mode = "default";
      await engine.start(vid);
    })();
    return () => {
      cancelled = true;
      engine.stop();
      stream?.getTracks().forEach(t => t.stop());
      if (vid?.parentNode) vid.parentNode.removeChild(vid);
      viewport.showCursor(false);
    };
  }, [enabled]);

  // hs: PoC 모드 로직 — enabled일 때만 동작
  useEffect(() => {
    if (!enabled) return;
    let lastSent = "";
    return engine.subscribe((f) => {
      const now = performance.now();

      if (!f.pointer) {
        viewport.showCursor(false);
      } else if (f.gesture === "Pointing_Up" && f.confidence > 0.5) {
        viewport.moveCursor(f.pointer);
        viewport.showCursor(true);
        viewport.setPointer(f.pointer, now);
      } else if (f.gesture === "Closed_Fist" && f.confidence > 0.6) {
        viewport.showCursor(true);
        viewport.snapMin();
      } else if (f.gesture === "Open_Palm" && f.confidence > 0.6) {
        viewport.showCursor(true);
        viewport.snapMax();
      } else if (f.openness != null) {
        viewport.showCursor(true);
        viewport.setOpenness(f.openness);
      }

      if (!f.gesture || f.hold_ms < HOLD_MS) { lastSent = ""; return; }
      if (isShared(engine.mode, f.gesture) && lastSent !== f.gesture) {
        lastSent = f.gesture;
        send({ kind: "gesture", payload: { kind: f.gesture, confidence: f.confidence, hold_ms: f.hold_ms } });
      }
    });
  }, [viewport, enabled]);

  return viewport;
}
