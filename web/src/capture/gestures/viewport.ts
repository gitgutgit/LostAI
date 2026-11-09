// 확대·축소·포인터·머물기 클릭 — 내 화면만. 이벤트 로그에 남기지 않는다.
// 확대 대상은 화면 전체가 아니라 문서 영역(B: 캔버스) 하나.
export const MIN_SCALE = 1;
export const MAX_SCALE = 2.5;
export const DWELL_CLICK_MS = 1000;

export class Viewport {
  scale = 1;
  origin = { x: 0.5, y: 0.5 };
  private dwellStart = 0;
  private dwellAt = { x: 0, y: 0 };

  constructor(private el: () => HTMLElement | null) {}

  /** openness 0..1 → 배율. 확대 모드일 때만 호출된다. */
  setOpenness(o: number) {
    this.scale = MIN_SCALE + (MAX_SCALE - MIN_SCALE) * o;
    this.render();
  }

  resetScale() { // 주먹 = 100% 복귀
    this.scale = 1;
    this.render();
  }

  /** pointer: 화면 정규화 좌표 0..1. 1초 머물면 그 위치 요소를 클릭(칸 팝오버). */
  setPointer(p: { x: number; y: number }, now: number) {
    this.origin = p;
    if (Math.hypot(p.x - this.dwellAt.x, p.y - this.dwellAt.y) > 0.02) {
      this.dwellAt = p;
      this.dwellStart = now;
    } else if (this.dwellStart && now - this.dwellStart > DWELL_CLICK_MS) {
      this.dwellStart = 0;
      const target = document.elementFromPoint(p.x * innerWidth, p.y * innerHeight) as HTMLElement | null;
      target?.click();
    }
    this.render();
  }

  private render() {
    const el = this.el();
    if (!el) return;
    el.style.transformOrigin = `${this.origin.x * 100}% ${this.origin.y * 100}%`;
    el.style.transform = `scale(${this.scale})`;
  }
}
