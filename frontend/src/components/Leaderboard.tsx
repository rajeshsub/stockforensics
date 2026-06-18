import { useState } from "react";
import type { CompanySummary } from "../types";
import { scoreColor } from "../themes";

const COLS = [
  { key: "graham", label: "Graham" },
  { key: "buffett", label: "Buffett" },
  { key: "munger", label: "Munger" },
  { key: "earnings_quality", label: "EarnQ" },
] as const;

function Cell({ pct }: { pct: number }) {
  const c = scoreColor(pct);
  return (
    <div
      className="cell num"
      style={{ color: c, background: `color-mix(in srgb, ${c} 14%, transparent)` }}
    >
      {pct.toFixed(0)}
    </div>
  );
}

export function Leaderboard({
  companies,
  onSelect,
}: {
  companies: CompanySummary[];
  onSelect: (t: string) => void;
}) {
  const [sort, setSort] = useState<string>("composite");

  const val = (c: CompanySummary, key: string): number => {
    if (key === "composite") return c.composite_pct;
    if (key === "promoter") return c.promoter.live ? (c.promoter.normalized_pct ?? -1) : -1;
    return c.scores[key]?.normalized_pct ?? -1;
  };
  const rows = [...companies].sort((a, b) => val(b, sort) - val(a, sort));

  return (
    <>
      <div className="hdr">
        <h1>S&P Leaderboard</h1>
        <span className="chip num">{companies.length} companies</span>
        <span className="chip">ranked on 4 deterministic dims</span>
      </div>

      <div className="panel">
        <div className="section-title">Click a company to run live AI analysis</div>
        <div className="heat">
          <div className="h" onClick={() => setSort("ticker")}>
            Company
          </div>
          {COLS.map((col) => (
            <div key={col.key} className="h" onClick={() => setSort(col.key)}>
              {col.label} {sort === col.key ? "▾" : ""}
            </div>
          ))}
          <div className="h" onClick={() => setSort("promoter")}>
            Promoter
          </div>
          <div className="h" onClick={() => setSort("composite")}>
            Avg {sort === "composite" ? "▾" : ""}
          </div>

          {rows.map((c) => (
            <Row key={c.ticker} c={c} onSelect={onSelect} />
          ))}
        </div>
        <div className="foot">
          Promoter Integrity is computed live when you select a stock (it needs the AI).
          Until then it reads “Select to calculate”. The ranking stays on the 4 reproducible
          code-computed dimensions so rows are comparable.
        </div>
      </div>
    </>
  );
}

function Row({ c, onSelect }: { c: CompanySummary; onSelect: (t: string) => void }) {
  return (
    <>
      <div className="co" onClick={() => onSelect(c.ticker)}>
        {c.ticker}
        <div className="muted">{c.name}</div>
      </div>
      {COLS.map((col) => (
        <Cell key={col.key} pct={c.scores[col.key]?.normalized_pct ?? 0} />
      ))}
      {c.promoter.live && c.promoter.normalized_pct != null ? (
        <Cell pct={c.promoter.normalized_pct} />
      ) : (
        <div className="placeholder" title="Computed live on selection">
          Select to calculate
        </div>
      )}
      <div className="cell num" style={{ color: scoreColor(c.composite_pct) }}>
        {c.composite_pct.toFixed(0)}
      </div>
    </>
  );
}
