// 결정 벽 화면. 장면 견본(#d1..#s9)이나 실시간 회의(?live=1)에서 WallState를 받아 Wall로 그린다.
// 주소: ?view=wall#s6, ?shot(움직임 끔, 캡처용), ?band=0(질문 띠 끔), ?play(4초마다 다음 장면), 화살표 키.
// author: ProfessionalSeaweedDevourer
import { useEffect, useState } from "react";
import { flushSync } from "react-dom";
import { Wall } from "./Wall";
import { scene, SCENES, type SceneId } from "./scenes";
import "./wall.css";

const QP = new URLSearchParams(location.search);
const SHOT = QP.has("shot");
const BAND = QP.get("band") !== "0";
if (SHOT) document.documentElement.classList.add("shot");

const fromHash = (): SceneId => {
  const h = location.hash.slice(1) as SceneId;
  return SCENES.includes(h) ? h : "d1";
};

function useFit(): number {
  const calc = () => (SHOT ? 1 : Math.min(1, window.innerWidth / 1920, (window.innerHeight - 56) / 1080));
  const [s, setS] = useState(calc);
  useEffect(() => {
    const on = () => setS(calc());
    window.addEventListener("resize", on);
    return () => window.removeEventListener("resize", on);
  }, []);
  return s;
}

export function WallView() {
  const [id, setId] = useState<SceneId>(fromHash);
  const [animate, setAnimate] = useState(false);
  const [playing, setPlaying] = useState(QP.has("play") && !SHOT);
  const fit = useFit();

  useEffect(() => {
    const go = () => {
      const next = fromHash();
      const apply = () => flushSync(() => { setAnimate(!SHOT); setId(next); });
      const doc = document as Document & { startViewTransition?: (cb: () => void) => { skipTransition: () => void; finished: Promise<void> } };
      if (!SHOT && doc.startViewTransition) {
        let done = false;
        const vt = doc.startViewTransition(() => { done = true; apply(); });
        // 프레임이 안 나오는 환경(숨은 탭, 일부 headless)에서는 전환을 건너뛴다
        setTimeout(() => { if (!done) vt.skipTransition(); }, 200);
      } else apply();
    };
    const key = (e: KeyboardEvent) => {
      const k = SCENES.indexOf(fromHash());
      if (e.key === "ArrowRight") location.hash = SCENES[Math.min(SCENES.length - 1, k + 1)];
      if (e.key === "ArrowLeft") location.hash = SCENES[Math.max(0, k - 1)];
    };
    window.addEventListener("hashchange", go);
    document.addEventListener("keydown", key);
    return () => { window.removeEventListener("hashchange", go); document.removeEventListener("keydown", key); };
  }, []);

  useEffect(() => {
    if (!playing) return;
    const t = setInterval(() => { location.hash = SCENES[(SCENES.indexOf(fromHash()) + 1) % SCENES.length]; }, 4000);
    return () => clearInterval(t);
  }, [playing]);

  const w = scene(id);
  const band = BAND && !!w.cardA && !w.cardB.take;

  return (
    <>
      <div style={{ width: 1920 * fit, height: 1080 * fit, overflow: "hidden" }}>
        <div style={fit === 1 ? undefined : { transform: `scale(${fit})`, transformOrigin: "0 0" }}>
          <Wall w={w} band={band} animate={animate} />
        </div>
      </div>
      {!SHOT && (
        <div id="controls">
          {SCENES.map((s) => <button key={s} className={s === id ? "on" : ""} onClick={() => { location.hash = s; }}>{s}</button>)}
          <button className={playing ? "on" : ""} onClick={() => setPlaying(!playing)}>Play</button>
          <span style={{ marginLeft: 12 }}>Left / Right keys, #d1 #d2 #s2..#s8 #r1 #s9, ?play, ?shot, ?band=0</span>
        </div>
      )}
    </>
  );
}
