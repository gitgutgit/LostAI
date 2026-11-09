// WebSocket 클라이언트. 끊기면 다시 붙고, 다시 붙으면 서버가 스냅샷을 보낸다.
import { dispatch } from "./store";
import type { ClientMessage, ServerMessage } from "./types";

let socket: WebSocket | null = null;
let currentToken: string | null = null;
let leaving = false;

/** 입장 토큰 (REST 호출용, 예: /api/links). */
export function getToken(): string | null {
  return currentToken;
}

export function connect(token: string) {
  currentToken = token;
  leaving = false;
  const proto = location.protocol === "https:" ? "wss" : "ws";
  socket = new WebSocket(`${proto}://${location.host}/ws?token=${encodeURIComponent(token)}`);
  socket.onmessage = (e) => dispatch(JSON.parse(e.data) as ServerMessage);
  socket.onclose = (e) => {
    if (e.code === 4401 || leaving) return; // 토큰 거부, 또는 회의 나가기
    setTimeout(() => { if (!leaving) connect(token); }, 1000); // 서버 재배포 중이면 다시 붙을 때까지 1초마다
  };
}

/** 회의 나가기 (gitgutgit 11-09): 다시 붙지 않게 막고 접속을 닫는다. 서버는 이 이름의 마지막 탭이면 participant.left. */
export function leave() {
  leaving = true;
  currentToken = null;
  socket?.close(1000, "leave");
  socket = null;
}

/** 보냈으면 true. 연결이 끊긴 동안에는 버리고 false (화면에서 안내). */
export function send(msg: ClientMessage): boolean {
  if (socket?.readyState !== WebSocket.OPEN) return false;
  socket.send(JSON.stringify(msg));
  return true;
}
