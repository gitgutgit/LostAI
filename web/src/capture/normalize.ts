// STT 받아쓰기 보정: 한국어 STT는 티켓 키를 소리 나는 대로 적는다 ("PAY-423" → "페이사이삼", "회의 사백이십삼").
// 보드에 실제로 있는 키(셀 값의 ABC-123 꼴)와 숫자가 맞을 때만 키로 바꾼다 → 엉뚱한 말을 바꿀 일이 적다.
// LLM을 거치지 않는 순수 문자열 처리 (말 → 화면 지연에 영향 없음). author: Mal-Mi-Jal
import type { DocState } from "../core/types";

const KEY_RE = /\b([A-Z][A-Z0-9]{1,9})-(\d{1,6})\b/g;
const DIGIT: Record<string, number> = { 공: 0, 영: 0, 일: 1, 이: 2, 삼: 3, 사: 4, 오: 5, 육: 6, 륙: 6, 칠: 7, 팔: 8, 구: 9 };
const UNIT: Record<string, number> = { 십: 10, 백: 100, 천: 1000 };
const NUM_CHARS = "공영일이삼사오육륙칠팔구십백천0-9";

/** 보드(시트) 셀 값에서 티켓 키 모으기: 숫자 → 키 목록 */
export function ticketKeys(state: DocState | null | undefined): Map<string, string[]> {
  const out = new Map<string, string[]>();
  if (!state) return out;
  for (const d of Object.values(state.docs)) {
    if (d.kind !== "sheet") continue;
    for (const r of d.rows) for (const v of Object.values(r.cells)) {
      if (typeof v !== "string") continue;
      for (const m of v.matchAll(KEY_RE)) {
        const list = out.get(m[2]) ?? [];
        if (!list.includes(m[0])) list.push(m[0]);
        out.set(m[2], list);
      }
    }
  }
  return out;
}

/** "사이삼"(자리마다) 과 "사백이십삼"(자릿값) 두 읽기를 모두 숫자 문자열로. 못 읽으면 빈 배열. */
export function readKoreanNumber(s: string): string[] {
  const t = s.replace(/\s+/g, "");
  if (!t) return [];
  if (/^[0-9]+$/.test(t)) return [t];
  const out: string[] = [];
  if ([...t].every((c) => c in DIGIT || /[0-9]/.test(c))) out.push([...t].map((c) => (c in DIGIT ? DIGIT[c] : c)).join(""));
  if ([...t].some((c) => c in UNIT) && [...t].every((c) => c in DIGIT || c in UNIT)) {
    let total = 0, cur = 0;
    for (const c of t) {
      if (c in DIGIT) cur = DIGIT[c];
      else { total += (cur || 1) * UNIT[c]; cur = 0; }
    }
    out.push(String(total + cur));
  }
  return out;
}

/**
 * 받아쓰기 → 키 보정. 숫자 덩어리(한글 숫자 2자 이상 또는 아라비아 숫자)가 보드 키 번호와 같고, 그 키가 하나뿐이면
 * 바로 앞에 붙은 접두(라틴 글자, 또는 붙어 있거나 한 칸 떨어진 한글 1~3자)까지 묶어서 키로 바꾼다.
 */
export function normalizeTranscript(text: string, keys: Map<string, string[]>): string {
  if (!keys.size) return text;
  const re = new RegExp(`([A-Za-z]{2,10}|[가-힣]{1,3})?([ -]?)([${NUM_CHARS}]{2,})`, "g");
  return text.replace(re, (whole, prefix: string | undefined, sep: string, num: string) => {
    // 숫자 덩어리 앞부분이 접두로 잘려 들어갔을 수 있다 ("회의사이삼": 접두 '회의사' + '이삼'으로 잡히면 다시 나눠 본다)
    const tries: [string, string][] = [[prefix ?? "", num]];
    if (prefix && /[가-힣]/.test(prefix)) {
      for (let k = 1; k <= prefix.length; k++) tries.push([prefix.slice(0, prefix.length - k), prefix.slice(-k) + num]);
    }
    for (const [pre, n] of tries) {
      for (const val of readKoreanNumber(n)) {
        const hit = keys.get(val);
        if (hit?.length !== 1) continue;
        const key = hit[0];
        // 접두가 다른 라틴 단어(예: "API 423")면 건드리지 않는다
        if (/^[A-Za-z]+$/.test(pre) && pre.toUpperCase() !== key.split("-")[0]) continue;
        // 한글 숫자 덩어리는 접두 없이도 키로 (예: "사이삼 추정"), 아라비아 숫자만 있을 땐 접두가 있어야 키로 본다
        if (!pre && /^[0-9]+$/.test(n)) continue;
        return key;
      }
    }
    return whole;
  });
}
