// 백엔드 없이 화면 개발: fixtures/*.jsonl 이벤트를 시간순으로 재생한다.
// 사용: http://localhost:5173/?fixture=sample_sprint_events  (web/public/fixtures/ 로 복사해 두거나 서버가 서빙)
import { dispatch, resetView } from "./store";
import type { DocState, MeetingEvent } from "./types";

export async function playFixture(name: string, seed: DocState, speed = 1) {
  resetView();
  dispatch({ kind: "snapshot", room_id: "fixture", state: seed, changes: [], events: [], participants: {}, paused: false });
  const text = await (await fetch(`/fixtures/${name}.jsonl`)).text();
  const events = text.split("\n").filter(Boolean).map((l) => JSON.parse(l) as MeetingEvent);
  let last = events[0]?.ts ?? 0;
  for (const ev of events) {
    await new Promise((r) => setTimeout(r, ((ev.ts - last) * 1000) / speed));
    last = ev.ts;
    dispatch({ kind: "event", event: ev });
  }
}
