// 실제 Google Sheet / Doc 바로가기 (새 탭). 화면 옆에 띄워 두면 실시간으로 바뀌는 걸 볼 수 있다. author: Mal-Mi-Jal
import { useEffect, useState } from "react";
import { getToken } from "../core/ws";

type Links = { sheet: string | null; doc: string | null; doc_sync: boolean };

export function DocLinks() {
  const [links, setLinks] = useState<Links | null>(null);

  useEffect(() => {
    const token = getToken();
    if (!token) return; // fixture 재생 모드
    fetch(`/api/links?token=${encodeURIComponent(token)}`)
      .then((r) => (r.ok ? r.json() : null))
      .then(setLinks)
      .catch(() => setLinks(null));
  }, []);

  if (!links) return null;
  return (
    <span className="doc-links">
      {links.sheet
        ? <a className="btn" href={links.sheet} target="_blank" rel="noreferrer">📊 Google Sheet ↗</a>
        : <span className="btn off" title="서버 .env에 GOOGLE_SHEET_ID 없음">📊 Sheet 미연결</span>}
      {links.doc
        ? <a className="btn" href={links.doc} target="_blank" rel="noreferrer"
             title={links.doc_sync ? "" : "Docs 동기화 준비 중: 아직 자동으로 안 바뀜"}>
            📝 Google Doc ↗{!links.doc_sync && " (동기화 준비 중)"}
          </a>
        : <span className="btn off" title="Docs 동기화 준비 중 (P1)">📝 Doc 준비 중</span>}
    </span>
  );
}
