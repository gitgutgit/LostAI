import type { RoomView } from "../core/reducer";

export function AgentStatus({ v }: { v: RoomView }) {
  const last = [...v.events].reverse().find((e) => e.type === "agent.progress");
  const sync = [...v.events].reverse().find((e) => e.type.startsWith("sync."));
  return (
    <div className="agent-status">
      <span className={v.connected ? "dot on" : "dot"} /> {v.paused ? "일시정지" : last?.payload.stage ?? "대기"}
      {sync && <span className={`chip ${sync.type === "sync.ok" ? "ok" : "fail"}`}>{sync.payload.target} {sync.type === "sync.ok" ? "✓" : "✗"}</span>}
    </div>
  );
}
