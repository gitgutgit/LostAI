// 음성 인식 언어 바꾸기 (EN ↔ 한국어). 기본은 영어, 고른 값은 이 브라우저에 저장된다.
// author: gitgutgit
import { useState } from "react";
import { STT_LANGS, defaultLang, setSttLang } from "../capture/stt";

export function LangToggle({ onChange }: { onChange?: (code: string) => void }) {
  const [lang, setLang] = useState(defaultLang());
  const i = STT_LANGS.findIndex((l) => l.code === lang);
  const next = STT_LANGS[(i + 1) % STT_LANGS.length];
  const cur = STT_LANGS[i] ?? { code: lang, label: lang };
  return (
    <button className="btn" title={`음성 인식 언어: ${cur.label}. 누르면 ${next.label}로 바꿔요 (말하는 언어와 같아야 알아들어요)`}
      onClick={() => { setSttLang(next.code); setLang(next.code); onChange?.(next.code); }}>
      🌐 {cur.label}
    </button>
  );
}
