// 1920x1080 무대를 창 전체에 맞춰 키운다(남는 띠는 벽색이라 경계가 보이지 않는다). 입장 화면과 실화면이 같이 쓴다.
// overlay는 축소되지 않는 창 기준 층(회의록 전문, 알림).
// author: ProfessionalSeaweedDevourer
import { useEffect, useState, type ReactNode } from "react";
import "./wall.css";

export function useFit(): number {
  const calc = () => Math.min(window.innerWidth / 1920, window.innerHeight / 1080);
  const [s, setS] = useState(calc);
  useEffect(() => {
    const on = () => setS(calc());
    window.addEventListener("resize", on);
    return () => window.removeEventListener("resize", on);
  }, []);
  return s;
}

export function FitStage({ children, overlay }: { children: ReactNode; overlay?: ReactNode }) {
  const fit = useFit();
  useEffect(() => {
    document.documentElement.classList.add("livewall");
    return () => document.documentElement.classList.remove("livewall");
  }, []);
  return (
    <div id="livewrap">
      <div style={{ position: "absolute", left: (window.innerWidth - 1920 * fit) / 2, top: (window.innerHeight - 1080 * fit) / 2, width: 1920, height: 1080, transform: `scale(${fit})`, transformOrigin: "0 0" }}>
        {children}
      </div>
      {overlay}
    </div>
  );
}
