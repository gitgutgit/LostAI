// 실제 회의 화면의 장면 전환: 장면 재생기(WallView.tsx)처럼 카드 B 장면이 바뀔 때 View Transition으로 넘긴다.
// 회의 화면은 서버 이벤트가 오는 대로 다시 그리므로, 장면 키가 바뀐 순간에는 직전 화면을 한 번 더 그려 두고
// 전환 안에서 새 화면으로 바꾼다. 문서 칸 갱신처럼 장면 키가 그대로인 변화는 기다리지 않고 바로 그린다.
// author: ProfessionalSeaweedDevourer
import { useEffect, useRef, useState } from "react";
import { flushSync } from "react-dom";

type VT = { skipTransition: () => void };
type DocVT = Document & { startViewTransition?: (cb: () => void) => VT };

/** key가 바뀌면 value를 View Transition 안에서 바꿔 그린다. 전환을 못 쓰는 환경이면 바로 바꾼다. */
export function useSceneTransition<T>(value: T, key: string): T {
  const [shownKey, setShownKey] = useState(key);
  const last = useRef(value);
  if (key === shownKey) last.current = value;

  useEffect(() => {
    if (key === shownKey) return;
    const apply = () => flushSync(() => setShownKey(key));
    const doc = document as DocVT;
    if (!doc.startViewTransition || matchMedia("(prefers-reduced-motion: reduce)").matches) { apply(); return; }
    let done = false;
    const vt = doc.startViewTransition(() => { done = true; apply(); });
    // 프레임이 안 나오는 환경(숨은 탭, 일부 headless)에서는 전환을 건너뛴다 (WallView.tsx와 같은 규칙)
    const t = setTimeout(() => { if (!done) vt.skipTransition(); }, 200);
    return () => clearTimeout(t);
  }, [key, shownKey]);

  return key === shownKey ? value : last.current;
}
