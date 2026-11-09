// Prints the static MOAI status-light markup for each state as JSON, from the same component the app renders.
// Used to put the identical SVG into the render v0.4 design source (web/design/render_v04), so the wall pixel
// judge compares like with like. Run from web/:
//   node_modules/.bin/esbuild scripts/moai_markup.tsx --bundle --platform=node --format=cjs --jsx=automatic --loader:.css=empty --outfile=/tmp/m.cjs && node /tmp/m.cjs
import { renderToStaticMarkup } from "react-dom/server";
import { MoaiStatic } from "../src/views/brand/Moai";
import type { MoaiState } from "../src/views/brand/moaiState";

const states: MoaiState[] = ["listening", "writing", "paused", "vote", "decided"];
const out: Record<string, string> = {};
for (const s of states) out[s] = renderToStaticMarkup(<MoaiStatic state={s} word={false} />);
console.log(JSON.stringify(out, null, 1));
