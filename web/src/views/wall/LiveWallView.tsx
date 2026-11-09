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
import { lastVoteSeq, liveWall } from "./live";
import { FitStage } from "./FitStage";
import { sayAs } from "./puppets";
import { DocLinks } from "../../components/DocLinks";
import { TestSeedPicker } from "../../components/TestSeedPicker";
import { DemoPlayer } from "../../components/DemoPlayer";
import { useSceneTransition } from "./sceneTransition";

/** 벽 + 장면 전환. 글자판 낱말, 전체화면 여부, 질문 카드와 띠 배치가 바뀌면 장면 재생기처럼 카드가 옮겨 가며 바뀐다. */
function SceneWall(props: Parameters<typeof Wall>[0]) {
  const { w, band } = props;
  const key = `${w.cardB.flap}|${w.cardB.take ?? ""}|${w.cardA ? 1 : 0}|${band ? 1 : 0}`;
  const shown = useSceneTransition({ w, band }, key);
  return <Wall {...props} w={shown.w} band={shown.band} />;
}

const BACK_AFTER_SEC = 5;

/** 평상시 화면으로 돌아가는 버튼 + 카운트다운. 0이 되거나 누르면 onBack. 부모가 key를 바꾸면 새로 센다. */
function BackCountdown({ onBack }: { onBack: () => void }) {
  const [left, setLeft] = useState(BACK_AFTER_SEC);
  const fired = useRef(false);
  useEffect(() => {
    const t = setInterval(() => setLeft((n) => n - 1), 1000);
    return () => clearInterval(t);
  }, []);
  useEffect(() => {
    if (left <= 0 && !fired.current) { fired.current = true; onBack(); }
  }, [left, onBack]);
  return (
    <button id="back-normal" onClick={() => { fired.current = true; onBack(); }} title="지금 평상시 화면으로">
      ✕ 평상시 화면으로 <b>{Math.max(0, left)}</b>
    </button>
  );
}

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
  // ep: 전체화면 표결 화면(카운트다운, CONVERGED, SPLIT)은 버튼이나 5초 카운트다운으로 평상시 화면으로 돌아간다.
  // 돌아가면 그 시점의 마지막 표결 이벤트까지 숨긴다 → 다음 vote.opened, vote.closed는 다시 전체화면으로 뜬다.
  // 리셋하면 서버 seq가 1부터 다시 시작한다 → 마지막 표결 seq가 숨김 기준보다 작아지면 새 회의이므로 기준을 버린다.
  const [hideRaw, setHideTakeUpTo] = useState(-1);
  const voteSeq = lastVoteSeq(v);
  const hideTakeUpTo = voteSeq < hideRaw ? -1 : hideRaw;
  useEffect(() => { if (voteSeq < hideRaw) setHideTakeUpTo(-1); }, [voteSeq, hideRaw]);
  // ep: 질문 카드 띠(한 칸에 값이 둘 → 질문이 열려 화면이 띠 배치로 바뀜)도 같은 방식으로 평상시 화면으로 돌아간다.
  // 접은 질문은 서버에 그대로 열려 있고 행의 'Q1 open' 표지로 남는다. 다른 질문이 열리면 다시 띠로 뜬다.
  const [hiddenQ, setHiddenQ] = useState("");
  const evCount = useRef(0); // 리셋(이벤트 목록이 줄어듦)이면 접어 둔 질문 기억을 버린다
  useEffect(() => { if (v.events.length < evCount.current) setHiddenQ(""); evCount.current = v.events.length; }, [v.events.length]);
  const toggleMic = () => {
    if (stopMic.current) { stopMic.current(); stopMic.current = null; setMic(false); }
    else { stopMic.current = startStt(); setMic(true); }
  };
  useEffect(() => () => stopMic.current?.(), []);

  // hs: 제스처 커스텀 훅 — 버튼으로 활성화, Thumb_Down 3초로 끄기
  useGesture(() => document.getElementById("livewrap"), gesture, () => setGesture(false));

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
  const w0 = liveWall(v, me, hideTakeUpTo);
  const qKey = w0.cardA ? `${w0.cardA.q} ${w0.cardA.title}` : "";
  const qHidden = !!qKey && qKey === hiddenQ && !w0.cardB.take;
  const w = qHidden ? { ...w0, cardA: null, idle: [`${w0.cardA!.q} is still open.`, "Say an option, or call a vote, to bring it back."] } : w0;
  const band = !!w.cardA && !w.cardB.take;
  // 평상시 화면으로 돌아가기: 표결 전체화면이 우선, 그다음 질문 띠. key가 바뀌면 카운트다운이 처음부터 다시 돈다.
  const back = w.cardB.take ? { key: `take ${voteSeq}`, go: () => setHideTakeUpTo(voteSeq) }
    : band ? { key: `q ${qKey}`, go: () => setHiddenQ(qKey) } : null;

  return (
    <FitStage overlay={<>
      {back && <BackCountdown key={back.key} onBack={back.go} />}
      {minutes && <Minutes onClose={() => setMinutes(false)} />}
      {v.notice && <div id="notice">{v.notice}</div>}
      {/* ep: Google Sheet, Doc 바로가기 + 테스트 대본 선택(임시). 무대(1920x1080) 배치는 건드리지 않게 창 왼쪽 아래 층에 둔다. 문서가 바뀌면(제목) 다시 받는다 */}
      <div id="wall-tools"><DocLinks refreshKey={Object.values(v.state.docs).map((d) => d.title).join("|")} /><TestSeedPicker /><DemoPlayer refreshKey={Object.values(v.state.docs).map((d) => d.title).join("|")} /></div>
    </>}>
      <SceneWall w={w} band={band} animate onOpenMinutes={() => setMinutes(true)}
        live={{ mic, onMic: toggleMic, gesture, onGesture: () => setGesture(!gesture), connected: v.connected, typing, onType: () => setTyping(true), onTypeEnd: () => setTyping(false), // hs: gesture 토글 전달
          mode, hint: import.meta.env.DEV ? "Ines: line speaks as Ines.  /up /down /1 /2 /t for hands" : undefined,
          // 개발 서버: 'Ines: 줄'은 Ines로, '/2'는 손 신호로(1인 시험, puppets.ts). 운영 빌드는 내 발화만.
          onSay: (text) => { if (import.meta.env.DEV) sayAs(text, me ?? "").catch(() => {}); else send({ kind: "utterance.final", payload: { text } }); } }} />
    </FitStage>
  );
}
