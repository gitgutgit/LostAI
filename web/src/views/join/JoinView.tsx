// 입장 화면 (A/B/C 공통): 랜덤 손동작 3개를 통과해야 들어온다 (ARCHITECTURE 5-2-1).
// TODO(P0): 통과 직후 "주먹 → 손바닥" 2초 보정값 저장. 카메라·마이크 권한 한 번에 요청.
import { useEffect, useRef, useState } from "react";
import { engine } from "../../capture/gestures/engine";
import { MIN_CONFIDENCE } from "../../capture/gestures/modes";
import { FitStage } from "../wall/FitStage";
import "./join.css";

const STEP_HOLD_MS = 600;

// hs: 제스처별 이모지·한국어 라벨 매핑 (hand-liveness-beta 참고)
const GESTURE_INFO: Record<string, { emoji: string; ko: string }> = {
  Closed_Fist:  { emoji: "✊", ko: "주먹" },
  Open_Palm:    { emoji: "🖐️", ko: "손바닥 펴기" },
  Pointing_Up:  { emoji: "☝️", ko: "검지 위로" },
  Thumb_Up:     { emoji: "👍", ko: "엄지 위로" },
  Thumb_Down:   { emoji: "👎", ko: "엄지 아래로" },
  Victory:      { emoji: "✌️", ko: "브이" },
  ILoveYou:     { emoji: "🤟", ko: "사랑해" },
};

const STEP_TIMEOUT_MS = 10000; // hs: 단계별 10초 제한시간

export function JoinView({ onJoined }: { onJoined: (name: string, token: string) => void }) {
  const video = useRef<HTMLVideoElement>(null);
  const [name, setName] = useState("");
  const [ch, setCh] = useState<{ challenge_id: string; gestures: string[] } | null>(null);
  const [step, setStep] = useState(0);
  const [hold, setHold] = useState(0);
  const [msg, setMsg] = useState("");
  const [manual, setManual] = useState(false);
  const [timeLeft, setTimeLeft] = useState(STEP_TIMEOUT_MS); // hs: 남은 시간
  const busy = useRef(false);
  const timerRef = useRef<number>(0); // hs: 타이머 ref
  const streamRef = useRef<MediaStream | null>(null); // hs: 카메라 스트림 ref (cleanup용)

  // hs: 타이머 시작/리셋 함수
  function startTimer() {
    clearInterval(timerRef.current);
    setTimeLeft(STEP_TIMEOUT_MS);
    const start = performance.now();
    timerRef.current = window.setInterval(() => {
      const elapsed = performance.now() - start;
      const remaining = Math.max(0, STEP_TIMEOUT_MS - elapsed);
      setTimeLeft(remaining);
      if (remaining <= 0) {
        clearInterval(timerRef.current);
        setMsg("⏱️ 시간 초과! 다시 시도해 주세요.");
        setCh(null); // hs: 챌린지 리셋
        engine.stop();
      }
    }, 50);
  }

  async function begin() {
    setMsg(""); // hs: 메시지 초기화
    const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true });
    streamRef.current = stream; // hs: 스트림 저장 (unmount 시 정리)
    video.current!.srcObject = stream;
    await video.current!.play();
    const r = await (await fetch("/api/join", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name }) })).json();
    setCh(r);
    setStep(0);
    engine.mode = "join";
    await engine.start(video.current!);
    startTimer(); // hs: 첫 단계 타이머 시작
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
      if (r.status === "next") { setStep(r.step); startTimer(); } // hs: 다음 단계 타이머 리셋
      else if (r.status === "pass") { clearInterval(timerRef.current); engine.mode = "default"; onJoined(name, r.token); } // hs: 통과 시 타이머 정리
      else if (r.status === "manual") setManual(true);
      else if (r.status === "expired") setMsg("시간이 지났어요. 다시 시도해 주세요.");
    });
  }, [ch, step, name, onJoined]);

  // hs: 컴포넌트 언마운트 시 타이머 + 엔진 + 카메라 스트림 정리
  useEffect(() => () => {
    clearInterval(timerRef.current);
    engine.stop();
    streamRef.current?.getTracks().forEach(t => t.stop());
    streamRef.current = null;
  }, []);

  async function manualJoin() {
    const r = await (await fetch("/api/join/manual", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name, host: "host" }) })).json();
    engine.mode = "default";
    onJoined(name, r.token);
  }

  // hs: 현재 제스처 정보 조회
  const currentGesture = ch ? ch.gestures[step] : null;
  const info = currentGesture ? GESTURE_INFO[currentGesture] : null;

  // ep: 화면은 렌더 v0.4 무대(1920x1080, 결정 벽과 같은 토큰과 부품). 왼쪽 큰 카드 = 카메라, 오른쪽 열 = 이름 또는 손동작 카드.
  const total = ch ? ch.gestures.length : 3;
  return (
    <FitStage>
      <div id="stage" className="joinwall">
        <div className="head" style={{ left: 24 }}>Join</div>
        <div id="slots">
          {Array.from({ length: total }, (_, i) => (
            <div key={i} className={`slot${ch && i < step ? " done" : ch && i === step ? " now" : ""}`}>{ch ? (GESTURE_INFO[ch.gestures[i]]?.emoji ?? i + 1) : i + 1}</div>
          ))}
        </div>
        <div className="head" style={{ left: 1270 }}>{ch ? "Show your hand" : "Who are you?"}{ch && <span className="n">{`${Math.min(step + 1, total)} of ${total}`}</span>}</div>
        <div id="mark">Hand check</div>

        <div className="jcam">
          <video ref={video} muted playsInline />
          {!ch && <div className="jcam-off">Camera turns on when you start.</div>}
        </div>

        {!ch ? (
          <div className="jcard">
            <label htmlFor="jname">Name</label>
            <input id="jname" placeholder="이름" value={name} autoFocus
              onChange={(e) => setName(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter" && name) begin(); }} />
            <button className="jgo" disabled={!name} onClick={begin}>카메라 켜고 시작</button>
            {/* hs: 시간 초과 등 메시지 표시 */}
            {msg && <p className="jmsg">{msg}</p>}
          </div>
        ) : (
          <div className="jcard">
            {/* hs: 큰 이모지 + 라벨 표시 (hand-liveness-beta 스타일) */}
            <div className="jprompt">
              <div className="jemoji">{info?.emoji ?? "❓"}</div>
              <div className="jlabel">{info?.ko ?? currentGesture}</div>
            </div>
            {/* hs: 인식 진행 바 */}
            <div className="jbar hold"><div style={{ width: `${Math.min(100, (hold / STEP_HOLD_MS) * 100)}%` }} /></div>
            {/* hs: 단계 타이머 바 */}
            <div className="jbar time"><div style={{ width: `${(timeLeft / STEP_TIMEOUT_MS) * 100}%` }} /></div>
            <div className="jrow">
              <span className="jtime">{`${(timeLeft / 1000).toFixed(1)}초`}</span>
              <button className="jghost" onClick={begin}>다시 시도</button>
              {manual && <button className="jghost" onClick={manualJoin}>호스트가 들여보내기</button>}
            </div>
            {msg && <p className="jmsg">{msg}</p>}
          </div>
        )}
        <div className="jfoot">Hold each hand sign until the green bar fills. Three signs, ten seconds each.</div>
      </div>
    </FitStage>
  );
}
