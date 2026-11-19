// 회의 문서 고르기·새로 만들기: 서버 Google 계정의 Sheet(보드) / Doc(노트)을 골라 회의 원본으로. author: Mal-Mi-Jal
// 서버: server/sync/source_api.py. 바꾸면 지금 회의 내용은 비워지고 지금 문서는 회의 전 상태로 돌아간다.
// 어느 화면에든 <DocPicker /> 한 줄로 붙일 수 있다 (버튼 + 창).
import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { getToken } from "../core/ws";
import "./DocPicker.css";

type Kind = "sheet" | "doc";
type GFile = { id: string; name: string; modified?: string; mine?: boolean };
type Current = { active: boolean; sheet?: { id: string; title: string }; doc?: { id: string; title: string } };
type Pick = null | "new" | string; // null = 지금 그대로

const LABEL: Record<Kind, string> = { sheet: "📊 보드 (Google Sheet)", doc: "📝 노트 (Google Doc)" };

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(path, init);
  const body = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(body.detail ?? `오류 ${r.status}`);
  return body as T;
}

function when(iso?: string) {
  if (!iso) return "";
  const d = new Date(iso);
  return `${d.getMonth() + 1}/${d.getDate()} ${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
}

function Column({ kind, current, pick, setPick, mustPick }: {
  kind: Kind; current?: { id: string; title: string }; pick: Pick; setPick: (p: Pick) => void; mustPick: boolean;
}) {
  const [q, setQ] = useState("");
  const [files, setFiles] = useState<GFile[] | null>(null);
  const [err, setErr] = useState("");

  useEffect(() => {
    const token = getToken();
    if (!token) return;
    const t = window.setTimeout(() => {
      setErr("");
      api<{ files: GFile[] }>(`/api/google/files?token=${encodeURIComponent(token)}&kind=${kind}&q=${encodeURIComponent(q)}`)
        .then((r) => setFiles(r.files)).catch((e) => { setFiles([]); setErr(e.message); });
    }, q ? 300 : 0); // 검색은 입력이 멈춘 뒤
    return () => window.clearTimeout(t);
  }, [kind, q]);

  return (
    <section className="dp-col">
      <h3>{LABEL[kind]}</h3>
      <input className="dp-search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="이름으로 찾기" aria-label={`${LABEL[kind]} 찾기`} />
      <ul className="dp-list" role="listbox">
        {!mustPick && (
          <li className={pick === null ? "on" : ""} onClick={() => setPick(null)} role="option" aria-selected={pick === null}>
            <b>지금 그대로</b> <span className="dp-sub">{current?.title}</span>
          </li>
        )}
        <li className={pick === "new" ? "on" : ""} onClick={() => setPick("new")} role="option" aria-selected={pick === "new"}>
          <b>＋ 새로 만들기</b> <span className="dp-sub">{kind === "sheet" ? "작업·담당·기간·상태 열" : "목표·메모·리스크 섹션"}</span>
        </li>
        {files === null && <li className="dp-muted">불러오는 중…</li>}
        {err && <li className="dp-err">{err}</li>}
        {files?.map((f) => (
          <li key={f.id} className={pick === f.id ? "on" : ""} onClick={() => setPick(f.id === current?.id ? null : f.id)}
              role="option" aria-selected={pick === f.id}>
            {f.name}
            {f.id === current?.id && <span className="dp-tag">지금</span>}
            {!f.mine && <span className="dp-tag soft">공유받음</span>}
            <span className="dp-sub">{when(f.modified)}</span>
          </li>
        ))}
        {files?.length === 0 && !err && <li className="dp-muted">문서가 없어요</li>}
      </ul>
    </section>
  );
}

export function DocPicker({ onSwitched }: { onSwitched?: () => void }) {
  const [open, setOpen] = useState(false);
  const [cur, setCur] = useState<Current | null>(null);
  const [sheet, setSheet] = useState<Pick>(null);
  const [doc, setDoc] = useState<Pick>(null);
  const [title, setTitle] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const token = getToken();

  useEffect(() => {
    if (!open || !token) return;
    setSheet(null); setDoc(null); setErr("");
    api<Current>(`/api/google/source?token=${encodeURIComponent(token)}`).then(setCur).catch((e) => setErr(e.message));
  }, [open, token]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape" && !busy) setOpen(false); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, busy]);

  if (!token) return null; // fixture 재생 모드
  const mustPick = cur ? !cur.active : false; // 원본이 아직 없으면 둘 다 골라야 한다
  const ready = mustPick ? sheet !== null && doc !== null : sheet !== null || doc !== null;

  const submit = async () => {
    setBusy(true); setErr("");
    try {
      await api("/api/google/source", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token, sheet, doc, title }),
      });
      setOpen(false);
      onSwitched?.();
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <button className="btn" onClick={() => setOpen(true)} title="회의 문서 고르기 / 새로 만들기">📂 문서 바꾸기</button>
      {open && createPortal( // 창은 body에 바로: 붙인 곳(결정 벽 도구 띠)의 opacity·transform을 물려받지 않게
        <div className="dp-overlay" onClick={() => !busy && setOpen(false)}>
          <div className="dp-modal" role="dialog" aria-modal="true" aria-label="회의 문서 고르기" onClick={(e) => e.stopPropagation()}>
            <header><h2>회의 문서 고르기</h2><button className="dp-x" onClick={() => setOpen(false)} disabled={busy} aria-label="닫기">✕</button></header>
            {cur === null && !err ? <p className="dp-muted">불러오는 중…</p> : (
              <div className="dp-cols">
                <Column kind="sheet" current={cur?.sheet} pick={sheet} setPick={setSheet} mustPick={mustPick} />
                <Column kind="doc" current={cur?.doc} pick={doc} setPick={setDoc} mustPick={mustPick} />
              </div>
            )}
            {(sheet === "new" || doc === "new") && (
              <label className="dp-title">새 문서 이름
                <input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="예: 스프린트 25 계획" />
              </label>
            )}
            <footer>
              <p className="dp-warn">⚠ 바꾸면 지금 회의 내용(타임라인·변경)이 비워지고, 지금 문서는 회의 전 상태로 돌아가요. 모든 참석자 화면이 같이 바뀌어요.</p>
              {err && <p className="dp-err">{err}</p>}
              <div className="dp-actions">
                <button className="btn" onClick={() => setOpen(false)} disabled={busy}>취소</button>
                <button className="btn primary" onClick={submit} disabled={!ready || busy}>{busy ? "문서 바꾸는 중…" : "이 문서로 회의 시작"}</button>
              </div>
            </footer>
          </div>
        </div>,
        document.body,
      )}
    </>
  );
}
