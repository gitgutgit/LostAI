import { useCallback, useEffect, useState } from "react";
import { connect } from "./core/ws";
import { playFixture } from "./core/fixtures";
import { JoinView } from "./views/join/JoinView";
import { CanvasView } from "./views/canvas/CanvasView";

// ?fixture=<이름> 이면 백엔드 없이 fixtures 이벤트를 재생한다 (web/public/fixtures/<이름>.jsonl).
const params = new URLSearchParams(location.search);
const fixture = params.get("fixture");

export function App() {
  const [joined, setJoined] = useState(!!fixture);

  useEffect(() => {
    if (!fixture) return;
    fetch("/fixtures/seed_sprint.json").then((r) => r.json()).then((seed) => playFixture(fixture, seed));
  }, []);

  const onJoined = useCallback((_name: string, token: string) => {
    connect(token);
    setJoined(true);
  }, []);

  return joined ? <CanvasView /> : <JoinView onJoined={onJoined} />;
}
