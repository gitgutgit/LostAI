// 입장 뒤 실제 회의 화면: 서버 회의방(WebSocket 이벤트)을 live.ts로 WallState로 바꿔 결정 벽으로 그린다.
// 창 전체가 벽이다(1920x1080 무대를 창에 맞춰 키우고 남는 띠는 벽색). 벽 밖 조작 띠는 없다:
// 마이크는 오른쪽 위 표지(또는 M 키), 회의록 전문은 Log 상자를 누르면 열린다. F 키는 브라우저 전체 화면.
// 임시 채팅: Enter 또는 발화 줄을 누르면 그 자리가 입력칸이 되고, 친 줄은 마이크 발화와 같은 utterance.final로 간다.
// 손 신호(엄지, 손가락 표결, T자)는 서버로 보낸다(기본 모드).
// author: ProfessionalSeaweedDevourer
import { useEffect, useRef, useState } from "react";
import { useRoom } from "../../core/store";
import { send } from "../../core/ws";
import { startStt } from "../../capture/stt";
import { useGesture } from "../../capture/gestures/useGesture"; // hs: 제스처 커스텀 훅
import { changeHeadline } from "../../lib/changeText";
import { Wall } from "./Wall";
import { liveWall } from "./live";
import { FitStage } from "./FitStage";
import { sayAs } from "./puppets";

function Minutes({ onClose }: { onClose: () => void }) {
  const v = useRoom();
  useEffect(() => {
    const k = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", k);
    return () => window.removeEventListener("keydown", k);
  }, [onClose]);
  let n = 0;
  return (
    <div id="minutes" onClick={onClose}>
      <div className="icard" onClick={(e) => e.stopPropagation()}>
        <h2>Minutes</h2>
        {v.events.filter((e) => e.type === "utterance.final").map((e) => {
          n += 1;
          const chs = Object.values(v.changes).filter((c) => c.utt_id === e.refs.utt_id);
          return (
            <div className="mrow" key={e.seq}>
              <b>{`L${n}`}</b>
              <div>
                <b>{String(e.payload.speaker)}</b>{` ${String(e.payload.text)}`}
                {chs.map((c) => <div key={c.change_id} className={`mch ${c.status}`}>{`${c.status}: ${changeHeadline(c, v.state)}`}</div>)}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export function LiveWallView({ me }: { me?: string }) {
  const v = useRoom();
  const [mic, setMic] = useState(false);
  const stopMic = useRef<null | (() => void)>(null);
  const [minutes, setMinutes] = useState(false);
  const [typing, setTyping] = useState(false);
  const [gesture, setGesture] = useState(false); // hs: 제스처 토글 상태
  // ep: 서버 모드(MOCK, LIVE)를 벽 표지에 보인다. LIVE면 한 줄마다 모델 비용이 든다.
  const [mode, setMode] = useState<string>();
  useEffect(() => { fetch("/api/stats").then((r) => r.json()).then((h) => setMode(h.mode)).catch(() => {}); }, [v.connected]);
  const toggleMic = () => {
    if (stopMic.current) { stopMic.current(); stopMic.current = null; setMic(false); }
    else { stopMic.current = startStt(); setMic(true); }
  };
  useEffect(() => () => stopMic.current?.(), []);

  // hs: 제스처 커스텀 훅 — 버튼으로 활성화할 때만 동작
  useGesture(() => document.getElementById("livewrap"), gesture);

  // 키: M 마이크, F 전체 화면 (입력칸에 쓰는 중이면 무시)
  useEffect(() => {
    const k = (e: KeyboardEvent) => {
      if (e.metaKey || e.ctrlKey || e.altKey || (e.target as HTMLElement)?.closest?.("input,textarea")) return;
      if (e.key === "Enter") { e.preventDefault(); setTyping(true); }
      else if (e.key === "m" || e.key === "M") toggleMic();
      else if (e.key === "f" || e.key === "F") {
        if (document.fullscreenElement) document.exitFullscreen(); else document.documentElement.requestFullscreen?.();
      }
    };
    window.addEventListener("keydown", k);
    return () => window.removeEventListener("keydown", k);
  }, []);

  if (!v.state) return <FitStage><div id="stage"><div className="head" style={{ left: 24 }}>Connecting…</div></div></FitStage>;
  const w = liveWall(v, me);
  const band = !!w.cardA && !w.cardB.take;

  return (
    <FitStage overlay={<>
      {minutes && <Minutes onClose={() => setMinutes(false)} />}
      {v.notice && <div id="notice">{v.notice}</div>}
    </>}>
      <Wall w={w} band={band} animate onOpenMinutes={() => setMinutes(true)}
        live={{ mic, onMic: toggleMic, gesture, onGesture: () => setGesture(!gesture), connected: v.connected, typing, onType: () => setTyping(true), onTypeEnd: () => setTyping(false), // hs: gesture 토글 전달
          mode, hint: import.meta.env.DEV ? "Ines: line speaks as Ines.  /up /down /1 /2 /t for hands" : undefined,
          // 개발 서버: 'Ines: 줄'은 Ines로, '/2'는 손 신호로(1인 시험, puppets.ts). 운영 빌드는 내 발화만.
          onSay: (text) => { if (import.meta.env.DEV) sayAs(text, me ?? "").catch(() => {}); else send({ kind: "utterance.final", payload: { text } }); } }} />
    </FitStage>
  );
}
