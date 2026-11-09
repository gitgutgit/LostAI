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
  normalize?: (text: string) => string; // 받아쓰기 보정 (예: "페이사이삼" → "PAY-423", capture/normalize.ts)
}

/** 기본 언어: URL ?lang=en-US 로 바꿀 수 있다. 시드 문서가 한국어라 ko-KR. */
export function defaultLang(): string {
  return new URLSearchParams(location.search).get("lang") ?? "ko-KR";
}

const INTERIM_MIN_GAP_MS = 250;
const MAX_FAILURES = 5;
// Chrome은 말이 끝나도 final을 0.7~5초 늦게 준다 (11-09 실측: 대부분 1초 안팎, 가끔 3.5·5초).
// interim이 이만큼 그대로면 말이 끝났다고 보고 우리가 먼저 final로 보낸다. 짧으면 문장 중간 쉼에서 잘린다.
// 1.2초: Chrome이 보통 1초 안팎에 주므로 평소엔 Chrome final, 늦을 때(3~5초)만 우리가 먼저. ?early=0 끔, ?early=800 조절.
const EARLY_FINAL_MS = Number(new URLSearchParams(location.search).get("early") ?? 1200);

/** 공백을 무시하고 full이 prefix로 시작하면 그 뒤 나머지, 아니면 null. */
function afterPrefix(full: string, prefix: string): string | null {
  let i = 0;
  for (const c of prefix.replace(/\s+/g, "")) {
    while (i < full.length && /\s/.test(full[i])) i++;
    if (full[i] !== c) return null;
    i++;
  }
  return full.slice(i).trim();
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
  let failures = 0;          // 연속 실패 횟수: 결과가 오면 0으로
  let retry: number | undefined;
  let lastInterim = "", lastInterimAt = 0;
  const fix = opts.normalize ?? ((t: string) => t);
  // 먼저 보낸 final: 결과 칸(resultIndex)별로 이미 보낸 원문. Chrome final이 오면 그 뒤 나머지만 보낸다.
  let committed = new Map<number, string>();
  let early: { timer: number; index: number; text: string } | null = null;

  const sendFinal = (text: string) => {
    const t = fix(text).trim();
    if (t) send({ kind: "utterance.final", payload: { text: t } });
  };
  const fireEarly = () => {
    if (!early) return;
    const { index, text } = early;
    window.clearTimeout(early.timer);
    early = null;
    const rest = committed.has(index) ? afterPrefix(text, committed.get(index)!) : text;
    if (!rest) return;
    committed.set(index, text);
    opts.onInterim?.("");
    lastInterim = "";
    sendFinal(rest);
  };

  rec.onstart = () => status({ kind: "listening" });
  rec.onresult = (e: any) => {
    failures = 0;
    for (let i = e.resultIndex; i < e.results.length; i++) {
      const r = e.results[i];
      const text = r[0].transcript.trim();
      if (!text) continue;
      const done = committed.get(i);
      if (r.isFinal) {
        const pend = early;
        if (pend && pend.index === i) { window.clearTimeout(pend.timer); early = null; }
        committed.delete(i);
        opts.onInterim?.("");
        lastInterim = "";
        // 먼저 보낸 게 있으면 그 뒤에 더 말한 부분만. Chrome이 앞부분을 고쳐 썼으면 먼저 보낸 쪽을 믿고 버린다.
        const rest = done === undefined ? text : afterPrefix(text, done);
        if (rest) sendFinal(rest);
        continue;
      }
      const pending = done === undefined ? text : afterPrefix(text, done);
      if (!pending) continue; // 먼저 보낸 부분을 Chrome이 고쳐 쓰는 중 → 무시
      const shown = fix(pending);
      opts.onInterim?.(shown); // 내 화면 미리보기는 매번
      // 서버(=이벤트 로그)에는 바뀌었을 때만, 최대 4번/초. 로그가 interim으로 넘치지 않게.
      const now = performance.now();
      if (shown !== lastInterim && now - lastInterimAt >= INTERIM_MIN_GAP_MS) {
        lastInterim = shown; lastInterimAt = now;
        send({ kind: "utterance.interim", payload: { text: shown } });
      }
      if (EARLY_FINAL_MS > 0) {
        if (early) window.clearTimeout(early.timer);
        early = { index: i, text, timer: window.setTimeout(fireEarly, EARLY_FINAL_MS) };
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
    fireEarly(); // final 없이 끊긴 말(11-09 실측에서 한 문장 잃어버림)은 지금까지 들은 걸로 보낸다
    committed = new Map(); // 새 세션은 결과 칸 번호가 0부터
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
    fireEarly(); // 🎙 끄기 직전까지 말한 것
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
