// 입장 뒤 실제 회의 화면: 서버 회의방(WebSocket 이벤트)을 live.ts로 WallState로 바꿔 결정 벽으로 그린다.
// 창 전체가 벽이다(1920x1080 무대를 창에 맞춰 키우고 남는 띠는 벽색). 벽 밖 조작 띠는 없다:
// 마이크는 오른쪽 위 표지(또는 M 키), 회의록 전문은 Log 상자를 누르면 열린다. F 키는 브라우저 전체 화면.
// 임시 채팅: Enter 또는 발화 줄을 누르면 그 자리가 입력칸이 되고, 친 줄은 마이크 발화와 같은 utterance.final로 간다.
// 손 신호(엄지, 손가락 표결, T자)는 서버로 보낸다(기본 모드).
// author: ProfessionalSeaweedDevourer
import { useEffect, useRef, useState } from "react";
import { useRoom } from "../../core/store";
import { getToken, send } from "../../core/ws";
import { startStt } from "../../capture/stt";
import { LangToggle } from "../../components/LangToggle";
import { useGesture } from "../../capture/gestures/useGesture"; // hs: 제스처 커스텀 훅
import { changeHeadline } from "../../lib/changeText";
import { Wall } from "./Wall";
import { Moai } from "../brand/Moai";
import { defaultDocTab, docTabs, lastCloseSeq, lastVoteSeq, liveWall } from "./live";
import { FitStage } from "./FitStage";
import { sayAs } from "./puppets";
import { DocLinks } from "../../components/DocLinks";
import { DocPicker } from "../../components/DocPicker"; // Mal-Mi-Jal: 기존 Sheet/Doc 불러오기·새로 만들기
import { NewMeetingDialog } from "../../components/NewMeetingDialog"; // Mal-Mi-Jal: 새 회의 확인창 (남기기/되돌리기)
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

const BACK_AFTER_SEC = 8; // hs: 투표 결과 화면 자동 닫기 시간 (5→8초, 결과 확인 여유)

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

export function LiveWallView({ me, onLeave }: { me?: string; onLeave?: () => void }) {
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
  // gitgutgit: 회의 끝(CLOSED) 화면은 자동으로 닫지 않는다. 버튼으로 접으면 그 '회의 끝' 발화까지 숨긴다.
  const [hideCloseUpTo, setHideCloseUpTo] = useState(-1);
  const closeSeq = lastCloseSeq(v);
  // Mal-Mi-Jal: 끝 화면의 '새 회의' = 서버 리셋(/api/meeting/new). 모두의 화면이 새 회의로, 원본 모드면 기본 문서(.env)로 돌아간다.
  // 확인창(NewMeetingDialog)에서 지금 문서에 회의 결과를 남길지 / 되돌릴지 고른다.
  const [newOpen, setNewOpen] = useState(false);
  const [newMsg, setNewMsg] = useState("");
  useEffect(() => { if (!newMsg) return; const t = setTimeout(() => setNewMsg(""), 6000); return () => clearTimeout(t); }, [newMsg]);
  const [hiddenQ, setHiddenQ] = useState("");
  const evCount = useRef(0); // 리셋(이벤트 목록이 줄어듦)이면 접어 둔 질문 기억을 버린다
  useEffect(() => { if (v.events.length < evCount.current) setHiddenQ(""); evCount.current = v.events.length; }, [v.events.length]);
  // Mal-Mi-Jal: 문서 칸 탭. 고른 탭이 사라지면(리셋, 문서 바꾸기) 기본 탭(첫 시트). seen = 탭별로 마지막으로 본 seq (새 편집 수 배지)
  const [pickedTab, setPickedTab] = useState<string>();
  const [tabSeen, setTabSeen] = useState<Record<string, number>>({});
  const docTab = pickedTab && v.state?.docs[pickedTab] ? pickedTab : defaultDocTab(v);
  const lastSeq = v.events.at(-1)?.seq ?? 0;
  const tabEvCount = useRef(0); // 리셋하면 seq가 1부터 다시 → 본 기록도 비운다
  useEffect(() => { if (v.events.length < tabEvCount.current) setTabSeen({}); tabEvCount.current = v.events.length; }, [v.events.length]);
  const onDocTab = (key: string) => {
    setTabSeen((s) => ({ ...s, ...(docTab ? { [docTab]: lastSeq } : {}), [key]: lastSeq })); // 떠나는 탭도 지금까지 본 것으로
    setPickedTab(key);
  };
  const toggleMic = () => {
    if (stopMic.current) { stopMic.current(); stopMic.current = null; setMic(false); }
    else { stopMic.current = startStt(); setMic(true); }
  };
  useEffect(() => () => stopMic.current?.(), []);
  // gitgutgit: 언어를 바꾸면 켜져 있는 마이크를 그 언어로 다시 켠다
  const onLang = () => { if (stopMic.current) { stopMic.current(); stopMic.current = startStt(); } };

  // hs: 제스처 커스텀 훅 — 버튼으로 활성화, Thumb_Down 3초로 끄기
  // gitgutgit: 표결이 열려 있으면 Gesture 버튼과 관계없이 카메라를 켜고 손가락 수만 표로 보낸다(확대·포인터 끔).
  const lastVoteEv = [...v.events].reverse().find((e) => e.type === "vote.opened" || e.type === "vote.closed");
  const voteOpen = lastVoteEv?.type === "vote.opened";
  const [camErr, setCamErr] = useState("");
  // gitgutgit: 표결 남은 초 — 마지막 표결 이벤트(vote.opened/cast)를 받은 순간부터 그 이벤트의 closes_in을 센다
  const lastVoteTick = [...v.events].reverse().find((e) => e.type === "vote.opened" || e.type === "vote.cast" || e.type === "vote.closed");
  const seen = useRef<{ seq: number; at: number }>({ seq: -1, at: 0 });
  if (lastVoteTick && lastVoteTick.seq !== seen.current.seq) seen.current = { seq: lastVoteTick.seq, at: Date.now() };
  const [, setTick] = useState(0);
  useEffect(() => { if (!voteOpen) return; const t = setInterval(() => setTick((n) => n + 1), 500); return () => clearInterval(t); }, [voteOpen]);
  const closesIn = voteOpen && lastVoteTick?.type !== "vote.closed" ? Number(lastVoteTick?.payload.closes_in) : NaN;
  const voteLeftSec = Number.isFinite(closesIn) ? Math.ceil(closesIn - (Date.now() - seen.current.at) / 1000) : null;
  useGesture(() => document.getElementById("livewrap"), gesture || voteOpen, () => setGesture(false),
    { voteOnly: voteOpen, onCamera: (s) => setCamErr(s.ok ? "" : s.reason) });

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
  const w1 = liveWall(v, me, hideTakeUpTo, closeSeq < hideCloseUpTo ? -1 : hideCloseUpTo, voteLeftSec, docTab);
  const w0 = { ...w1, doc: { ...w1.doc, tabs: docTabs(v, docTab, tabSeen) } };
  const isClosed = w0.cardB.take === "navy end";
  const qKey = w0.cardA ? `${w0.cardA.q} ${w0.cardA.title}` : "";
  const qHidden = !!qKey && qKey === hiddenQ && !w0.cardB.take;
  const w = qHidden ? { ...w0, cardA: null, idle: [`${w0.cardA!.q} is still open.`, "Say an option, or call a vote, to bring it back."] } : w0;
  const band = !!w.cardA && !w.cardB.take;
  // hs: 투표 카운트다운 중에는 자동 닫기 없이 수동 닫기 버튼만.
  // 투표 결과 화면(CONVERGED, SPLIT 등)은 자동 닫기(8초).
  const isVoteCountdown = w.cardB.take === "count";
  const back = isClosed ? null
    : w.cardB.take ? { key: `take ${voteSeq}`, go: () => setHideTakeUpTo(voteSeq) }
    : band ? { key: `q ${qKey}`, go: () => setHiddenQ(qKey) } : null;

  return (
    <FitStage overlay={<>
      {/* hs: 투표 카운트다운 중에는 수동 닫기 버튼만, 결과 화면은 자동 카운트다운 */}
      {back && !isVoteCountdown && <BackCountdown key={back.key} onBack={back.go} />}
      {back && isVoteCountdown && <button id="back-normal" onClick={back.go} title="투표 화면 접기">✕ 메인으로</button>}
      {isClosed && <button id="back-normal" onClick={() => setHideCloseUpTo(closeSeq)} title="끝 화면을 접고 회의 화면으로">✕ 회의 화면으로</button>}
      {isClosed && getToken() && <button id="new-meeting" onClick={() => setNewOpen(true)} disabled={newOpen} title="회의 내용을 지우고 기본 문서로 새 회의 (모든 참석자)">🆕 새 회의 시작</button>}
      {newOpen && <NewMeetingDialog onClose={() => setNewOpen(false)} onDone={setNewMsg} />}
      {newMsg && <div id="notice">{newMsg}</div>}
      {minutes && <Minutes onClose={() => setMinutes(false)} />}
      {v.notice && <div id="notice">{v.notice}</div>}
      {camErr && (gesture || voteOpen) && <div id="notice">📷 {camErr}</div>}
      {/* ep: Google Sheet, Doc 바로가기 + 테스트 대본 선택(임시). 무대(1920x1080) 배치는 건드리지 않게 창 왼쪽 아래 층에 둔다. 문서가 바뀌면(제목) 다시 받는다 */}
      <div id="wall-tools"><DocLinks refreshKey={Object.values(v.state.docs).map((d) => d.title).join("|")} /><DocPicker /><LangToggle onChange={onLang} /><TestSeedPicker /><DemoPlayer refreshKey={Object.values(v.state.docs).map((d) => d.title).join("|")} />{onLeave && <button id="leave-meeting" onClick={() => { if (confirm("회의에서 나갈까요?")) onLeave(); }} title="참석자 목록에서 빠지고 입장 화면으로">🚪 회의 나가기</button>}</div>
    </>}>
      <SceneWall w={w} band={band} animate onOpenMinutes={() => setMinutes(true)}
        live={{ mic, onMic: toggleMic, gesture, onGesture: () => setGesture(!gesture), connected: v.connected, status: <Moai v={v} mic={mic} size={56} word={false} />, onDocTab, typing, onType: () => setTyping(true), onTypeEnd: () => setTyping(false), // hs: gesture 토글 전달
          mode, hint: import.meta.env.DEV ? "Ines: line speaks as Ines.  /up /down /1 /2 /t for hands" : undefined,
          // 개발 서버: 'Ines: 줄'은 Ines로, '/2'는 손 신호로(1인 시험, puppets.ts). 운영 빌드는 내 발화만.
          onSay: (text) => { if (import.meta.env.DEV) sayAs(text, me ?? "").catch(() => {}); else send({ kind: "utterance.final", payload: { text } }); } }} />
    </FitStage>
  );
}
