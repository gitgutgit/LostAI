// 데모 자동 재생 (임시, 테스트와 시연용). 지금 시드의 대본을 서버가 사람이 말하듯 한 줄씩 넣는다 (server/demo.py).
// 재생을 누르면 회의가 처음 상태로 돌아간 뒤 시작한다. 대본이 없는 시드면 숨긴다.
// author: ProfessionalSeaweedDevourer
import { useEffect, useState } from "react";

type Status = { seed: string; lines: number; running: boolean; pos: number; speed: number };

/** refreshKey가 바뀌면(테스트 대본 전환) 상태를 다시 받는다. 재생 중에는 1초마다 진행을 받는다. */
export function DemoPlayer({ refreshKey = "" }: { refreshKey?: string }) {
  const [st, setSt] = useState<Status | null>(null);
  const [speed, setSpeed] = useState(1);
  const [err, setErr] = useState("");

  const load = () => fetch("/api/demo").then((r) => (r.ok ? r.json() : null)).then(setSt).catch(() => setSt(null));
  useEffect(() => { load(); }, [refreshKey]);
  useEffect(() => {
    if (!st?.running) return;
    const t = setInterval(load, 1000);
    return () => clearInterval(t);
  }, [st?.running]);

  if (!st || !st.lines) return null;

  const call = async (path: string, body?: object) => {
    setErr("");
    try {
      const r = await fetch(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body ?? {}) });
      if (!r.ok) throw new Error(`${r.status}`);
    } catch (e) {
      setErr(`실패 (${(e as Error).message})`);
    }
    load();
  };
  const play = () => {
    if (confirm(`'${st.seed}' 대본 ${st.lines}줄을 처음부터 자동 재생합니다. 지금 회의 내용은 지워집니다. 시작할까요?`)) {
      call("/api/demo/start", { speed });
    }
  };

  return (
    <span className="demo-player" title="테스트용: 지금 대본의 대사를 서버가 자동으로 말합니다">
      {st.running
        ? <button onClick={() => call("/api/demo/stop")}>■ 재생 멈춤 <b>{st.pos}/{st.lines}</b></button>
        : <button onClick={play}>▶ 대본 자동 재생 ({st.lines}줄)</button>}
      {!st.running && (
        <select value={speed} onChange={(e) => setSpeed(Number(e.target.value))} aria-label="재생 속도">
          {[1, 2, 4].map((s) => <option key={s} value={s}>{s}배속</option>)}
        </select>
      )}
      {err && <span className="seed-picker-err">{err}</span>}
    </span>
  );
}
