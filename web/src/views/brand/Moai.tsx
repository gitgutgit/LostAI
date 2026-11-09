// MOAI mascot: one statue, five faces. The body never changes; only the face layer, one prop
// (listening headphones, writing pencil, vote wig, decided thumb) and the glow colour switch,
// so a state change never jumps the layout.
// Geometry is the 64-grid drawing from web/design/brand/logo/v2/build.py; keep both in step.
import { useEffect, useId, useRef, useState } from "react";
import type { RoomView } from "../../core/reducer";
import { MOAI_LABEL, moaiSignal, type MoaiState } from "./moaiState";
import "./moai.css";

const HEAD = "M21 6H43Q45 6 45.3 8L48 46H16L18.7 8Q19 6 21 6Z";
const BASE = "M11 60L15.5 48H48.5L53 60Z";
const FACE = {
  neutral: ["M22 17H42V22H22Z", "M29.5 22H34.5V33H29.5Z", "M26 38H38V41H26Z"],
  down: ["M23 22H41V26H23Z", "M29.5 26H34.5V34H29.5Z", "M26 38H38V41H26Z"],
  brow: ["M22 18H31V23H22Z", "M33 15.5L42 11.5L43.6 16L34.6 20Z", "M29.5 20H34.5V33H29.5Z", "M27 38H37V41H27Z"],
  frown: ["M21 14.5L31.5 19V24L21 19.5Z", "M43 14.5L32.5 19V24L43 19.5Z", "M29.5 22H34.5V33H29.5Z", "M27.5 39H36.5V42H27.5Z"],
} as const;
// Wordmark face: the joined brow and nose read as a T, so the wordmark spelled MOAT (12:21). Two eyes and a
// detached nose leave no crossbar; context-free reading went from 2/12 to 11/12 MOAI (wordmark/result_wm.txt, v1).
const FACE_WORDMARK = ["M22.5 18H29.5V23H22.5Z", "M34.5 18H41.5V23H34.5Z", "M30 26H34V34H30Z", "M26 38H38V41H26Z"];
const THUMB = "M45 41V31.5Q45 29 47.5 29H49Q51.5 29 51.5 31.5V41H55Q58 41 58 44V52Q58 55 55 55H44Q41 55 41 52V44Q41 41 44 41Z";
const THUMB_CUTS = ["M41 45.5H52V47H41Z", "M41 49.5H52V51H41Z"];
const PHONES_CUPS = "M7 20.5Q7 17 10.5 17H14.5Q18.5 17 18.5 20.5V33.5Q18.5 37 14.5 37H10.5Q7 37 7 33.5Z" +
  "M45.5 20.5Q45.5 17 49.5 17H53.5Q57 17 57 20.5V33.5Q57 37 53.5 37H49.5Q45.5 37 45.5 33.5Z";
const PHONES_BAND = "M12.5 18V14Q12.5 2 32 2Q51.5 2 51.5 14V18";
const PENCIL = "M-4 -17H4V8L0 16L-4 8Z";
const PENCIL_CUTS = ["M-4 -11.5H4V-9.5H-4Z", "M-4 7H4V9H-4Z"];
const PENCIL_T = "translate(48.5 37) rotate(30)";
const WIG_CAP = "M16 15Q15 3.5 32 3.5Q49 3.5 48 15Q44 11.5 40 13Q36 10 32 12.5Q28 10 24 13Q20 11.5 16 15Z";
const WIG_CURLS: [number, number][] = [13.5, 50.5].flatMap((x) => [17, 25.5, 34].map((y) => [x, y] as [number, number]));

/** Which vote face ships. Both are kept until the team vote on the candidates. */
export type VoteFace = "wig" | "frown";

const DECIDED_MS = 2500; // the nod plays once, then the statue goes back to its base state
const WRITING_MIN_MS = 1200; // a just-applied change keeps the writing face long enough to be seen

/** `bare` drops the listening headphones: the mic is off, so the statue is not listening. */
export function MoaiFigure({ state, voteFace = "wig", size = 40, bare = false }: { state: MoaiState; voteFace?: VoteFace; size?: number; bare?: boolean }) {
  const uid = useId().replace(/:/g, "");
  const face = state === "writing" ? FACE.down : state === "paused" ? FACE.brow : state === "vote" && voteFace === "frown" ? FACE.frown : FACE.neutral;
  const wig = state === "vote" && voteFace === "wig";
  const thumb = state === "decided";
  const phones = state === "listening" && !bare;
  const pencil = state === "writing";
  return (
    <svg className={`moai moai-${state}`} viewBox="0 0 64 64" width={size} height={size} aria-hidden="true" focusable="false">
      <defs>
        <mask id={`mf${uid}`}>
          <rect width="64" height="64" fill="#fff" />
          <g fill="#000">
            {face.map((d) => <path key={d} d={d} />)}
            {thumb && <path d={THUMB} stroke="#000" strokeWidth={5} strokeLinejoin="round" />}
            {phones && <path d={PHONES_CUPS} stroke="#000" strokeWidth={5} />}
            {pencil && <path transform={PENCIL_T} d={PENCIL} stroke="#000" strokeWidth={5} strokeLinejoin="round" />}
          </g>
        </mask>
        {thumb && (
          <mask id={`mh${uid}`}>
            <rect width="64" height="64" fill="#fff" />
            <g fill="#000">{THUMB_CUTS.map((d) => <path key={d} d={d} />)}</g>
          </mask>
        )}
        {pencil && (
          <mask id={`mp${uid}`} maskUnits="userSpaceOnUse" x="-30" y="-30" width="60" height="60">
            <rect x="-30" y="-30" width="60" height="60" fill="#fff" />
            <g fill="#000">{PENCIL_CUTS.map((d) => <path key={d} d={d} />)}</g>
          </mask>
        )}
      </defs>
      <g className="moai-body" fill="currentColor">
        {wig && <g className="moai-wig">{WIG_CURLS.map(([x, y]) => <circle key={`${x}-${y}`} cx={x} cy={y} r={5.6} />)}</g>}
        <g mask={`url(#mf${uid})`}><path d={HEAD} /><path d={BASE} /></g>
        {wig && <path className="moai-wig" d={WIG_CAP} strokeLinejoin="round" />}
        {thumb && <path d={THUMB} mask={`url(#mh${uid})`} />}
        {phones && <><path d={PHONES_BAND} fill="none" stroke="currentColor" strokeWidth={4} strokeLinecap="round" /><path d={PHONES_CUPS} /></>}
        {pencil && <g transform={PENCIL_T}><path d={PENCIL} mask={`url(#mp${uid})`} /></g>}
      </g>
    </svg>
  );
}

/** Live status light: derives the state from the room view and shows the statue plus its word.
 *  `mic` is given where the screen owns a microphone (the decision wall): off means the statue is not
 *  listening, so the listening face loses its headphones, dims and reads Mic off. Typed chat and hand signs
 *  still reach the agent with the mic off, so writing, conflict, vote and decided still show. */
export function Moai({ v, voteFace, size, mic, word = true }: { v: Pick<RoomView, "events" | "state" | "paused" | "connected">; voteFace?: VoteFace; size?: number; mic?: boolean; word?: boolean }) {
  const sig = moaiSignal(v);
  const [held, setHeld] = useState<MoaiState | null>(null);
  const seenDecided = useRef<number | null | undefined>(undefined);
  const timer = useRef<number | undefined>(undefined);

  // decided: a new resolution seq shows the nod once. The first render only records the seq,
  // so joining a room that already has decisions does not replay an old nod.
  useEffect(() => {
    if (seenDecided.current === undefined) { seenDecided.current = sig.decidedSeq; return; }
    if (sig.decidedSeq !== null && sig.decidedSeq !== seenDecided.current) {
      seenDecided.current = sig.decidedSeq;
      hold("decided", DECIDED_MS);
    }
  }, [sig.decidedSeq]);

  // writing: keep the face for a minimum time so a fast apply is still visible
  useEffect(() => { if (sig.base === "writing") hold("writing", WRITING_MIN_MS); }, [sig.base, v.events.length]);
  useEffect(() => () => window.clearTimeout(timer.current), []);

  function hold(s: MoaiState, ms: number) {
    setHeld((cur) => (cur === "decided" && s === "writing" ? cur : s));
    window.clearTimeout(timer.current);
    timer.current = window.setTimeout(() => setHeld(null), ms);
  }

  // vote and conflict always win over a held face: the room must see that writing stopped
  const state: MoaiState = sig.base === "vote" || sig.base === "paused" ? sig.base : held ?? sig.base;
  const micOff = mic === false && state === "listening";
  const label = !v.connected ? "Offline" : micOff ? "Mic off" : state === "paused" && !sig.conflict ? "Paused" : MOAI_LABEL[state];
  return (
    <span className={`moai-light${v.connected && !micOff ? "" : " off"}`} role="status" aria-live="polite" aria-label={word ? undefined : label}>
      <MoaiFigure key={state === "decided" ? `d${sig.decidedSeq}` : state} state={state} voteFace={voteFace} size={size} bare={micOff} />
      {word && <span className="moai-word">{label}</span>}
    </span>
  );
}

/** Fixed status light for scripted scenes (the ?view=wall scenes and the render v0.4 source): statue plus word,
 *  no room view. The live wall uses Moai. */
export function MoaiStatic({ state, voteFace, size = 56, word = true }: { state: MoaiState; voteFace?: VoteFace; size?: number; word?: boolean }) {
  return (
    <span className="moai-light" role="status" aria-label={word ? undefined : MOAI_LABEL[state]}>
      <MoaiFigure state={state} voteFace={voteFace} size={size} />
      {word && <span className="moai-word">{MOAI_LABEL[state]}</span>}
    </span>
  );
}

/** Wordmark: MOA + the statue standing in for the I, with a split-eye face so it reads I, not T. */
export function MoaiWordmark({ height = 32, title = "MOAI" }: { height?: number; title?: string }) {
  const uid = useId().replace(/:/g, "");
  return (
    <svg className="moai-wordmark" viewBox="0 0 178 64" height={height} width={(height * 178) / 64} role="img" aria-label={title}>
      <defs>
        <mask id={`mw${uid}`}>
          <rect width="64" height="64" fill="#fff" />
          <g fill="#000">{FACE_WORDMARK.map((d) => <path key={d} d={d} />)}</g>
        </mask>
      </defs>
      <g fill="currentColor">
        <path d="M0 60V4H12.5L20 29L27.5 4H40V60H30V27L23.5 47H16.5L10 27V60Z" />
        <path fillRule="evenodd" d="M63 4C72 4 80 10 80 20V44C80 54 72 60 63 60C54 60 46 54 46 44V20C46 10 54 4 63 4ZM63 15C60 15 58 17 58 20V44C58 47 60 49 63 49C66 49 68 47 68 44V20C68 17 66 15 63 15Z" />
        <path fillRule="evenodd" d="M95 4H113L124 60H113L111 48H97L95 60H84ZM98.5 38H109.5L104 13Z" />
        <g transform="translate(118 0)" mask={`url(#mw${uid})`}><path d={HEAD} /><path d={BASE} /></g>
      </g>
    </svg>
  );
}
