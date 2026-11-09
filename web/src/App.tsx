import { useCallback, useEffect, useState } from "react";
import { connect, leave } from "./core/ws";
import { resetView } from "./core/store";
import { playFixture } from "./core/fixtures";
import { JoinView } from "./views/join/JoinView";
import { JoinProbe } from "./views/join/JoinProbe";
import { CanvasView } from "./views/canvas/CanvasView";
import { LiveWallView } from "./views/wall/LiveWallView";

// ?fixture=<이름> 이면 백엔드 없이 fixtures 이벤트를 재생한다 (web/public/fixtures/<이름>.jsonl).
const params = new URLSearchParams(location.search);
const fixture = params.get("fixture");
// 개발 서버의 React.StrictMode는 effect를 두 번 실행한다. 재생이 두 번 겹치지 않게 한 번만 시작한다.
let fixtureStarted = false;
// 입장 뒤 화면: 기본은 결정 벽(렌더 v0.4 설계), ?ui=canvas 면 예전 B 캔버스.
const ui = params.get("ui") === "canvas" ? "canvas" : "wall";
// 개발 서버 전용: ?as=이름 이면 손동작 관문 없이 호스트 수동 입장으로 들어간다(화면 확인, 자동 시험용). 운영 빌드에는 없다.
const devAs = import.meta.env.DEV ? params.get("as") : null;
let devJoinStarted = false;
// 개발 서버 전용: ?joinprobe 면 입장 손동작 측정 화면(손동작별 신뢰도 기록, 서버 호출 없음).
const devProbe = import.meta.env.DEV && params.has("joinprobe");

export function App() {
  const [joined, setJoined] = useState(!!fixture);
  const [me, setMe] = useState<string | undefined>(devAs ?? undefined);

  useEffect(() => {
    if (!fixture || fixtureStarted) return;
    fixtureStarted = true;
    fetch("/fixtures/seed_sprint.json").then((r) => r.json()).then((seed) => playFixture(fixture, seed));
  }, []);

  const onJoined = useCallback((name: string, token: string) => {
    connect(token);
    setMe(name);
    setJoined(true);
  }, []);

  const onLeave = useCallback(() => { // gitgutgit 11-09: 회의 나가기 → 입장 화면으로
    leave();
    resetView();
    setMe(undefined);
    setJoined(false);
  }, []);

  useEffect(() => {
    if (!devAs || fixture || devJoinStarted) return;
    devJoinStarted = true;
    fetch("/api/join/manual", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name: devAs, host: "dev" }) })
      .then((r) => r.json()).then((r) => onJoined(devAs, r.token));
  }, [onJoined]);

  if (devProbe) return <JoinProbe />;
  if (!joined) return <JoinView onJoined={onJoined} />;
  return ui === "canvas" ? <CanvasView /> : <LiveWallView me={me} onLeave={onLeave} />;
}
