// B 화면: 캔버스 하나 (보드·노트 탭) + 타임라인 (ARCHITECTURE 7절).
import { useEffect, useMemo, useRef, useState } from "react";
import { AgentStatus } from "../../components/AgentStatus";
import { ChangeCard } from "../../components/ChangeCard";
import { DocLinks } from "../../components/DocLinks";
import { DocView } from "../../components/DocView";
import { SheetView } from "../../components/SheetView";
import { cellIndex, docTabCounts, timeline } from "../../core/viewmodels";
import { useRoom } from "../../core/store";
import { send } from "../../core/ws";
import { engine } from "../../capture/gestures/engine";
import { isShared, HOLD_MS } from "../../capture/gestures/modes"; // hs: ZOOM_AUTO_OFF_MS, ZOOM_TOGGLE 제거 (PoC 방식은 모드 토글 안 씀)
import { Viewport } from "../../capture/gestures/viewport";
import { startStt, sttStatusText, type SttStatus } from "../../capture/stt";

/** 마이크 없이 발화를 넣는 입력창. 팀 테스트용이자 시연 때 STT 백업. */
function UtteranceInput() {
  const [text, setText] = useState("");
  const [warn, setWarn] = useState("");
  const submit = () => {
    const t = text.trim();
    if (!t) return;
    if (send({ kind: "utterance.final", payload: { text: t } })) { setText(""); setWarn(""); }
    else setWarn("서버 연결이 끊겨 있어요. 다시 연결되면 보내 주세요.");
  };
  return (
    <form className="utt-input" onSubmit={(e) => { e.preventDefault(); submit(); }}>
      <input value={text} onChange={(e) => setText(e.target.value)}
             placeholder="말 대신 입력 (Enter로 전송) — 예: PAY-423 추정 3으로 바꾸자" aria-label="발화 입력" />
      <button type="submit" disabled={!text.trim()}>보내기</button>
      {warn && <div className="warn">{warn}</div>}
    </form>
  );
}

export function CanvasView() {
  const v = useRoom();
  const [tab, setTab] = useState("board");
  const [seen, setSeen] = useState<Record<string, number>>({});
  const [mic, setMic] = useState<null | (() => void)>(null);
  const [stt, setStt] = useState<SttStatus>({ kind: "off" });
  const [interim, setInterim] = useState("");
  // hs: zoom 상태 제거 — PoC 방식은 항상 제스처 활성, 모드 토글 없음
  const canvasRef = useRef<HTMLDivElement>(null);
  const viewport = useMemo(() => new Viewport(() => canvasRef.current), []);
  const cells = cellIndex(v);
  const counts = docTabCounts(v, seen);

  // hs: PoC pa_hs_gesture_api.js start() 방식 — video는 숨김(화면에 안 보임)
  useEffect(() => {
    let stream: MediaStream | null = null;
    let vid: HTMLVideoElement | null = null;
    let cancelled = false; // hs: StrictMode 이중 실행 방어
    (async () => {
      vid = document.createElement("video");
      vid.autoplay = true;
      vid.playsInline = true;
      vid.muted = true;
      vid.style.cssText = "position:fixed;width:1px;height:1px;opacity:0;pointer-events:none;"; // hs: 숨김
      document.body.appendChild(vid);

      stream = await navigator.mediaDevices.getUserMedia(
        { video: { width: 640, height: 480, facingMode: "user" } }
      );
      if (cancelled) { stream.getTracks().forEach(t => t.stop()); return; }
      vid.srcObject = stream;
      await new Promise<void>(r => vid!.addEventListener("loadeddata", () => r(), { once: true }));
      if (cancelled) { stream.getTracks().forEach(t => t.stop()); return; }

      engine.mode = "default";
      await engine.start(vid);
    })();
    return () => {
      cancelled = true;
      engine.stop();
      stream?.getTracks().forEach(t => t.stop());
      if (vid?.parentNode) vid.parentNode.removeChild(vid);
    };
  }, []);

  // hs: PoC pa_hs_gesture_api 모드 로직 그대로:
  // hs: Pointing_Up → 커서 이동 (줌 크기 유지)
  // hs: Closed_Fist → 커서 고정, 최소(1x)
  // hs: Open_Palm → 커서 고정, 최대(2x)
  // hs: 그 외(손가락 벌림) → 커서 고정(마지막 위치), 연속 줌
  useEffect(() => {
    let lastSent = "";
    let lastSeen = performance.now();
    return engine.subscribe((f) => {
      const now = performance.now();
      if (f.pointer) lastSeen = now;

      if (!f.pointer) {
        viewport.showCursor(false); // hs: 손 안 보이면 커서 숨김
      } else if (f.gesture === "Pointing_Up" && f.confidence > 0.5) {
        // hs: 검지 = 커서 이동, 줌 크기 유지
        viewport.moveCursor(f.pointer);
        viewport.showCursor(true);
        viewport.setPointer(f.pointer, now); // hs: 줌 기준점 저장
      } else if (f.gesture === "Closed_Fist" && f.confidence > 0.6) {
        // hs: 주먹 = 커서 고정, 최소(1x)
        viewport.showCursor(true);
        viewport.snapMin();
      } else if (f.gesture === "Open_Palm" && f.confidence > 0.6) {
        // hs: 손바닥 = 커서 고정, 최대(2x)
        viewport.showCursor(true);
        viewport.snapMax();
      } else if (f.openness != null) {
        // hs: 손가락 벌림/오므림 = 커서 고정(마지막 위치), 연속 줌
        viewport.showCursor(true);
        viewport.setOpenness(f.openness);
      }

      // 기존 공유 신호 (엄지 등 → 서버)
      if (!f.gesture || f.hold_ms < HOLD_MS) { lastSent = ""; return; }
      if (isShared(engine.mode, f.gesture) && lastSent !== f.gesture) {
        lastSent = f.gesture;
        send({ kind: "gesture", payload: { kind: f.gesture, confidence: f.confidence, hold_ms: f.hold_ms } });
      }
    });
  }, [viewport]);

  if (!v.state) return <div className="loading">연결 중…</div>;
  const doc = v.state.docs[tab];

  return (
    <div className="canvas-layout">
      <header>
        <AgentStatus v={v} />
        <button onClick={() => {
          if (mic) { mic(); setMic(null); setInterim(""); }
          else setMic(() => startStt({ onStatus: setStt, onInterim: setInterim }));
        }}>{mic ? "🎙 끄기" : "🎙 켜기"}</button>
        <span className={`stt ${stt.kind}`}>{sttStatusText(stt)}</span>
        <DocLinks />
        {/* hs: 줌 모드 토글 버튼 제거 — PoC 방식은 제스처로 항상 동작 */}
      </header>
      <main>
        <nav className="tabs">
          {Object.entries(v.state.docs).map(([k, d]) => (
            <button key={k} className={k === tab ? "on" : ""}
                    onClick={() => { setTab(k); setSeen((s) => ({ ...s, [k]: v.events.at(-1)?.seq ?? 0 })); }}>
              {d.title}{k !== tab && counts[k] ? <span className="badge">{counts[k]}</span> : null}
            </button>
          ))}
        </nav>
        <div className="canvas-viewport">
          <div ref={canvasRef} className="canvas">
            {doc.kind === "sheet" ? <SheetView docKey={tab} sheet={doc} cellIndex={cells} /> : <DocView docKey={tab} doc={doc} cellIndex={cells} />}
          </div>
        </div>
      </main>
      <aside className="timeline">
        {timeline(v).map((e) => (
          <div key={e.utt.seq} className="entry">
            <div className="utt"><b>{e.utt.payload.speaker}</b> {e.utt.payload.text} {e.label && <span className="label">{e.label}</span>}</div>
            {e.answer && <div className="answer">💬 {e.answer}</div>}
            {e.changes.map((c) => <ChangeCard key={c.change_id} ch={c} />)}
          </div>
        ))}
        <div className="timeline-foot">
          {interim && <div className="interim">🎙 {interim}…</div>}
          <UtteranceInput />
        </div>
      </aside>
      {v.notice && <div className="toast">{v.notice}</div>}
    </div>
  );
}
