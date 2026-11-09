// WebSocket 클라이언트. 끊기면 다시 붙고, 다시 붙으면 서버가 스냅샷을 보낸다.
import { dispatch } from "./store";
import type { ClientMessage, ServerMessage } from "./types";

let socket: WebSocket | null = null;
let currentToken: string | null = null;

/** 입장 토큰 (REST 호출용, 예: /api/links). */
export function getToken(): string | null {
  return currentToken;
}

export function connect(token: string) {
  currentToken = token;
  const proto = location.protocol === "https:" ? "wss" : "ws";
  socket = new WebSocket(`${proto}://${location.host}/ws?token=${encodeURIComponent(token)}`);
  socket.onmessage = (e) => dispatch(JSON.parse(e.data) as ServerMessage);
  socket.onclose = (e) => {
    if (e.code === 4401) return; // 토큰 거부
    setTimeout(() => connect(token), 1000);
  };
}

/** 보냈으면 true. 연결이 끊긴 동안에는 버리고 false (화면에서 안내). */
export function send(msg: ClientMessage): boolean {
  if (socket?.readyState !== WebSocket.OPEN) return false;
  socket.send(JSON.stringify(msg));
  return true;
}
