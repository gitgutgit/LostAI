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

const INTERIM_MIN_GAP_MS = 250;
const MAX_FAILURES = 5;

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
  let failures = 0;          // 연속 실패 횟수: 결과가 오면 0으로
  let retry: number | undefined;
  let lastInterim = "", lastInterimAt = 0;
  rec.onstart = () => status({ kind: "listening" });
  rec.onresult = (e: any) => {
    failures = 0;
    for (let i = e.resultIndex; i < e.results.length; i++) {
      const r = e.results[i];
      const text = r[0].transcript.trim();
      if (!text) continue;
      if (r.isFinal) {
        opts.onInterim?.("");
        lastInterim = "";
        send({ kind: "utterance.final", payload: { text } });
        continue;
      }
      opts.onInterim?.(text); // 내 화면 미리보기는 매번
      // 서버(=이벤트 로그)에는 바뀌었을 때만, 최대 4번/초. 로그가 interim으로 넘치지 않게.
      const now = performance.now();
      if (text !== lastInterim && now - lastInterimAt >= INTERIM_MIN_GAP_MS) {
        lastInterim = text; lastInterimAt = now;
        send({ kind: "utterance.interim", payload: { text } });
      }
    }
  };
  rec.onerror = (e: any) => {
    if (e.error === "no-speech" || e.error === "aborted") return; // 조용함 → onend에서 다시 켬
    if (e.error === "not-allowed" || e.error === "service-not-allowed") {
      stopped = true;
      status({ kind: "denied" });
      return;
    }
    failures++; // audio-capture(마이크 없음)·network(Chrome 음성 서버) 등 → onend에서 늦춰서 다시
    status({ kind: "error", code: e.error });
  };
  rec.onend = () => {
    if (stopped) return;
    if (failures >= MAX_FAILURES) { stopped = true; status({ kind: "error", code: `${failures}번 연속 실패, 🎙 다시 켜 주세요` }); return; }
    // Chrome은 조용하면(또는 약 1분마다) 끊는다 → 바로 다시. 오류 뒤에는 0.5·1·2·4초로 늦춘다(무한 재시작 방지).
    const delay = failures ? 500 * 2 ** (failures - 1) : 0;
    retry = window.setTimeout(() => { try { rec.start(); } catch { /* 이미 시작됨 */ } }, delay);
  };
  rec.start();
  return () => {
    stopped = true;
    window.clearTimeout(retry);
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
    case "error": return `음성 인식 오류: ${ERROR_TEXT[s.code] ?? s.code}`;
  }
}

const ERROR_TEXT: Record<string, string> = {
  "audio-capture": "마이크를 찾을 수 없음 (연결·Windows 입력 장치 확인)",
  "network": "Chrome 음성 서버 연결 실패 (인터넷 확인)",
  "language-not-supported": "이 언어 미지원 (?lang= 확인)",
};
