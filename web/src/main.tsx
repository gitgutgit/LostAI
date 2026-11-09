import React from "react";
import ReactDOM from "react-dom/client";

// ?view=wall 이면 결정 벽(렌더 v0.4) 화면. 그 화면은 시안 CSS를 원문 그대로 쓰므로 공용 styles.css를 싣지 않는다.
const root = ReactDOM.createRoot(document.getElementById("root")!);
const view = new URLSearchParams(location.search).get("view");

if (view === "wall") {
  import("./views/wall/WallView").then(({ WallView }) => root.render(<React.StrictMode><WallView /></React.StrictMode>));
} else {
  Promise.all([import("./App"), import("./styles.css")]).then(([{ App }]) => root.render(<React.StrictMode><App /></React.StrictMode>));
}
