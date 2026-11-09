// 음성 인식: Chrome Web Speech 기본 (Deepgram은 P2). localhost 또는 https에서만 마이크가 열린다.
// 상태를 onStatus로 알려서 화면에서 "왜 안 되는지"를 바로 보이게 한다.
import { send } from "../core/ws";

type Rec = any; // webkitSpeechRecognition 타입이 표준 lib에 없다

export type SttStatus =
  | { kind: "off" }
  | { kind: "listening" }
  | { kind: "unsupported" }   // 브라우저에 Web Speech 없음 (Chrome/Edge 사용)
  | { kind: "insecure" }      // http(로컬 아님) → 마이크 못 엶
  | { kind: "denied" }        // 마이크 권한 거부
  | { kind: "error"; code: string };

export interface SttOptions {
  lang?: string;
  onStatus?: (s: SttStatus) => void;
  onInterim?: (text: string) => void; // 화면에 "듣는 중…" 미리보기용
}

/** 기본 언어: URL ?lang=en-US 로 바꿀 수 있다. 시드 문서가 한국어라 ko-KR. */
export function defaultLang(): string {
  return new URLSearchParams(location.search).get("lang") ?? "ko-KR";
}

export function startStt(opts: SttOptions = {}): () => void {
  const status = opts.onStatus ?? (() => {});
  const Ctor = (window as any).SpeechRecognition ?? (window as any).webkitSpeechRecognition;
  if (!window.isSecureContext) {
    status({ kind: "insecure" });
    return () => {};
  }
  if (!Ctor) {
    status({ kind: "unsupported" });
    return () => {};
  }
  const rec: Rec = new Ctor();
  rec.lang = opts.lang ?? defaultLang();
  rec.continuous = true;
  rec.interimResults = true;
  let stopped = false;
  rec.onstart = () => status({ kind: "listening" });
  rec.onresult = (e: any) => {
    for (let i = e.resultIndex; i < e.results.length; i++) {
      const r = e.results[i];
      const text = r[0].transcript.trim();
      if (!text) continue;
      if (!r.isFinal) opts.onInterim?.(text);
      else opts.onInterim?.("");
      send({ kind: r.isFinal ? "utterance.final" : "utterance.interim", payload: { text } });
    }
  };
  rec.onerror = (e: any) => {
    if (e.error === "no-speech" || e.error === "aborted") return; // 조용함 → onend에서 다시 켬
    if (e.error === "not-allowed" || e.error === "service-not-allowed") {
      stopped = true;
      status({ kind: "denied" });
      return;
    }
    status({ kind: "error", code: e.error });
  };
  rec.onend = () => {
    if (stopped) return;
    try { rec.start(); } catch { /* 이미 시작됨 */ } // Chrome은 조용하면 끊는다
  };
  rec.start();
  return () => {
    stopped = true;
    rec.stop();
    status({ kind: "off" });
  };
}

export function sttStatusText(s: SttStatus): string {
  switch (s.kind) {
    case "off": return "마이크 꺼짐";
    case "listening": return "듣는 중";
    case "unsupported": return "이 브라우저는 음성 인식 미지원 (Chrome 사용)";
    case "insecure": return "https 또는 localhost에서만 마이크 사용 가능";
    case "denied": return "마이크 권한 거부됨 (주소창 자물쇠 → 마이크 허용)";
    case "error": return `음성 인식 오류: ${s.code}`;
  }
}
