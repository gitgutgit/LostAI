// 결정 벽 무대(렌더 v0.4)를 WallState 하나로 그린다. DOM 구조와 클래스는 시안과 같게 둔다(wall.css가 원문 그대로라서).
// author: ProfessionalSeaweedDevourer
import { createContext, Fragment, useContext, useEffect, useRef, type CSSProperties, type ReactNode } from "react";
import type { CardA, CardB, CardBMsg, CellKey, CellVal, Chip, DocRow, EndCard, Rich, WallState } from "./types";

const Lit = createContext<Set<string>>(new Set());

export function Ref({ r }: { r: string }) {
  const lit = useContext(Lit).has(r);
  return <span className={`ref${lit ? " lit" : ""}`} data-r={r}>{r}</span>;
}

export function ChipEl({ c }: { c: Chip }) {
  const set = useContext(Lit);
  const lit = !!c.r && set.has(c.r);
  return <span className={`chip ${c.cls ?? ""}${lit ? " lit" : ""}`} data-r={c.r || undefined}>{c.t}</span>;
}

export function RichEl({ rich }: { rich: Rich }) {
  return (
    <>
      {rich.map((s, i) => {
        if (typeof s === "string") return <Fragment key={i}>{s}</Fragment>;
        if ("ref" in s) return <Ref key={i} r={s.ref} />;
        if ("b" in s) return <b key={i}>{s.b}</b>;
        if ("bad" in s) return <span key={i} className="bad">{s.bad}</span>;
        if ("tag" in s) return <span key={i} className="tagp">{s.tag}</span>;
        return <ChipEl key={i} c={s.chip} />;
      })}
    </>
  );
}

// ------------------------------------------------------------------ 문서

function Cell({ row, k, val }: { row: DocRow; k: CellKey; val: CellVal }) {
  const fresh = !!row.fresh && k in row.fresh;
  const delay = fresh ? row.fresh![k] : 0;
  const wrap = (k === "o" && row.wrapO) || !!val.br;
  const style: CSSProperties | undefined = delay ? { animationDelay: `${delay}ms` } : undefined;
  return (
    <span className={`${fresh ? "fresh" : ""}${wrap ? " wrap2" : ""}`} style={style}>
      {val.old !== undefined && <s>{val.old}</s>}{val.br && <br />}{val.v}
    </span>
  );
}

function Row({ r, ghost, hide = [], grid }: { r: DocRow; ghost: boolean; hide?: CellKey[]; grid?: string }) {
  const show = (k: CellKey) => !hide.includes(k);
  const cls = ["g"];
  if (r.hl) cls.push("hl");
  if (r.newrow) cls.push("newrow");
  if (r.rowfresh) cls.push("fresh");
  if (r.tall || r.src.length > 1) cls.push("tall");
  const vtName: CSSProperties = { viewTransitionName: r.vt ? "qcard" : "none" } as CSSProperties;
  let mid: ReactNode;
  if (r.cf) {
    mid = ghost ? (
      <>
        <div className="cf" id="c33" style={{ gridColumn: "3 / 6", ...vtName }}>
          <div><Ref r={r.cf.a.r} /><br />{r.cf.a.short}</div><div><Ref r={r.cf.b.r} /><br />{r.cf.b.short}</div>
        </div>
        <span className="gh">{r.gh?.[0]}</span><span className="gh">{r.gh?.[1]}</span>
      </>
    ) : (
      <div className="cf" id="c33" style={vtName}>
        <div><b>{r.cf.a.who}</b> <Ref r={r.cf.a.r} /><br />{r.cf.a.v}</div>
        <div><b>{r.cf.b.who}</b> <Ref r={r.cf.b.r} /><br />{r.cf.b.v}</div>
      </div>
    );
  } else if (ghost) {
    const bad = r.ghbad ? " bad" : "";
    mid = (
      <>
        <Cell row={r} k="s" val={r.s} /><Cell row={r} k="e" val={r.e} /><Cell row={r} k="d" val={r.d} />
        {r.gh
          ? <><span className={`gh${bad}`}>{r.gh[0]}</span><span className={`gh${bad}`}>{r.gh[1]}{r.ghref && <Ref r={r.ghref} />}</span></>
          : <><span className="gh e" /><span className="gh e" /></>}
      </>
    );
  } else if (r.vt) {
    mid = (
      <div className="span4" id="c33" style={{ display: "grid", gridTemplateColumns: "100px 100px 74px 160px", padding: 0, ...vtName }}>
        <Cell row={r} k="s" val={r.s} /><Cell row={r} k="e" val={r.e} /><Cell row={r} k="d" val={r.d} /><Cell row={r} k="st" val={r.st} />
      </div>
    );
  } else {
    mid = <>{(["s", "e", "d", "st"] as CellKey[]).filter(show).map((k) => <Cell key={k} row={r} k={k} val={r[k]} />)}</>;
  }
  const src = ghost ? r.src.slice(0, 1) : r.src;
  return (
    <div className={cls.join(" ")} style={grid ? { gridTemplateColumns: grid } : undefined}>
      <span className="w">{r.w}</span><span>{r.t}</span>
      {!ghost && show("o") && <Cell row={r} k="o" val={r.o} />}
      {mid}
      <span className="src">{src.map((c, i) => <ChipEl key={i} c={c} />)}</span>
      {r.memo && (
        <div className={`memo${r.memo.bad ? " bad" : ""}${r.memo.fresh ? " fresh" : ""}`}>
          <span className="mt">{r.memo.t}</span>{r.memo.c && <ChipEl c={r.memo.c} />}
        </div>
      )}
    </div>
  );
}

function useChanged<T>(value: T): boolean {
  const prev = useRef(value);
  const changed = prev.current !== value;
  useEffect(() => { prev.current = value; });
  return changed;
}

const COLS = ["WBS", "Task", "Owner", "Start", "End", "Days", "State"];
const HIDE_KEYS: CellKey[] = ["o", "s", "e", "d", "st"];

function Doc({ w, band, animate }: { w: WallState; band: boolean; animate: boolean }) {
  const d = w.doc;
  const ghost = !!d.ghost;
  const bump = useChanged(d.edits) && animate;
  return (
    <div id="doc" className={ghost ? "ghost" : ""}>
      <div className="sh" id="sh1" /><div className="sh" id="sh2" />
      <div id="sheet">
        <div id="qband">{band && w.cardA && <QLine a={w.cardA} />}</div>
        <div className="dh">
          <b>{d.title}<span className="m">{d.subtitle}</span></b>
          <span id="count" className={bump ? "bump" : ""}><i />{`Live  ${d.edits} edits written, ${d.undone} undone`}</span>
        </div>
        <div id="dnote"><RichEl rich={d.note} /></div>
        <div id="rows">
          {ghost
            ? <div className="g colh"><span>WBS</span><span>Task</span><span>Start</span><span>End</span><span>Days</span><span>{d.ghost!.cols[0]}</span><span>{d.ghost!.cols[1]}</span><span>Source</span></div>
            : <div className="g colh" style={d.grid ? { gridTemplateColumns: d.grid } : undefined}>
                {(d.cols ?? COLS).map((c, i) => (i >= 2 && d.hide?.includes(HIDE_KEYS[i - 2]) ? null : <span key={i}>{c}</span>))}<span>Source</span>
              </div>}
          {d.rows.map((r, i) => <Row key={`${i}-${r.w}`} r={r} ghost={ghost} hide={d.hide} grid={d.grid} />)}
        </div>
      </div>
    </div>
  );
}

// ------------------------------------------------------------------ 카드 A

function QLine({ a }: { a: CardA }) {
  return <><span className="qn">{a.q}</span>{a.title}</>;
}

function CardAEl({ a }: { a: CardA | null }) {
  const style = { viewTransitionName: a?.fromCell ? "qcard" : "none" } as CSSProperties;
  if (!a) return <div id="cardA" className="gone" style={style} />;
  return (
    <div id="cardA" style={style}>
      <div id="qline"><QLine a={a} /></div>
      {a.options?.map((o) => (
        <div className="opt" key={o.n}>
          <div className="onum">{o.n}</div>
          <div className="oleft"><div className="oname">{o.name}</div><div className="osrc"><RichEl rich={o.src} /></div></div>
          <div className="oside">{o.side && <><div className="cost"><RichEl rich={o.side.cost} /></div><div className="costsub"><RichEl rich={o.side.sub} /></div></>}</div>
        </div>
      ))}
      {a.reframe && (
        <div className="rf">
          {a.reframe.old && <div className="old">{a.reframe.old}</div>}
          <div className="new">{a.reframe.now}</div>
          <div className="vt">{a.reframe.vt}</div>
        </div>
      )}
    </div>
  );
}

// ------------------------------------------------------------------ 카드 B

function Flap({ word, off, animate }: { word: string; off: number[]; animate: boolean }) {
  const prev = useRef<string>(word);
  const gen = useRef(0);
  const changed = prev.current !== word;
  if (changed) gen.current += 1;
  const before = prev.current;
  useEffect(() => { prev.current = word; });
  return (
    <div id="flap">
      {Array.from({ length: 9 }, (_, j) => {
        const ch = word[j] && word[j] !== " " ? word[j] : "";
        const was = before[j] && before[j] !== " " ? before[j] : "";
        let cls = "cell" + (ch ? " on" : "");
        if (ch && off.includes(j)) cls = "cell off";
        const flip = animate && changed && ch !== was;
        return (
          <div key={`${j}-${flip ? gen.current : 0}`} className={cls + (flip ? " flip" : "")}
               style={flip ? { animationDelay: `${j * 35}ms` } : undefined}>{ch}</div>
        );
      })}
    </div>
  );
}

function EndCardEl({ c }: { c: EndCard }) {
  return (
    <div className={`icard${c.parked ? " p" : ""}`}>
      <span className="qn">{c.q}</span><span className="ct">{c.title}</span>
      {c.lines.map((l, i) => <span key={i} className={`cm${l.green ? " g" : ""}`}><RichEl rich={l.rich} /></span>)}
    </div>
  );
}

function Msg({ m }: { m: CardBMsg }) {
  switch (m.kind) {
    case "headline":
      return (
        <>
          <div className={m.bigCls ?? "b40"}>{m.underline ? <span className="ul"><RichEl rich={m.big} /></span> : <RichEl rich={m.big} />}</div>
          {m.sub && <div className="sub" style={{ marginTop: m.subTop ?? 0 }}><RichEl rich={m.sub} /></div>}
        </>
      );
    case "facts":
      return <><div className="b40">{m.title}</div><div className="fc">{m.chips.map((c, i) => <ChipEl key={i} c={c} />)}</div></>;
    case "sentence":
      return <><div className="b32">{m.sentence}</div><div className="b40" style={{ marginTop: 6 }}><RichEl rich={m.big} /></div></>;
    case "costs":
      return (
        <>
          <div className="b32"><RichEl rich={m.line} /></div>
          <div className="sub" style={{ marginTop: 4 }}>{m.sub}</div>
          <div className="sub bandonly">{m.bandSub}</div>
        </>
      );
    case "countdown":
      return (
        <>
          <div className="t56"><span className="qn">{m.q}</span>{m.title}</div>
          <div style={{ height: 390 }} />
          <div className="tp">{m.prompt}</div>
        </>
      );
    case "split":
      return (
        <>
          <div className="t56"><span className="qn">{m.q}</span>{m.title}</div>
          <div style={{ height: 440 }} />
          {m.lines.map((l, i) => <div key={i} className="tp" style={i ? { marginTop: 20 } : undefined}>{l}</div>)}
        </>
      );
    case "converged": {
      const total = m.dist.reduce((a, d) => a + d[2], 0) || 1;
      // 바늘: 왼쪽(1번)에서 오른쪽(2번)까지 반원. 2번 쪽 비율만큼 기운다. 시안의 바늘(4 of 4 쪽, 45도)과 같게 맞춘 식.
      const share = m.dist[1] ? m.dist[1][2] / total : 0;
      const ang = Math.PI * (1 - share * 0.75);
      const nx = 320 + Math.round(263 * Math.cos(ang)), ny = 330 - Math.round(263 * Math.sin(ang));
      return (
        <>
          <div className="t56"><span className="qn">{m.q}</span>{m.first ? m.first.title : "Revote"}</div>
          <div className="mv" style={{ marginTop: 30 }}>{m.first ? m.first.winner : `${m.moved} votes moved`}</div>
          {m.first
            ? <div className="t56" style={{ marginTop: 20 }}>{m.first.sub}</div>
            : <div className="t56" style={{ marginTop: 20 }}>from <span className="num">{m.from[0]}</span>{`${m.from[1]} to `}<span className="num">{m.to[0]}</span>{m.to[1]}</div>}
          <svg id="dial" viewBox="0 0 640 380" aria-hidden="true">
            <path d="M40 330 A280 280 0 0 1 600 330" fill="none" stroke="#4A5A6B" strokeWidth="22" />
            <path d="M320 50 A280 280 0 0 1 518 132" fill="none" stroke="#F3C316" strokeWidth="22" />
            <line x1="320" y1="330" x2="320" y2="70" stroke="#4A5A6B" strokeWidth="6" strokeDasharray="14 12" />
            <line x1="320" y1="330" x2={nx} y2={ny} stroke="#ffffff" strokeWidth="12" />
            <rect x="300" y="310" width="40" height="40" fill="#ffffff" />
            <text x="40" y="378" fontSize="56" fontWeight="700" fill="#ffffff" textAnchor="middle" fontFamily="Barlow Condensed, Arial Narrow, sans-serif">1</text>
            <text x="600" y="378" fontSize="56" fontWeight="700" fill="#ffffff" textAnchor="middle" fontFamily="Barlow Condensed, Arial Narrow, sans-serif">2</text>
          </svg>
          <div className="dist">
            {m.dist.map(([n, name, count]) => (
              <div className="dr" key={n}>
                <span className="num">{n}</span><span>{name}</span>
                <span className="bars">{Array.from({ length: count }, (_, i) => <i key={i} />)}<em>{count}</em></span>
              </div>
            ))}
          </div>
          <div className="cw">{m.foot}</div>
        </>
      );
    }
    case "closed":
      return (
        <>
          <div className="e96">{m.title}</div>
          <div className="ecards">{m.cards.map((c) => <EndCardEl key={c.q} c={c} />)}</div>
          <div className="estats">
            {m.stats.map(([n, a, b], i) => <div key={i}><div className="n">{n}</div><div className="t">{a}{b !== undefined && <><br />{b}</>}</div></div>)}
          </div>
          <div className="efoot">{m.foot}</div>
        </>
      );
  }
}

function CardBEl({ b, animate }: { b: CardB; animate: boolean }) {
  return (
    <div id="cardB" className={b.take ? `take ${b.take}` : ""}>
      <Flap word={b.flap} off={b.off ?? []} animate={animate} />
      <div id="bside">{b.side ?? ""}</div>
      <div id="bmsg"><Msg m={b.msg} /></div>
    </div>
  );
}

// ------------------------------------------------------------------ 참가자 손 표시

const GL: Record<string, ReactNode> = {
  cam: <><rect x="6" y="26" width="60" height="44" rx="6" fill="none" stroke="#17212B" strokeWidth="5" /><circle cx="36" cy="48" r="12" fill="none" stroke="#17212B" strokeWidth="5" /></>,
  fd: <g className="fd turn"><rect x="6" y="6" width="60" height="88" rx="5" fill="#17212B" /><path d="M16 16 L56 84 M36 16 L56 50 M16 50 L36 84" stroke="#4A5762" strokeWidth="5" /></g>,
  nr: <rect x="8" y="8" width="56" height="84" rx="5" fill="none" stroke="#4A5762" strokeWidth="4" strokeDasharray="10 8" />,
  again: <><rect x="8" y="8" width="56" height="84" rx="5" fill="none" stroke="#17212B" strokeWidth="5" strokeDasharray="10 8" /><rect x="0" y="40" width="72" height="20" fill="#F3C316" /></>,
  thumb: <path d="M10 46h14v42H10z M28 88h26a7 7 0 0 0 7-6l5-24a7 7 0 0 0-7-8H44l3-18a7 7 0 0 0-7-8h-3L28 46z" fill="#1E7B4F" />,
};

// ------------------------------------------------------------------ 무대

// 실화면 조작: 마이크 표지, 임시 채팅(발화 줄 자리에 입력칸, 마이크 없이 시험용)
export interface LiveCtl { mic: boolean; onMic: () => void; connected: boolean; typing: boolean; onType: () => void; onSay: (text: string) => void; onTypeEnd: () => void;
  /** 입력칸 안내 문구, 서버 모드(MOCK, LIVE: 비용 여부 표시) */ hint?: string; mode?: string }

export function Wall({ w, band, animate, onOpenMinutes, live }: { w: WallState; band: boolean; animate: boolean; onOpenMinutes?: () => void; live?: LiveCtl }) {
  const lit = new Set(w.lit);
  const slotsDone = w.slots.map((s) => s === "done").join();
  const prevDone = useRef(slotsDone);
  const fillFrom = useRef<boolean[]>(w.slots.map((s) => s === "done"));
  if (prevDone.current !== slotsDone) { fillFrom.current = prevDone.current.split(",").map((x) => x === "true"); prevDone.current = slotsDone; }
  return (
    <Lit.Provider value={lit}>
      <div id="stage" className={`${w.big ? "big" : ""}${band ? " band" : ""}${live ? " live" : ""}`.trim()}>
        <div className="head" style={{ left: 24 }}>Today</div>
        <div id="slots">
          {w.slots.map((s, i) => {
            const fill = animate && s === "done" && !fillFrom.current[i];
            return <div key={i} className={`slot${s ? " " + s : ""}${fill ? " fill" : ""}`} id={`q${i + 1}`}>{`Q${i + 1}`}</div>;
          })}
        </div>
        <div className="head" style={{ left: 430 }} id="prog">{w.progText ?? `${w.decided} of ${w.total} decided`}</div>
        <div className="head" style={{ left: 1270 }}>Now<span className="n" id="hNow">{w.now}</span></div>
        {live
          ? <button id="mark" className={live.mic ? "on" : ""} onClick={live.onMic} title="마이크 (M)">
              {!live.connected ? "Offline" : live.mic ? <><i />Listening</> : "Mic off"}{live.mode && <em className={live.mode === "LIVE" ? "paid" : ""}>{live.mode}</em>}
            </button>
          : <div id="mark">{w.mark}</div>}

        <Doc w={w} band={band} animate={animate} />

        <div id="idle" style={{ display: w.idle ? "block" : "none" }}>
          {(w.idle ?? ["No open question.", "Listening and writing to the WBS."]).map((l, i) => <Fragment key={i}>{i > 0 && <br />}{l}</Fragment>)}
        </div>
        <CardAEl a={w.cardA} />
        <CardBEl b={w.cardB} animate={animate} />

        <div id="dp">
          <div><div className="dph">Decided<span className="n" id="hDec">{w.decidedMarks.length}</span></div>
            <div className="mk" id="dmk">{w.decidedMarks.map((q) => <span key={q}>{q}</span>)}</div></div>
          <div><div className="dph">Parked<span className="n" id="hPark">{w.parked.length}</span></div>
            <div id="pmk">{w.parked.length
              ? w.parked.map((p) => <div className="pk" key={p.q}><b>{p.q}</b>{` ${p.text}${p.ref ? " " : ""}`}{p.ref && <Ref r={p.ref} />}</div>)
              : <div className="empty">none yet</div>}</div></div>
        </div>

        {live?.typing
          ? <div id="said"><input id="sayin" autoFocus placeholder={live.hint ?? "Type a line, Enter to send, Esc to close"}
              onKeyDown={(e) => {
                const t = e.currentTarget;
                if (e.key === "Enter" && !e.nativeEvent.isComposing && t.value.trim()) { live.onSay(t.value.trim()); t.value = ""; }
                else if (e.key === "Escape") live.onTypeEnd();
              }} /></div>
          : <div id="said" onClick={live ? live.onType : onOpenMinutes} title={live ? "입력 (Enter)" : onOpenMinutes ? "회의록 전문" : undefined}>
              {w.said.length === 0 && live ? <span className="hint">Press Enter to type a line</span> : w.said.map((u, i) => (
                <Fragment key={i}><b className={lit.has(u.line) ? "lit" : undefined}>{`${u.line} ${u.who}`}</b>{` ${u.text}${i < w.said.length - 1 ? " " : ""}`}</Fragment>
              ))}
            </div>}
        <div id="log" onClick={onOpenMinutes} title={onOpenMinutes ? "회의록 전문" : undefined}><b>Log</b><RichEl rich={typeof w.log[0] === "string" ? [` ${w.log[0]}`, ...w.log.slice(1)] : [" ", ...w.log]} /></div>

        <div id="people">
          {w.people.map((p, i) => {
            let g: string = w.glyph ?? "";
            if (g === "fd") g = p.tone === "again" ? "again" : p.tone === "ok" ? "fd" : "nr";
            return (
              <div key={i} className={`pp${w.turn === i ? " turn" : ""}`} id={`p${i}`}>
                <svg className={`gl${g ? " on" : ""}`} viewBox="0 0 72 100">{g ? GL[g] : null}</svg>
                <div className="nm">{p.name}</div>
                <div className={`st ${p.tone}`}>{p.status}</div>
              </div>
            );
          })}
        </div>
      </div>
    </Lit.Provider>
  );
}
