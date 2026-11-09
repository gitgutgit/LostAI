// TODO(P1): MediaPipe 인식을 Web Worker로 옮긴다 (메인 스레드에서 STT·WS·화면 갱신과 부딪힘).
// main → worker: ImageBitmap (createImageBitmap(video)), ts
// worker → main: EngineFrame (engine.ts 와 같은 형식)
export {};
