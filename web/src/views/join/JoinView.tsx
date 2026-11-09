// 입장 화면 (A/B/C 공통): 랜덤 손동작 3개를 통과해야 들어온다 (ARCHITECTURE 5-2-1).
// TODO(P0): 통과 직후 "주먹 → 손바닥" 2초 보정값 저장. 카메라·마이크 권한 한 번에 요청.
import { useEffect, useRef, useState } from "react";
import { engine } from "../../capture/gestures/engine";
import { MIN_CONFIDENCE } from "../../capture/gestures/modes";

const STEP_HOLD_MS = 600;

export function JoinView({ onJoined }: { onJoined: (name: string, token: string) => void }) {
  const video = useRef<HTMLVideoElement>(null);
  const [name, setName] = useState("");
  const [ch, setCh] = useState<{ challenge_id: string; gestures: string[] } | null>(null);
  const [step, setStep] = useState(0);
  const [hold, setHold] = useState(0);
  const [msg, setMsg] = useState("");
  const [manual, setManual] = useState(false);
  const busy = useRef(false);

  async function begin() {
    const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true });
    video.current!.srcObject = stream;
    await video.current!.play();
    const r = await (await fetch("/api/join", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name }) })).json();
    setCh(r);
    setStep(0);
    engine.mode = "join";
    await engine.start(video.current!);
  }

  useEffect(() => {
    if (!ch) return;
    return engine.subscribe(async (f) => {
      const expected = ch.gestures[step];
      setHold(f.gesture === expected ? f.hold_ms : 0);
      if (busy.current || f.gesture !== expected || f.hold_ms < STEP_HOLD_MS || f.confidence < MIN_CONFIDENCE) return;
      busy.current = true;
      const r = await (await fetch(`/api/join/${ch.challenge_id}/step`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ gesture: f.gesture, confidence: f.confidence, hold_ms: f.hold_ms }),
      })).json();
      busy.current = false;
      if (r.status === "next") setStep(r.step);
      else if (r.status === "pass") { engine.mode = "default"; onJoined(name, r.token); }
      else if (r.status === "manual") setManual(true);
      else if (r.status === "expired") setMsg("시간이 지났어요. 다시 시도해 주세요.");
    });
  }, [ch, step, name, onJoined]);

  async function manualJoin() {
    const r = await (await fetch("/api/join/manual", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name, host: "host" }) })).json();
    engine.mode = "default";
    onJoined(name, r.token);
  }

  return (
    <div className="join">
      <video ref={video} className="cam" muted playsInline />
      {!ch ? (
        <div className="form">
          <input placeholder="이름" value={name} onChange={(e) => setName(e.target.value)} />
          <button disabled={!name} onClick={begin}>카메라 켜고 시작</button>
        </div>
      ) : (
        <div className="challenge">
          <div className="steps">{ch.gestures.map((g, i) => <span key={g} className={i < step ? "done" : i === step ? "now" : ""}>{g}</span>)}</div>
          <div className="target">지금: <b>{ch.gestures[step]}</b></div>
          <progress max={STEP_HOLD_MS} value={Math.min(hold, STEP_HOLD_MS)} />
          <button onClick={begin}>다시 시도</button>
          {manual && <button onClick={manualJoin}>호스트가 들여보내기</button>}
          {msg && <p>{msg}</p>}
        </div>
      )}
    </div>
  );
}
