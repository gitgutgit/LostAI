// 확대·축소·포인터·머물기 클릭 — 내 화면만. 이벤트 로그에 남기지 않는다.
// 확대 대상은 화면 전체가 아니라 문서 영역(B: 캔버스) 하나.
export const MIN_SCALE = 1;
export const MAX_SCALE = 2.0; // hs: PoC 기준 최대 2배
export const ZOOM_SMOOTH = 0.06; // hs: 확대 스무딩 계수 (PoC 검증값)
export const DWELL_CLICK_MS = 1000;

export class Viewport {
  scale = 1;
  private targetScale = 1; // hs: 스무딩용 목표 배율
  origin = { x: 0.5, y: 0.5 };
  private dwellStart = 0;
  private dwellAt = { x: 0, y: 0 };
  private cursorEl: HTMLElement | null = null; // hs: 포인터 커서 DOM

  constructor(private el: () => HTMLElement | null) {
    this.initCursor(); // hs: 포인터 커서 생성
  }

  // hs: 검지 추적용 초록 커서 원 (PoC pa_hs_gesture_api 스타일)
  private initCursor() {
    if (typeof document === "undefined") return;
    const c = document.createElement("div");
    c.id = "gesture-pointer";
    c.style.cssText = `position:fixed;width:20px;height:20px;border:2px solid #4ade80;border-radius:50%;
      transform:translate(-50%,-50%);pointer-events:none;z-index:9999;display:none;
      box-shadow:0 0 12px rgba(74,222,128,0.4);transition:border-color 0.15s;`;
    document.body.appendChild(c);
    this.cursorEl = c;
  }

  // hs: 커서 표시/숨기기
  showCursor(visible: boolean) {
    if (this.cursorEl) this.cursorEl.style.display = visible ? "block" : "none";
  }

  // hs: 검지 위치 → 커서 이동 (항상 호출, PoC의 smoothPointer 방식)
  moveCursor(p: { x: number; y: number }) {
    if (this.cursorEl) {
      this.cursorEl.style.left = `${p.x * innerWidth}px`;
      this.cursorEl.style.top = `${p.y * innerHeight}px`;
    }
  }

  /** openness 0..1 → 배율. hs: 스무딩 적용 (PoC 0.06 계수) */
  setOpenness(o: number) {
    this.targetScale = MIN_SCALE + (MAX_SCALE - MIN_SCALE) * o;
    this.scale += ZOOM_SMOOTH * (this.targetScale - this.scale); // hs: 부드러운 확대
    this.render();
  }

  // hs: Open_Palm → 최대 확대 (PoC의 palm 모드)
  snapMax() {
    this.targetScale = MAX_SCALE;
    this.scale += 0.25 * (this.targetScale - this.scale); // hs: 빠른 스냅
    this.render();
  }

  // hs: Closed_Fist → 최소(원래 크기) (PoC의 fist 모드)
  snapMin() {
    this.targetScale = MIN_SCALE;
    this.scale += 0.25 * (this.targetScale - this.scale); // hs: 빠른 스냅
    this.render();
  }

  resetScale() { // 주먹 = 100% 복귀
    this.scale = 1;
    this.targetScale = 1; // hs: 목표도 리셋
    this.render();
  }

  /** pointer: 화면 정규화 좌표 0..1. 줌 기준점 + 머물기 클릭. */
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
