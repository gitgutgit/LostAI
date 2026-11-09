import type { RoomView } from "../core/reducer";

const STAGE_TEXT: Record<string, string> = {
  routing: "듣는 중", editing: "고치는 중", asking: "답 찾는 중", done: "대기", failed: "실패",
};

export function AgentStatus({ v }: { v: RoomView }) {
  // 서버는 묻기와 수정 뒤에 done 단계를 따로 내지 않는다. 답이나 변경 결과가 더 늦게 왔으면 끝난 것으로 본다.
  const last = [...v.events].reverse().find((e) =>
    e.type === "agent.progress" || e.type === "ask.answered" || (e.type.startsWith("change.") && e.type !== "change.proposed"));
  const sync = [...v.events].reverse().find((e) => e.type.startsWith("sync."));
  const stage = last?.type === "agent.progress" ? (last.payload.stage as string) : "done";
  const busy = stage === "routing" || stage === "editing" || stage === "asking";
  return (
    <div className={`agent-status ${busy ? "busy" : ""}`}>
      <span className={v.connected ? "dot on" : "dot"} />
      {v.paused ? "일시정지" : STAGE_TEXT[stage ?? "done"] ?? stage}
      {sync && <span className={`chip ${sync.type === "sync.ok" ? "ok" : "fail"}`}>{sync.payload.target} {sync.type === "sync.ok" ? "✓" : "✗"}</span>}
    </div>
  );
}
