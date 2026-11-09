// 테스트 대본 선택 (임시, 테스트용). 고르면 서버가 그 시드로 회의를 처음부터 다시 시작한다 (/api/reset).
// 원본 문서 모드(SEED=google)에서는 서버가 막으므로 숨긴다.
import { useEffect, useState } from "react";

type Seed = { name: string; title: string };
type Seeds = { current: string; seeds: Seed[]; locked: boolean };

export function TestSeedPicker({ onSwitched }: { onSwitched?: () => void }) {
  const [info, setInfo] = useState<Seeds | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  useEffect(() => {
    fetch("/api/seeds")
      .then((r) => (r.ok ? r.json() : null))
      .then(setInfo)
      .catch(() => setInfo(null));
  }, []);

  if (!info || info.locked || info.seeds.length < 2) return null;

  const pick = async (name: string) => {
    if (name === info.current) return;
    if (!confirm(`'${name}' 대본으로 바꾸면 지금 회의 내용이 지워집니다. 바꿀까요?`)) return;
    setBusy(true);
    setErr("");
    try {
      const r = await fetch("/api/reset", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ seed: name }),
      });
      if (!r.ok) throw new Error(`${r.status}`);
      setInfo({ ...info, current: name });
      onSwitched?.();
    } catch (e) {
      setErr(`전환 실패 (${(e as Error).message})`);
    } finally {
      setBusy(false);
    }
  };

  return (
    <label className="seed-picker" title="테스트용: 고르면 회의가 그 대본의 시작 상태로 초기화됩니다">
      🧪 테스트 대본
      <select value={info.current} disabled={busy} onChange={(e) => pick(e.target.value)}>
        {info.seeds.map((s) => (
          <option key={s.name} value={s.name}>{s.name} ({s.title})</option>
        ))}
      </select>
      {err && <span className="seed-picker-err">{err}</span>}
    </label>
  );
}
