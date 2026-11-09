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
import { isShared, ZOOM_AUTO_OFF_MS, ZOOM_TOGGLE, HOLD_MS } from "../../capture/gestures/modes";
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
  const [zoom, setZoom] = useState(false);
  const canvasRef = useRef<HTMLDivElement>(null);
  const webcamRef = useRef<HTMLDivElement>(null); // hs: 웹캠 컨테이너
  const viewport = useMemo(() => new Viewport(() => canvasRef.current), []);
  const cells = cellIndex(v);
  const counts = docTabCounts(v, seen);

  // hs: PoC pa_hs_gesture_api.js start() 방식 그대로
  // hs: video를 createElement로 직접 생성 → getUserMedia → loadeddata 대기 → engine.start
  useEffect(() => {
    let stream: MediaStream | null = null;
    let vid: HTMLVideoElement | null = null;
    (async () => {
      // hs: PoC와 동일하게 video 요소 직접 생성
      vid = document.createElement("video");
      vid.autoplay = true;
      vid.playsInline = true;
      vid.muted = true;
      vid.style.cssText = "width:160px;display:block;transform:scaleX(-1);";

      // hs: PoC와 동일하게 getUserMedia
      stream = await navigator.mediaDevices.getUserMedia(
        { video: { width: 640, height: 480, facingMode: "user" } }
      );
      vid.srcObject = stream;

      // hs: PoC와 동일하게 loadeddata 대기
      await new Promise<void>(r => vid!.addEventListener("loadeddata", () => r(), { once: true }));

      // hs: 웹캠 미리보기에 붙이기
      webcamRef.current?.appendChild(vid);

      // hs: 엔진 시작
      engine.mode = "default";
      await engine.start(vid);
    })();
    return () => {
      engine.stop();
      stream?.getTracks().forEach(t => t.stop());
      if (vid?.parentNode) vid.parentNode.removeChild(vid);
    };
  }, []);

  // 손 신호: 기본 모드는 공유 신호만 서버로, 확대 모드는 내 화면만.
  // hs: 검지 커서 + 줌은 항상 동작 (PoC pa_hs 방식 — 줌 모드 토글 불필요)
  useEffect(() => {
    let lastSent = "";
    let lastSeen = performance.now();
    viewport.showCursor(true); // hs: 캔버스 진입 시 커서 켜기
    return engine.subscribe((f) => {
      const now = performance.now();

      // hs: 검지 포인터 — 항상 추적
      if (f.pointer) {
        lastSeen = now;
        viewport.moveCursor(f.pointer); // hs: 커서 위치
        viewport.showCursor(true);
        viewport.setPointer(f.pointer, now); // hs: 줌 기준점 + 머물기 클릭
      } else {
        viewport.showCursor(false); // hs: 손 안 보이면 커서 숨김
      }

      // hs: 제스처별 줌 (PoC pa_hs_gesture_api 로직)
      if (f.gesture === "Closed_Fist" && f.confidence > 0.6) {
        viewport.snapMin(); // hs: 주먹 → 최소(1x)
      } else if (f.gesture === "Open_Palm" && f.confidence > 0.6) {
        viewport.snapMax(); // hs: 손바닥 → 최대(2x)
      } else if (f.openness != null) {
        viewport.setOpenness(f.openness); // hs: 손 벌림/오므림 → 연속 줌
      }

      // hs: 기존 줌 모드 자동 해제
      if (engine.mode === "zoom" && now - lastSeen > ZOOM_AUTO_OFF_MS) { engine.mode = "default"; setZoom(false); }

      // 기존 공유 신호 (엄지 등 → 서버)
      if (!f.gesture || f.hold_ms < HOLD_MS) { lastSent = ""; return; }
      if (f.gesture === ZOOM_TOGGLE && lastSent !== ZOOM_TOGGLE) {
        lastSent = ZOOM_TOGGLE;
        engine.mode = engine.mode === "zoom" ? "default" : "zoom";
        setZoom(engine.mode === "zoom");
        return;
      }
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
        <div className="timeline-foot">
          {interim && <div className="interim">🎙 {interim}…</div>}
          <UtteranceInput />
        </div>
      </aside>
      {v.notice && <div className="toast">{v.notice}</div>}
      {/* hs: 웹캠 미리보기 컨테이너 (PoC처럼 video를 createElement로 직접 append) */}
      <div ref={webcamRef} style={{ position: "fixed", bottom: 8, right: 8, zIndex: 50, borderRadius: 12, overflow: "hidden", border: "2px solid #333" }} />
    </div>
  );
}
