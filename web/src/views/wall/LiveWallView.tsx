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
import { engine } from "../../capture/gestures/engine";
import { HOLD_MS, isShared } from "../../capture/gestures/modes";
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
  // ep: 서버 모드(MOCK, LIVE)를 벽 표지에 보인다. LIVE면 한 줄마다 모델 비용이 든다.
  const [mode, setMode] = useState<string>();
  useEffect(() => { fetch("/api/stats").then((r) => r.json()).then((h) => setMode(h.mode)).catch(() => {}); }, [v.connected]);
  const toggleMic = () => {
    if (stopMic.current) { stopMic.current(); stopMic.current = null; setMic(false); }
    else { stopMic.current = startStt(); setMic(true); }
  };
  useEffect(() => () => stopMic.current?.(), []);

  // ep: 입장 화면은 닫힐 때 엔진과 카메라를 끈다(#10). 회의 화면도 캔버스 화면처럼 숨긴 카메라로 엔진을 다시 켠다.
  // 카메라가 없거나 거부되면 넘어간다(채팅과 '/1' 같은 명령으로 시험 가능).
  useEffect(() => {
    let stream: MediaStream | null = null;
    let cancelled = false;
    const vid = document.createElement("video");
    vid.autoplay = true; vid.playsInline = true; vid.muted = true;
    vid.style.cssText = "position:fixed;width:1px;height:1px;opacity:0;pointer-events:none;";
    document.body.appendChild(vid);
    (async () => {
      try {
        stream = await navigator.mediaDevices.getUserMedia({ video: { width: 640, height: 480, facingMode: "user" } });
        if (cancelled) return;
        vid.srcObject = stream;
        await new Promise<void>((r) => vid.addEventListener("loadeddata", () => r(), { once: true }));
        if (cancelled) return;
        engine.mode = "default";
        await engine.start(vid);
      } catch { /* 카메라 없음: 손 신호 없이 진행 */ }
    })();
    return () => {
      cancelled = true;
      engine.stop();
      stream?.getTracks().forEach((t) => t.stop());
      vid.remove();
    };
  }, []);

  // ep: 손 신호(공유 신호만: 엄지, 손가락 표결, T자)를 서버로. 캔버스 화면과 같은 규칙, 같은 신호를 연달아 보내지 않는다.
  useEffect(() => {
    let lastSent = "";
    return engine.subscribe((f) => {
      if (!f.gesture || f.hold_ms < HOLD_MS) { lastSent = ""; return; }
      if (isShared(engine.mode, f.gesture) && lastSent !== f.gesture) {
        lastSent = f.gesture;
        send({ kind: "gesture", payload: { kind: f.gesture, confidence: f.confidence, hold_ms: f.hold_ms } });
      }
    });
  }, []);

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
        live={{ mic, onMic: toggleMic, connected: v.connected, typing, onType: () => setTyping(true), onTypeEnd: () => setTyping(false),
          mode, hint: import.meta.env.DEV ? "Ines: line speaks as Ines.  /up /down /1 /2 /t for hands" : undefined,
          // 개발 서버: 'Ines: 줄'은 Ines로, '/2'는 손 신호로(1인 시험, puppets.ts). 운영 빌드는 내 발화만.
          onSay: (text) => { if (import.meta.env.DEV) sayAs(text, me ?? "").catch(() => {}); else send({ kind: "utterance.final", payload: { text } }); } }} />
    </FitStage>
  );
}
