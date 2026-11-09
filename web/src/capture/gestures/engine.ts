// 손 인식 엔진 (PoC-hs PaHsGestureEngine에서 출발).
// 내보내는 것: {mode, gesture, confidence, hold_ms, pointer, openness} 하나로 통일 (ARCHITECTURE 5-2-4).
// TODO(P1): engine.worker.ts 로 옮기기. 지금은 메인 스레드에서 초당 15프레임으로 제한.
import { FilesetResolver, GestureRecognizer } from "@mediapipe/tasks-vision";
import type { GestureKind } from "../../core/types";
import { countFingers, openness, type Landmark } from "./vocabulary";
import type { Mode } from "./modes";

export interface EngineFrame {
  mode: Mode;
  gesture: GestureKind | null;
  confidence: number;
  hold_ms: number;
  pointer: { x: number; y: number } | null;
  openness: number | null;
}

const WASM = "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.18/wasm";
const MODEL = "https://storage.googleapis.com/mediapipe-models/gesture_recognizer/gesture_recognizer/float16/1/gesture_recognizer.task";
const FPS = 15;

export class GestureEngine {
  mode: Mode = "join";
  private rec: GestureRecognizer | null = null;
  private subs = new Set<(f: EngineFrame) => void>();
  private held: { g: GestureKind | null; since: number } = { g: null, since: 0 };
  private timer = 0;

  async start(video: HTMLVideoElement) {
    const vision = await FilesetResolver.forVisionTasks(WASM);
    this.rec = await GestureRecognizer.createFromOptions(vision, {
      baseOptions: { modelAssetPath: MODEL, delegate: "GPU" },
      runningMode: "VIDEO",
      numHands: 1, // T자(P2)는 2
    });
    this.timer = window.setInterval(() => this.tick(video), 1000 / FPS);
  }

  stop() { clearInterval(this.timer); this.rec?.close(); this.rec = null; } // hs: rec null 처리 — 재시작 시 새로 생성되도록

  subscribe(fn: (f: EngineFrame) => void): () => void { this.subs.add(fn); return () => { this.subs.delete(fn); }; }

  private tick(video: HTMLVideoElement) {
    if (!this.rec || video.readyState < 2) return;
    const now = performance.now();
    const res = this.rec.recognizeForVideo(video, now);
    const lm = res.landmarks?.[0] as Landmark[] | undefined;
    let gesture: GestureKind | null = null;
    let confidence = 0;
    const top = res.gestures?.[0]?.[0];
    if (top && top.categoryName !== "None") {
      gesture = top.categoryName as GestureKind;
      confidence = top.score;
    } else if (lm) {
      gesture = `Fingers_${countFingers(lm)}` as GestureKind;
      confidence = 0.7;
    }
    if (gesture !== this.held.g) this.held = { g: gesture, since: now };
    const frame: EngineFrame = {
      mode: this.mode,
      gesture,
      confidence,
      hold_ms: gesture ? Math.round(now - this.held.since) : 0,
      pointer: lm ? { x: 1 - lm[8].x, y: lm[8].y } : null, // 거울 모드
      openness: lm ? openness(lm) : null,
    };
    this.subs.forEach((fn) => fn(frame));
  }
}

export const engine = new GestureEngine();
