import { send } from "../core/ws";
import type { Change } from "../core/types";

export function ChangeCard({ ch }: { ch: Change }) {
  const live = ch.status === "applied" || ch.status === "proposed";
  return (
    <div className={`change ${ch.status}`}>
      <div className="ops">{ch.ops.map((o) => o.op).join(", ")} <span className="status">{ch.status}</span></div>
      {ch.error && <div className="err">{ch.error}</div>}
      <div className="meta">
        {ch.requested_by}
        {Object.keys(ch.latency_ms).length > 0 && <> · {Object.entries(ch.latency_ms).map(([k, v]) => `${k} ${v}ms`).join(" / ")}</>}
      </div>
      {live && (
        <div className="actions">
          <button onClick={() => send({ kind: "change.approve", payload: { change_id: ch.change_id } })}>👍 승인</button>
          <button onClick={() => send({ kind: "change.revert", payload: { change_id: ch.change_id } })}>↩ 되돌리기</button>
        </div>
      )}
    </div>
  );
}
