// 음성 인식: Chrome Web Speech 기본 (Deepgram은 P2). localhost 또는 https에서만 마이크가 열린다.
import { send } from "../core/ws";

type Rec = any; // webkitSpeechRecognition 타입이 표준 lib에 없다

export function startStt(lang = "en-US"): () => void {
  const Ctor = (window as any).SpeechRecognition ?? (window as any).webkitSpeechRecognition;
  if (!Ctor) {
    console.warn("Web Speech API not available");
    return () => {};
  }
  const rec: Rec = new Ctor();
  rec.lang = lang;
  rec.continuous = true;
  rec.interimResults = true;
  let stopped = false;
  rec.onresult = (e: any) => {
    for (let i = e.resultIndex; i < e.results.length; i++) {
      const r = e.results[i];
      const text = r[0].transcript.trim();
      if (!text) continue;
      send({ kind: r.isFinal ? "utterance.final" : "utterance.interim", payload: { text } });
    }
  };
  rec.onend = () => { if (!stopped) rec.start(); }; // Chrome은 조용하면 끊는다
  rec.start();
  return () => { stopped = true; rec.stop(); };
}
