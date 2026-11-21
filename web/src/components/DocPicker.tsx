// 회의 문서 고르기·새로 만들기: 각자 Google 로그인 → 자기 Sheet(보드) / Doc(노트)을 골라 회의 원본으로. author: Mal-Mi-Jal
// 서버: server/sync/source_api.py. 파일 목록은 Google Picker가 내 브라우저에서 Google과 직접 주고받는다
// (다른 사람 Drive는 안 보이고, 우리 서버는 고른 파일 id만 받는다). 권한은 drive.file = 고른 파일·만든 파일만.
// 바꾸면 지금 회의 내용은 비워지고, 지금 문서에는 회의 결과를 남기거나(남기기) 회의 전 상태로 돌린다(되돌리기).
// 기본값: 기본 WBS(서버 계정) = 되돌리기, 각자 문서 = 남기기. 주인 승인이면 주인이 승인 카드에서 고른다 (PR3).
// Google 로그인은 서버가 준 열쇠(gsid)를 이 탭의 sessionStorage에만 둔다. 입장 토큰은 이름만으로 만들어져
// 같은 이름이면 같으므로, 열쇠 없이는 남의 Google 로그인(→ Drive)을 쓸 수 없게 하려는 것.
// 어느 화면에든 <DocPicker /> 한 줄로 붙일 수 있다 (버튼 + 창).
import { useCallback, useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { getToken } from "../core/ws";
import "./DocPicker.css";

type Kind = "sheet" | "doc";
type Config = { enabled: boolean; client_id: string; api_key: string; app_id: string; scope: string; me: { email: string } | null };
// 바꾸기 요청 (PR2): 주인 탭엔 request(승인/거절), 요청한 탭엔 my_request(결과). 서버가 탭(gsid)별로 골라 준다
type OwnerRequest = { id: string; by: string; sheet: string | null; doc: string | null; left: number };
type MyRequest = { id: string; status: "waiting" | "running" | "approved" | "rejected" | "timeout" | "failed" | "canceled"; detail: string; left: number };
type Current = {
  active: boolean; owner?: string | null; mine?: boolean; keep_default?: boolean;
  sheet?: { id: string; title: string }; doc?: { id: string; title: string };
  request?: OwnerRequest; my_request?: MyRequest;
};
type SwitchRes = { ok: boolean; pending?: boolean; owner_absent?: boolean; owner?: string | null };
const POLL_MS = 2000;
type Pick = null | "new" | { id: string; name: string }; // null = 안 고름 (내 문서면 그대로, 아니면 새로)

const LABEL: Record<Kind, string> = { sheet: "📊 보드 (Google Sheet)", doc: "📝 노트 (Google Doc)" };

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const w = window as any;

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(path, init);
  const body = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(body.detail ?? `오류 ${r.status}`);
  return body as T;
}

const GSID_KEY = "lostai.google.gsid";
function getGsid(): string {
  try { return sessionStorage.getItem(GSID_KEY) ?? ""; } catch { return ""; }
}
function setGsid(v: string) {
  try { if (v) sessionStorage.setItem(GSID_KEY, v); else sessionStorage.removeItem(GSID_KEY); } catch { /* 저장 못 하면 다음에 다시 로그인 */ }
}
export const qs = (token: string) => `?token=${encodeURIComponent(token)}&gsid=${encodeURIComponent(getGsid())}`;

const scripts: Record<string, Promise<void>> = {};
function loadScript(src: string): Promise<void> {
  scripts[src] ??= new Promise((ok, fail) => {
    const s = document.createElement("script");
    s.src = src; s.async = true;
    s.onload = () => ok();
    s.onerror = () => { delete scripts[src]; fail(new Error("Google 스크립트를 못 불러왔어요 (인터넷 연결 확인)")); };
    document.head.appendChild(s);
  });
  return scripts[src];
}

/** Google 로그인 팝업 → code. 서버가 토큰으로 바꾼다 (client secret은 서버에만). */
async function googleCode(cfg: Config): Promise<string> {
  await loadScript("https://accounts.google.com/gsi/client");
  return new Promise((ok, fail) => {
    const client = w.google.accounts.oauth2.initCodeClient({
      client_id: cfg.client_id, scope: cfg.scope, ux_mode: "popup",
      callback: (r: { code?: string; error?: string }) => (r.code ? ok(r.code) : fail(new Error(`Google 로그인 실패 (${r.error ?? "알 수 없음"})`))),
      error_callback: (e: { type?: string }) => fail(new Error(e.type === "popup_closed" ? "로그인 창이 닫혔어요" : "로그인 창을 못 열었어요 (팝업 차단 확인)")),
    });
    client.requestCode();
  });
}

/** Google Picker: 내 Drive(나와 공유된 문서 포함)에서 하나 고르기. 취소하면 null. */
async function pickFromDrive(cfg: Config, token: string, kind: Kind): Promise<{ id: string; name: string } | null> {
  await loadScript("https://apis.google.com/js/api.js");
  await new Promise<void>((ok) => w.gapi.load("picker", () => ok()));
  const { access_token } = await api<{ access_token: string }>(`/api/google/access${qs(token)}`);
  const P = w.google.picker;
  const view = new P.DocsView(kind === "sheet" ? P.ViewId.SPREADSHEETS : P.ViewId.DOCUMENTS).setMode(P.DocsViewMode.LIST);
  return new Promise((ok) => {
    new P.PickerBuilder()
      .addView(view)
      .setOAuthToken(access_token)
      .setDeveloperKey(cfg.api_key)
      .setAppId(cfg.app_id) // drive.file: 고른 파일을 이 앱이 열 수 있게
      .setOrigin(window.location.origin)
      .setTitle(kind === "sheet" ? "회의 보드로 쓸 Google Sheet" : "회의 노트로 쓸 Google Doc")
      .setCallback((d: { action: string; docs?: { id: string; name: string }[] }) => {
        if (d.action === P.Action.PICKED && d.docs?.[0]) ok({ id: d.docs[0].id, name: d.docs[0].name });
        else if (d.action === P.Action.CANCEL) ok(null);
      })
      .build()
      .setVisible(true);
  });
}

function Column({ kind, current, mine, pick, setPick, onPickDrive }: {
  kind: Kind; current?: { id: string; title: string }; mine: boolean; pick: Pick; setPick: (p: Pick) => void; onPickDrive: () => void;
}) {
  const picked = pick !== null && pick !== "new" ? pick : null;
  return (
    <section className="dp-col">
      <h3>{LABEL[kind]}</h3>
      <ul className="dp-list" role="listbox">
        <li className={pick === null ? "on" : ""} onClick={() => setPick(null)} role="option" aria-selected={pick === null}>
          {mine
            ? <><b>지금 그대로</b> <span className="dp-sub">{current?.title}</span></>
            : <><b>안 고름</b> <span className="dp-sub">내 Drive에 새로 만들어요</span></>}
        </li>
        <li className={pick === "new" ? "on" : ""} onClick={() => setPick("new")} role="option" aria-selected={pick === "new"}>
          <b>＋ 새로 만들기</b> <span className="dp-sub">{kind === "sheet" ? "작업·담당·기간·상태 열" : "목표·메모·리스크 섹션"}</span>
        </li>
        <li className={picked ? "on" : ""} onClick={onPickDrive} role="option" aria-selected={!!picked}>
          <b>📂 내 Drive에서 고르기</b>
          <span className="dp-sub">{picked ? picked.name : "Google 창이 열려요"}</span>
        </li>
      </ul>
    </section>
  );
}

export function DocPicker({ onSwitched }: { onSwitched?: () => void }) {
  const [open, setOpen] = useState(false);
  const [cfg, setCfg] = useState<Config | null>(null);
  const [cur, setCur] = useState<Current | null>(null);
  const [sheet, setSheet] = useState<Pick>(null);
  const [doc, setDoc] = useState<Pick>(null);
  const [title, setTitle] = useState("");
  const [busy, setBusy] = useState(false);
  const [picking, setPicking] = useState(false); // Google Picker가 떠 있는 동안 내 창은 숨긴다 (겹침 방지)
  const [err, setErr] = useState("");
  const [ownerReq, setOwnerReq] = useState<OwnerRequest | null>(null);
  const [myReq, setMyReq] = useState<MyRequest | null>(null);
  const [answering, setAnswering] = useState(false);
  const [answerErr, setAnswerErr] = useState("");
  const [dismissed, setDismissed] = useState<string | null>(null); // 닫은 결과 카드 (같은 요청 결과를 다시 안 띄움)
  const [keep, setKeep] = useState(true); // 지금 문서에 회의 결과를 남기나 (창을 열 때 서버 기본값으로)
  const token = getToken();

  // 로그인한 탭만 2초마다: 내 문서에 걸린 요청 / 내가 보낸 요청 결과 (Google 호출 없음, 서버 메모리만 읽음)
  useEffect(() => {
    if (!token) return;
    let stop = false;
    const tick = () => {
      if (!getGsid()) { setOwnerReq(null); setMyReq(null); return; }
      api<Current>(`/api/google/source${qs(token)}`)
        .then((s) => { if (!stop) { setOwnerReq(s.request ?? null); setMyReq(s.my_request ?? null); } })
        .catch(() => { /* 다음 번에 다시 */ });
    };
    tick();
    const id = setInterval(tick, POLL_MS);
    return () => { stop = true; clearInterval(id); };
  }, [token]);

  useEffect(() => {
    if (myReq?.status === "approved" && myReq.id !== dismissed) onSwitched?.();
  }, [myReq?.status, myReq?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  const reload = useCallback(() => {
    if (!token) return;
    const q = qs(token);
    Promise.all([api<Config>(`/api/google/config${q}`), api<Current>(`/api/google/source${q}`)])
      .then(([c, s]) => { if (!c.me) setGsid(""); setCfg(c); setCur(s); setKeep(!!s.keep_default); }) // 서버 재시작 등으로 열쇠가 무효면 지운다
      .catch((e) => setErr(e.message));
  }, [token]);

  useEffect(() => {
    if (!open) return;
    setSheet(null); setDoc(null); setErr("");
    reload();
  }, [open, reload]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape" && !busy && !picking) setOpen(false); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, busy, picking]);

  if (!token) return null; // fixture 재생 모드
  const me = cfg?.me ?? null;
  const mine = !!cur?.mine;
  const ready = !!me && (sheet !== null || doc !== null);
  const makesNew = sheet === "new" || doc === "new" || (!mine && (sheet === null || doc === null));

  const login = async () => {
    if (!cfg) return;
    setErr(""); setBusy(true);
    try {
      const code = await googleCode(cfg);
      const r = await api<{ gsid: string }>("/api/google/login", {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ token, code, prev_gsid: getGsid() }),
      });
      setGsid(r.gsid);
      reload();
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  };

  const logout = async () => {
    await api("/api/google/logout", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ token, gsid: getGsid() }) }).catch(() => {});
    setGsid("");
    setSheet(null); setDoc(null);
    reload();
  };

  const pickDrive = (kind: Kind) => async () => {
    if (!cfg || !me) return;
    setErr(""); setPicking(true);
    try {
      const f = await pickFromDrive(cfg, token, kind);
      if (f) (kind === "sheet" ? setSheet : setDoc)(f);
    } catch (e: any) {
      setErr(e.message);
      if (/로그인/.test(e.message)) reload();
    } finally {
      setPicking(false);
    }
  };

  const submit = async () => {
    setBusy(true); setErr("");
    const id = (p: Pick) => (p === null || p === "new" ? p : p.id);
    const name = (p: Pick) => (p !== null && p !== "new" ? p.name : "");
    const send = (force: boolean) => api<SwitchRes>("/api/google/source", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ token, gsid: getGsid(), sheet: id(sheet), doc: id(doc), title,
                             sheet_name: name(sheet), doc_name: name(doc), force, keep }),
    });
    try {
      let r = await send(false);
      if (r.owner_absent) {
        if (!confirm(`문서 주인(${r.owner ?? "알 수 없음"})이 회의에 없어요. 승인 없이 바꿀까요?\n주인 문서는 ${keep ? "회의 결과를 남긴 채로 둬요" : "회의 전 상태로 돌아가요"}.`)) return;
        r = await send(true);
      }
      setOpen(false);
      if (r.pending) { // 주인 화면에 승인 카드가 뜬다. 결과는 아래 카드로
        setMyReq({ id: "", status: "waiting", detail: "", left: 30 });
        return;
      }
      onSwitched?.();
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  };

  const answer = async (approve: boolean, keepMine?: boolean) => {
    if (!ownerReq) return;
    setAnswering(true); setAnswerErr("");
    try {
      await api("/api/google/source/answer", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token, gsid: getGsid(), request_id: ownerReq.id, approve, keep: keepMine ?? null }),
      });
      setOwnerReq(null);
    } catch (e: any) {
      setAnswerErr(e.message);
    } finally {
      setAnswering(false);
    }
  };

  const askOwner = !!cur?.active && !!cur.owner && !mine; // 남의 문서 → 바꾸기 = 주인에게 요청
  const RESULT: Record<string, string> = { approved: "✅", rejected: "❌", timeout: "⌛", failed: "⚠", canceled: "ℹ" };
  const showMine = myReq && myReq.id !== dismissed;

  return (
    <>
      <button className="btn" onClick={() => setOpen(true)} title="회의 문서 고르기 / 새로 만들기">📂 문서 바꾸기</button>
      {(ownerReq || showMine) && createPortal(
        <div className="dp-toasts">
          {ownerReq && (
            <div className="dp-toast" role="alertdialog" aria-label="문서 바꾸기 요청">
              <p><b>🔔 {ownerReq.by}</b>님이 회의 문서를 바꾸려고 해요 <span className="dp-sub">{ownerReq.left}초</span></p>
              <ul>
                {ownerReq.sheet && <li>📊 보드 → {ownerReq.sheet}</li>}
                {ownerReq.doc && <li>📝 노트 → {ownerReq.doc}</li>}
                {(!ownerReq.sheet || !ownerReq.doc) && <li className="dp-muted">안 고른 쪽은 {ownerReq.by}님 Drive에 새로 만들어요</li>}
              </ul>
              <p className="dp-warn">승인하면 회의 내용(타임라인)이 비워져요. 내 문서에 이번 회의 결과를 <b>남길지</b>, 회의 전으로 <b>되돌릴지</b> 골라 주세요. 답이 없으면 자동으로 거절돼요.</p>
              {answerErr && <p className="dp-err">{answerErr}</p>}
              <div className="dp-actions">
                <button className="btn" onClick={() => answer(false)} disabled={answering}>거절</button>
                <button className="btn" onClick={() => answer(true, false)} disabled={answering}>승인 · 되돌리기</button>
                <button className="btn primary" onClick={() => answer(true, true)} disabled={answering}>{answering ? "바꾸는 중…" : "승인 · 남기기"}</button>
              </div>
            </div>
          )}
          {showMine && (
            <div className="dp-toast" role="status">
              {myReq.status === "waiting" || myReq.status === "running" ? (
                <p>⏳ 문서 주인의 승인을 기다리는 중이에요{myReq.status === "waiting" && myReq.id ? <span className="dp-sub">{myReq.left}초</span> : null}</p>
              ) : (
                <div className="dp-row">
                  <p>{RESULT[myReq.status]} {myReq.detail}</p>
                  <button className="dp-x" onClick={() => setDismissed(myReq.id)} aria-label="닫기">✕</button>
                </div>
              )}
            </div>
          )}
        </div>,
        document.body,
      )}
      {open && !picking && createPortal( // 창은 body에 바로: 붙인 곳(결정 벽 도구 띠)의 opacity·transform을 물려받지 않게
        <div className="dp-overlay" onClick={() => !busy && setOpen(false)}>
          <div className="dp-modal" role="dialog" aria-modal="true" aria-label="회의 문서 고르기" onClick={(e) => e.stopPropagation()}>
            <header><h2>회의 문서 고르기</h2><button className="dp-x" onClick={() => setOpen(false)} disabled={busy} aria-label="닫기">✕</button></header>
            {cfg === null && !err ? <p className="dp-muted">불러오는 중…</p> : cfg && !cfg.enabled ? (
              <p className="dp-muted">각자 Google 로그인이 아직 설정되지 않았어요. 서버 관리자: <code>server/sync/GOOGLE_SETUP.md</code> 6절</p>
            ) : (
              <>
                <div className="dp-account">
                  {me ? (
                    <><span>🔐 <b>{me.email}</b> 계정으로 골라요</span><button className="btn" onClick={logout} disabled={busy}>로그아웃</button></>
                  ) : (
                    <><span>내 Google 계정으로 로그인하면 <b>내 Drive 파일만</b> 보여요. 이 앱은 내가 고른 파일과 새로 만든 파일만 열 수 있어요.</span>
                      <button className="btn primary" onClick={login} disabled={busy || !cfg}>Google로 로그인</button></>
                  )}
                </div>
                {cur?.active && (
                  <p className="dp-muted">지금 회의 문서: {cur.sheet?.title} · {cur.doc?.title} ({mine ? "내 계정" : cur.owner ?? "서버 계정"})</p>
                )}
                {me && (
                  <div className="dp-cols">
                    <Column kind="sheet" current={cur?.sheet} mine={mine} pick={sheet} setPick={setSheet} onPickDrive={pickDrive("sheet")} />
                    <Column kind="doc" current={cur?.doc} mine={mine} pick={doc} setPick={setDoc} onPickDrive={pickDrive("doc")} />
                  </div>
                )}
                {me && makesNew && (
                  <label className="dp-title">새 문서 이름
                    <input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="예: 스프린트 25 계획" />
                  </label>
                )}
              </>
            )}
            <footer>
              {askOwner && <p className="dp-warn">🔐 지금 문서는 {cur?.owner} 것이라 주인 승인이 필요해요 (30초 안에 답이 없으면 자동 거절). 주인이 회의를 나갔으면 승인 없이 바꿀지 한 번 더 물어봐요.</p>}
              <p className="dp-warn">⚠ 바꾸면 지금 회의 내용(타임라인·변경)이 비워지고, 모든 참석자 화면이 같이 바뀌어요. 회의 중 문서 수정은 고른 사람의 Google 계정으로 돼요.</p>
              {cur?.active && me && (
                <KeepChoice keep={keep} setKeep={setKeep} disabled={busy}
                  label={askOwner ? "주인이 회의에 없을 때 지금 문서는 (주인이 있으면 주인이 정해요)" : "지금 문서에 이번 회의 결과를"} />
              )}
              {err && <p className="dp-err">{err}</p>}
              <div className="dp-actions">
                <button className="btn" onClick={() => setOpen(false)} disabled={busy}>취소</button>
                <button className="btn primary" onClick={submit} disabled={!ready || busy}>
                  {busy && me ? (askOwner ? "요청 보내는 중…" : "문서 바꾸는 중…") : askOwner ? "주인에게 바꾸기 요청" : "이 문서로 회의 시작"}
                </button>
              </div>
            </footer>
          </div>
        </div>,
        document.body,
      )}
    </>
  );
}

/** 지금 문서에 회의 결과를 남기기 / 되돌리기 (문서 바꾸기 창, 새 회의 확인창이 같이 쓴다). */
export function KeepChoice({ keep, setKeep, label, disabled }: { keep: boolean; setKeep: (v: boolean) => void; label: string; disabled?: boolean }) {
  return (
    <fieldset className="dp-keep" disabled={disabled}>
      <legend>{label}</legend>
      <label><input type="radio" checked={keep} onChange={() => setKeep(true)} /> 남기기 <span className="dp-muted">(결정·액션·바뀐 칸 그대로)</span></label>
      <label><input type="radio" checked={!keep} onChange={() => setKeep(false)} /> 되돌리기 <span className="dp-muted">(회의 전 상태로)</span></label>
    </fieldset>
  );
}
