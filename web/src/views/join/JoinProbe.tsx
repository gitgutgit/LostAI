// 개발 서버 전용 측정 화면 (?joinprobe): 입장 손동작 7종을 차례로 보여 주며 프레임마다 동작 이름과 신뢰도를 기록한다.
// 목적: 막대가 다 찬 뒤 인증이 늦게 넘어가는 손동작을 실제 카메라로 재고, 판정 규칙을 같은 기록으로 비교한다.
// 서버는 부르지 않는다. 운영 빌드에서는 App.tsx가 이 화면을 열지 않는다.
import { useEffect, useRef, useState } from "react";
import { engine, type EngineFrame } from "../../capture/gestures/engine";
import { MIN_CONFIDENCE } from "../../capture/gestures/modes";

const GESTURES = ["Thumb_Up", "Thumb_Down", "Pointing_Up", "Victory", "Open_Palm", "Closed_Fist", "ILoveYou"];
const LABEL: Record<string, string> = {
  Thumb_Up: "👍 엄지 위로", Thumb_Down: "👎 엄지 아래로", Pointing_Up: "☝️ 검지 위로", Victory: "✌️ 브이",
  Open_Palm: "🖐️ 손바닥 펴기", Closed_Fist: "✊ 주먹", ILoveYou: "🤟 사랑해",
};
const REPS = 5;
const TRIAL_MS = 6000;   // 손동작 하나를 보여 주는 시간
const REST_MS = 1500;    // 사이에 손을 내리는 시간
const STEP_HOLD_MS = 600; // JoinView 와 같은 값

interface Rec { t: number; g: string | null; c: number; h: number }
interface Trial { expected: string; frames: Rec[] }

function plan(): string[] {
  const out: string[] = [];
  for (let r = 0; r < REPS; r++) out.push(...[...GESTURES].sort(() => Math.random() - 0.5));
  return out;
}

/** 지금 JoinView 규칙으로 본 한 시도: 막대가 다 찬 시각과 실제로 보냈을 시각(시도 시작 기준 ms). */
function current(tr: Trial) {
  const full = tr.frames.find((f) => f.g === tr.expected && f.h >= STEP_HOLD_MS);
  const send = tr.frames.find((f) => f.g === tr.expected && f.h >= STEP_HOLD_MS && f.c >= MIN_CONFIDENCE);
  return { full: full?.t ?? null, send: send?.t ?? null };
}

const median = (xs: number[]) => { if (!xs.length) return NaN; const s = [...xs].sort((a, b) => a - b); return s[Math.floor(s.length / 2)]; };

export function JoinProbe() {
  const video = useRef<HTMLVideoElement>(null);
  const [order] = useState(plan);
  const [idx, setIdx] = useState(-1);
  const [resting, setResting] = useState(false);
  const [trials, setTrials] = useState<Trial[]>([]);
  const [live, setLive] = useState<EngineFrame | null>(null);
  const cur = useRef<Trial | null>(null);
  const t0 = useRef(0);

  async function start() {
    const stream = await navigator.mediaDevices.getUserMedia({ video: true });
    video.current!.srcObject = stream;
    await video.current!.play();
    await engine.start(video.current!);
    setIdx(0);
  }

  useEffect(() => engine.subscribe((f) => {
    setLive(f);
    if (cur.current) cur.current.frames.push({ t: Math.round(performance.now() - t0.current), g: f.gesture, c: +f.confidence.toFixed(3), h: f.hold_ms });
  }), []);

  useEffect(() => {
    if (idx < 0 || idx >= order.length) return;
    setResting(true);
    const a = window.setTimeout(() => {
      setResting(false);
      cur.current = { expected: order[idx], frames: [] };
      t0.current = performance.now();
    }, REST_MS);
    const b = window.setTimeout(() => {
      const done = cur.current; cur.current = null;
      if (done) setTrials((ts) => [...ts, done]);
      setIdx((i) => i + 1);
    }, REST_MS + TRIAL_MS);
    return () => { clearTimeout(a); clearTimeout(b); };
  }, [idx, order]);

  useEffect(() => () => engine.stop(), []);

  function download() {
    const blob = new Blob([JSON.stringify({ fps: 15, step_hold_ms: STEP_HOLD_MS, min_conf: MIN_CONFIDENCE, ua: navigator.userAgent, trials })], { type: "application/json" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `joinprobe-${new Date().toISOString().slice(0, 19).replace(/[:T]/g, "")}.json`;
    a.click();
  }

  const rows = GESTURES.map((g) => {
    const ts = trials.filter((t) => t.expected === g);
    const rs = ts.map(current);
    const stalls = rs.filter((r) => r.full != null && r.send != null).map((r) => r.send! - r.full!);
    const never = rs.filter((r) => r.full != null && r.send == null).length;
    const confs = ts.flatMap((t) => t.frames.filter((f) => f.g === g).map((f) => f.c));
    return { g, n: ts.length, stall: median(stalls), never, conf: median(confs), low: confs.filter((c) => c < MIN_CONFIDENCE).length / (confs.length || 1) };
  });

  const finished = idx >= order.length;
  const expected = idx >= 0 && !finished ? order[idx] : null;
  return (
    <div style={{ display: "grid", gridTemplateColumns: "1fr 520px", gap: 24, padding: 24, font: "16px/1.4 system-ui" }}>
      <video ref={video} muted playsInline style={{ width: "100%", transform: "scaleX(-1)", background: "#ddd" }} />
      <div>
        <h2 style={{ margin: 0 }}>입장 손동작 측정 (개발 전용)</h2>
        {idx < 0 && <button onClick={start} style={{ fontSize: 20, marginTop: 12 }}>카메라 켜고 시작</button>}
        {expected && <div style={{ fontSize: 48, margin: "16px 0" }}>{resting ? "손 내리기" : LABEL[expected]}</div>}
        {expected && <div>{idx + 1} / {order.length}</div>}
        {finished && <div style={{ fontSize: 28, margin: "16px 0" }}>끝. 기록을 내려받아 주세요.</div>}
        {live && <div style={{ fontFamily: "monospace", margin: "8px 0" }}>지금: {live.gesture ?? "-"} {live.confidence.toFixed(2)} {live.hold_ms}ms</div>}
        <table style={{ borderCollapse: "collapse", marginTop: 12, fontVariantNumeric: "tabular-nums" }}>
          <thead><tr><th align="left">손동작</th><th>회</th><th>막대 뒤 멈춤 p50</th><th>끝내 안 넘어감</th><th>신뢰도 p50</th><th>0.6 미만 비율</th></tr></thead>
          <tbody>{rows.map((r) => (
            <tr key={r.g}><td>{LABEL[r.g]}</td><td align="right">{r.n}</td>
              <td align="right">{Number.isNaN(r.stall) ? "-" : `${r.stall}ms`}</td><td align="right">{r.never}</td>
              <td align="right">{Number.isNaN(r.conf) ? "-" : r.conf.toFixed(2)}</td><td align="right">{`${Math.round(r.low * 100)}%`}</td></tr>
          ))}</tbody>
        </table>
        <button onClick={download} disabled={!trials.length} style={{ fontSize: 18, marginTop: 16 }}>기록 내려받기 (JSON)</button>
      </div>
    </div>
  );
}
