// B 화면: 캔버스 하나 (보드·노트 탭) + 타임라인 (ARCHITECTURE 7절).
import { useEffect, useMemo, useRef, useState } from "react";
import { AgentStatus } from "../../components/AgentStatus";
import { ChangeCard } from "../../components/ChangeCard";
import { DocView } from "../../components/DocView";
import { SheetView } from "../../components/SheetView";
import { cellIndex, docTabCounts, timeline } from "../../core/viewmodels";
import { useRoom } from "../../core/store";
import { send } from "../../core/ws";
import { engine } from "../../capture/gestures/engine";
import { isShared, ZOOM_AUTO_OFF_MS, ZOOM_TOGGLE, HOLD_MS } from "../../capture/gestures/modes";
import { Viewport } from "../../capture/gestures/viewport";
import { startStt } from "../../capture/stt";

export function CanvasView() {
  const v = useRoom();
  const [tab, setTab] = useState("board");
  const [seen, setSeen] = useState<Record<string, number>>({});
  const [mic, setMic] = useState<null | (() => void)>(null);
  const [zoom, setZoom] = useState(false);
  const canvasRef = useRef<HTMLDivElement>(null);
  const viewport = useMemo(() => new Viewport(() => canvasRef.current), []);
  const cells = cellIndex(v);
  const counts = docTabCounts(v, seen);

  // 손 신호: 기본 모드는 공유 신호만 서버로, 확대 모드는 내 화면만.
  useEffect(() => {
    let lastSent = "";
    let lastSeen = performance.now();
    return engine.subscribe((f) => {
      const now = performance.now();
      if (f.pointer) lastSeen = now;
      if (engine.mode === "zoom" && now - lastSeen > ZOOM_AUTO_OFF_MS) { engine.mode = "default"; setZoom(false); }
      if (!f.gesture || f.hold_ms < HOLD_MS) { lastSent = ""; return; }
      if (f.gesture === ZOOM_TOGGLE && lastSent !== ZOOM_TOGGLE) {
        lastSent = ZOOM_TOGGLE;
        engine.mode = engine.mode === "zoom" ? "default" : "zoom";
        setZoom(engine.mode === "zoom");
        return;
      }
      if (engine.mode === "zoom") {
        if (f.gesture === "Closed_Fist") viewport.resetScale();
        else if (f.openness != null) viewport.setOpenness(f.openness);
        if (f.pointer) viewport.setPointer(f.pointer, now);
      } else if (isShared(engine.mode, f.gesture) && lastSent !== f.gesture) {
        lastSent = f.gesture; // 서버도 2초 쿨다운을 건다
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
        <button onClick={() => { if (mic) { mic(); setMic(null); } else setMic(() => startStt()); }}>{mic ? "🎙 끄기" : "🎙 켜기"}</button>
        <button onClick={() => { engine.mode = zoom ? "default" : "zoom"; setZoom(!zoom); if (zoom) viewport.resetScale(); }}>
          {zoom ? "확대 모드 끄기" : "확대 모드"}
        </button>
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
      </aside>
      {v.notice && <div className="toast">{v.notice}</div>}
    </div>
  );
}
