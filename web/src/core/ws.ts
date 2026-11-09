// WebSocket 클라이언트. 끊기면 다시 붙고, 다시 붙으면 서버가 스냅샷을 보낸다.
import { dispatch } from "./store";
import type { ClientMessage, ServerMessage } from "./types";

let socket: WebSocket | null = null;

export function connect(token: string) {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  socket = new WebSocket(`${proto}://${location.host}/ws?token=${encodeURIComponent(token)}`);
  socket.onmessage = (e) => dispatch(JSON.parse(e.data) as ServerMessage);
  socket.onclose = (e) => {
    if (e.code === 4401) return; // 토큰 거부
    setTimeout(() => connect(token), 1000);
  };
}

export function send(msg: ClientMessage) {
  if (socket?.readyState === WebSocket.OPEN) socket.send(JSON.stringify(msg));
}
