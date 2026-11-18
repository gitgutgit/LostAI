// hs: 제스처 카메라 초기화 + 포인터/줌 핸들러 커스텀 훅
// hs: CanvasView, LiveWallView 등 어디서든 import해서 쓸 수 있음
import { useEffect, useMemo } from "react";
import { engine } from "./engine";
import { isShared, HOLD_MS } from "./modes";
import { Viewport } from "./viewport";
import { send } from "../../core/ws";
import type { GestureKind } from "../../core/types";

const FIST_OFF_MS = 2000; // hs: Closed_Fist 2초 유지 → Gesture Off

/**
 * hs: 제스처 제어 훅. enabled가 true일 때만 카메라+엔진+포인터+줌이 동작한다.
 * @param getEl 줌 대상 HTMLElement를 반환하는 함수 (없으면 null)
 * @param enabled 제스처 활성화 여부 (기본 true)
 * @param onDisable Thumb_Down 3초로 제스처 끌 때 호출되는 콜백
 */
/** gitgutgit: voteOnly = 표결 중. 손 랜드마크로 센 손가락 1~4를 0.5초 유지하면 표로 보내고, 확대·포인터는 끈다.
 *  onCamera = 카메라를 켰는지/못 켰는지(이유 문장) 알려 준다. */
export interface GestureOptions { voteOnly?: boolean; onCamera?: (s: { ok: true } | { ok: false; reason: string }) => void }

function cameraReason(e: unknown): string {
  const name = (e as { name?: string })?.name ?? "";
  if (!window.isSecureContext) return "카메라는 localhost나 https 주소에서만 열려요.";
  if (name === "NotAllowedError" || name === "SecurityError") return "카메라 권한이 꺼져 있어요. 주소창 왼쪽 자물쇠 → 카메라 허용 후 새로고침하세요.";
  if (name === "NotReadableError" || name === "AbortError") return "다른 앱(Zoom, FaceTime 등)이 카메라를 쓰고 있어요. 그 앱을 닫고 다시 해 보세요.";
  if (name === "NotFoundError" || name === "OverconstrainedError") return "카메라를 찾지 못했어요.";
  return `카메라를 못 열었어요 (${name || String(e)}).`;
}

export function useGesture(getEl: () => HTMLElement | null, enabled = true, onDisable?: () => void, opts: GestureOptions = {}) {
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
      vid.style.cssText = "position:fixed;bottom:8px;right:8px;width:160px;border-radius:12px;transform:scaleX(-1);z-index:50;border:2px solid #333;";
      document.body.appendChild(vid);

      try {
        if (!navigator.mediaDevices?.getUserMedia) throw Object.assign(new Error("no mediaDevices"), { name: "SecurityError" });
        stream = await navigator.mediaDevices.getUserMedia(
          { video: { width: 640, height: 480, facingMode: "user" } }
        );
      } catch (e) {
        if (vid?.parentNode) vid.parentNode.removeChild(vid);
        if (!cancelled) opts.onCamera?.({ ok: false, reason: cameraReason(e) });
        return;
      }
      if (cancelled) { stream.getTracks().forEach(t => t.stop()); return; }
      vid.srcObject = stream;
      await new Promise<void>(r => vid!.addEventListener("loadeddata", () => r(), { once: true }));
      if (cancelled) { stream.getTracks().forEach(t => t.stop()); return; }

      engine.mode = "default";
      try {
        await engine.start(vid);
        if (!cancelled) opts.onCamera?.({ ok: true });
      } catch {
        if (!cancelled) opts.onCamera?.({ ok: false, reason: "손 인식 모델을 받지 못했어요. 인터넷 연결을 확인하세요." });
      }
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
  // hs: 손가락 2개 이상 = 줌(커서 고정), 1개 이하 = 커서 이동, Fist = 최소, Palm = 최대
  useEffect(() => {
    if (!enabled) return;
    let lastSent = "";
    // gitgutgit: 표결 중 — 손가락 수(랜드마크)만 본다. 1개는 Pointing_Up, 2개는 Victory로 이름 붙어도 1·2로 센다.
    // hs: 안정화 — 손가락 수가 1~2프레임 흔들려도 hold를 리셋하지 않음 (STABLE_FRAMES만큼 연속 바뀌어야 리셋)
    if (opts.voteOnly) {
      viewport.showCursor(false);
      const VOTE_HOLD_MS = 350; // hs: 투표 모드에서는 0.35초로 줄여 인식 반응성 개선
      const STABLE_FRAMES = 3;  // hs: 3프레임(~200ms) 연속 바뀌어야 손가락 수 변경 인정
      let held: { n: number | null; since: number } = { n: null, since: 0 };
      let diffCount = 0;
      let lastDiffN: number | null = null;
      return engine.subscribe((f) => {
        const now = performance.now();
        const n = f.fingers != null && f.fingers >= 1 && f.fingers <= 4 ? f.fingers : null;
        if (n !== held.n) {
          // hs: 같은 다른 값이 연속으로 나와야 변경 인정
          if (n === lastDiffN) { diffCount++; } else { diffCount = 1; lastDiffN = n; }
          if (diffCount >= STABLE_FRAMES) { held = { n, since: now }; diffCount = 0; }
        } else { diffCount = 0; lastDiffN = null; }
        if (held.n == null) { lastSent = ""; return; }
        if (now - held.since >= VOTE_HOLD_MS && lastSent !== `Fingers_${held.n}`) {
          lastSent = `Fingers_${held.n}`;
          send({ kind: "gesture", payload: { kind: `Fingers_${held.n}` as GestureKind, confidence: 0.9, hold_ms: Math.round(now - held.since) } });
        }
      });
    }
    return engine.subscribe((f) => {
      const now = performance.now();

      // hs: 제스처 이름에서 손가락 개수 추출 (Fingers_0 ~ Fingers_5)
      const fingerMatch = f.gesture?.match(/^Fingers_(\d)$/);
      const fingers = fingerMatch ? Number(fingerMatch[1]) : null;
      // hs: 2개 이상 펴져있거나, Victory/ILoveYou 등 멀티핑거 제스처 → 줌 모드
      const isZoom = (fingers != null && fingers >= 2) || f.gesture === "Victory" || f.gesture === "ILoveYou";

      if (!f.pointer) {
        viewport.showCursor(false);
      } else if (f.gesture === "Closed_Fist" && f.confidence > 0.6) {
        // hs: 주먹 → 커서 고정 + 최소
        viewport.showCursor(true);
        viewport.snapMin();
      } else if (f.gesture === "Open_Palm" && f.confidence > 0.6) {
        // hs: 손바닥 → 커서 고정 + 최대
        viewport.showCursor(true);
        viewport.snapMax();
      } else if (isZoom && f.openness != null) {
        // hs: 손가락 2개+ → 커서 완전 고정, 줌만 적용
        viewport.showCursor(true);
        viewport.setOpenness(f.openness);
      } else {
        // hs: 손가락 0~1개 → 커서 이동
        viewport.moveCursor(f.pointer);
        viewport.showCursor(true);
        viewport.setPointer(f.pointer, now);
      }

      // hs: Closed_Fist 2초 유지 → Gesture Off + 화면 디폴트 사이즈
      if (f.gesture === "Closed_Fist" && f.hold_ms >= FIST_OFF_MS && onDisable) {
        viewport.resetScale();
        viewport.showCursor(false);
        onDisable();
        return;
      }

      if (!f.gesture || f.hold_ms < HOLD_MS) { lastSent = ""; return; }
      if (isShared(engine.mode, f.gesture) && lastSent !== f.gesture) {
        lastSent = f.gesture;
        send({ kind: "gesture", payload: { kind: f.gesture, confidence: f.confidence, hold_ms: f.hold_ms } });
      }
    });
  }, [viewport, enabled, onDisable, opts.voteOnly]);

  return viewport;
}
