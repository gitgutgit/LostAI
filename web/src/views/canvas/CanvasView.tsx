// B 화면: 캔버스 하나 (보드·노트 탭) + 타임라인 (ARCHITECTURE 7절).
import { useRef, useState } from "react"; // hs: useEffect, useMemo 제거 (useGesture로 이동)
import { AgentStatus } from "../../components/AgentStatus";
import { ChangeCard } from "../../components/ChangeCard";
import { DocLinks } from "../../components/DocLinks";
import { DocView } from "../../components/DocView";
import { SheetView } from "../../components/SheetView";
import { cellIndex, docTabCounts, timeline } from "../../core/viewmodels";
import { useRoom } from "../../core/store";
import { useGesture } from "../../capture/gestures/useGesture"; // hs: 제스처 커스텀 훅
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
  const canvasRef = useRef<HTMLDivElement>(null);
  useGesture(() => canvasRef.current); // hs: 제스처 커스텀 훅 (카메라+포인터+줌 전부)
  const cells = cellIndex(v);
  const counts = docTabCounts(v, seen);

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
