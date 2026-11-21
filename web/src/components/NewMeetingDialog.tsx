// 회의 끝 화면의 '🆕 새 회의' 확인창. author: Mal-Mi-Jal
// 서버: POST /api/meeting/new {token, keep} (server/app.py → source_api.back_to_default).
// 원본 문서 모드면 지금 문서에 이번 회의 결과를 남길지 / 회의 전으로 되돌릴지 고른다 (PR3).
// 기본값은 서버가 정한다 (keep_default): 기본 WBS(서버 계정, 팀 시연 문서) = 되돌리기, 각자 문서 = 남기기.
import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { getToken } from "../core/ws";
import { api, KeepChoice, qs } from "./DocPicker";

type Source = { active: boolean; owner?: string | null; doc?: { title: string }; keep_default?: boolean };

export function NewMeetingDialog({ onClose, onDone }: { onClose: () => void; onDone: (msg: string) => void }) {
  const token = getToken() ?? "";
  const [src, setSrc] = useState<Source | null>(null);
  const [keep, setKeep] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  useEffect(() => {
    api<Source>(`/api/google/source${qs(token)}`)
      .then((s) => { setSrc(s); setKeep(!!s.keep_default); })
      .catch(() => setSrc({ active: false })); // 못 물어보면 선택 없이 (서버 기본값)
  }, [token]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape" && !busy) onClose(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [busy, onClose]);

  const start = async () => {
    setBusy(true); setErr("");
    try {
      const body = await api<{ notice?: string }>("/api/meeting/new", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token, keep: src?.active ? keep : null }),
      });
      onDone(body.notice ?? "");
      onClose();
    } catch (e) {
      setErr(`새 회의를 못 열었어요 (${(e as Error).message})`);
    } finally {
      setBusy(false);
    }
  };

  return createPortal(
    <div className="dp-overlay" onClick={() => !busy && onClose()}>
      <div className="dp-modal" role="dialog" aria-modal="true" aria-label="새 회의 시작" onClick={(e) => e.stopPropagation()}>
        <header><h2>🆕 새 회의 시작</h2><button className="dp-x" onClick={onClose} disabled={busy} aria-label="닫기">✕</button></header>
        <p className="dp-warn">지금 회의 내용(타임라인)을 지우고 기본 문서로 새 회의를 시작해요. 참석자 모두의 화면이 새 회의로 바뀌어요.</p>
        {src === null ? <p className="dp-muted">불러오는 중…</p> : src.active && (
          <KeepChoice keep={keep} setKeep={setKeep} disabled={busy}
            label={`지금 문서(${src.doc?.title ?? "회의 문서"} · ${src.owner ?? "서버 계정"})에 이번 회의 결과를`} />
        )}
        {err && <p className="dp-err">{err}</p>}
        <footer>
          <div className="dp-actions">
            <button className="btn" onClick={onClose} disabled={busy}>취소</button>
            <button className="btn primary" onClick={start} disabled={busy || src === null}>{busy ? "새 회의 여는 중…" : "새 회의 시작"}</button>
          </div>
        </footer>
      </div>
    </div>,
    document.body,
  );
}
