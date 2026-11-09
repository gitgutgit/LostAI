// 시트 렌더러 + 앵커 하이라이트 + 칸 팝오버(누가 언제 무슨 말 — P1)
import type { Change, Sheet } from "../core/types";

export function SheetView({ docKey, sheet, cellIndex, onCell }: {
  docKey: string; sheet: Sheet; cellIndex: Record<string, Change>; onCell?: (anchor: string, ch?: Change) => void;
}) {
  return (
    <table className="sheet">
      <thead><tr>{sheet.columns.map((c) => <th key={c}>{c}</th>)}</tr></thead>
      <tbody>
        {sheet.rows.map((r) => (
          <tr key={r.row_id} className={cellIndex[`${docKey}/${r.row_id}`] ? "hl" : ""}>
            {sheet.columns.map((c) => {
              const anchor = `${docKey}/${r.row_id}/${c}`;
              const ch = cellIndex[anchor];
              return (
                <td key={c} data-anchor={anchor} className={ch ? "hl" : ""} onClick={() => onCell?.(anchor, ch)}
                    title={ch ? `${ch.requested_by} · ${ch.reason ?? ""}` : undefined}>
                  {String(r.cells[c] ?? "")}
                </td>
              );
            })}
          </tr>
        ))}
      </tbody>
    </table>
  );
}
