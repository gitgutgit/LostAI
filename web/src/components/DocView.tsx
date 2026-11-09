import type { Change, Doc } from "../core/types";

export function DocView({ docKey, doc, cellIndex }: { docKey: string; doc: Doc; cellIndex: Record<string, Change> }) {
  return (
    <div className="doc">
      {doc.sections.map((s) => (
        <section key={s.section_id}>
          <h3>{s.heading}{s.binding && <small> · {s.binding}</small>}</h3>
          <ul>
            {s.items.map((it) => {
              const anchor = `${docKey}/${s.section_id}/${it.item_id}`;
              const ch = cellIndex[anchor];
              return (
                <li key={it.item_id} data-anchor={anchor} className={ch ? "hl" : ""}
                    title={ch ? `${ch.requested_by} · ${ch.reason ?? ""}` : undefined}>
                  {it.text}{it.meta?.owner && <em> — {it.meta.owner}</em>}
                </li>
              );
            })}
          </ul>
        </section>
      ))}
    </div>
  );
}
