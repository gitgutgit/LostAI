// 1인 시험(개발 서버 전용): 채팅 한 칸으로 회의 전체를 혼자 몬다.
//   'Ines: 텍스트'  → Ines로 수동 입장한 소켓을 열어 그 이름으로 말한다(처음 한 번 입장, 그 뒤 재사용).
//   '/up' '/down'   → 엄지 승인, 되돌림.  '/1'..'/5' → 손가락 표결.  '/t' → T자 멈춤, 재개.
//   'Ines: /2'      → Ines의 손 신호.  접두가 없거나 내 이름이면 내 소켓으로 보낸다.
// 서버 계약은 그대로다: 수동 입장(/api/join/manual)과 같은 utterance.final, gesture 메시지만 쓴다.
// author: ProfessionalSeaweedDevourer
import { send } from "../../core/ws";
import type { ClientMessage, GestureKind } from "../../core/types";

const GEST: Record<string, GestureKind> = {
  up: "Thumb_Up", down: "Thumb_Down", t: "T_Shape",
  "0": "Fingers_0", "1": "Fingers_1", "2": "Fingers_2", "3": "Fingers_3", "4": "Fingers_4", "5": "Fingers_5",
};
const socks = new Map<string, Promise<WebSocket>>();

function puppet(name: string, host: string): Promise<WebSocket> {
  const have = socks.get(name);
  if (have) return have;
  const p = (async () => {
    const r = await fetch("/api/join/manual", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ name, host: host || "tester" }) });
    const { token } = await r.json();
    const proto = location.protocol === "https:" ? "wss" : "ws";
    const ws = new WebSocket(`${proto}://${location.host}/ws?token=${encodeURIComponent(token)}`);
    await new Promise<void>((ok, bad) => { ws.onopen = () => ok(); ws.onerror = () => bad(new Error(`puppet ${name}`)); });
    ws.onclose = () => socks.delete(name);
    return ws;
  })();
  socks.set(name, p);
  p.catch(() => socks.delete(name));
  return p;
}

/** 한 줄을 해석한다. 이름 접두는 공백 없는 1~12자 뒤 콜론. */
export function parseLine(line: string, me: string): { who: string | null; msg: ClientMessage } {
  const m = /^\s*([^\s:/]{1,12}):\s*(.+)$/.exec(line);
  const who = m && m[1] !== me ? m[1] : null;
  const body = (m ? m[2] : line).trim();
  const g = /^\/(up|down|t|[0-5])$/i.exec(body);
  const msg: ClientMessage = g
    ? { kind: "gesture", payload: { kind: GEST[g[1].toLowerCase()], confidence: 1, hold_ms: 1000 } }
    : { kind: "utterance.final", payload: { text: body } };
  return { who, msg };
}

export async function sayAs(line: string, me: string): Promise<void> {
  const { who, msg } = parseLine(line, me);
  if (!who) { send(msg); return; }
  (await puppet(who, me)).send(JSON.stringify(msg));
}
