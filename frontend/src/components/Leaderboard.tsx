import { useState } from "react";
import type { CompanySummary } from "../types";
import { scoreColor } from "../themes";

const COLS = [
  { key: "graham", label: "Graham" },
  { key: "buffett", label: "Buffett" },
  { key: "munger", label: "Munger" },
  { key: "earnings_quality", label: "EarnQ" },
] as const;

const ANALYSIS_TTL_MS = 4 * 60 * 60 * 1000;

function fmtDuration(ms: number): string {
  const totalMin = Math.floor(ms / 60000);
  if (totalMin < 1) return "< 1 min";
  if (totalMin < 60) return `${totalMin}m`;
  const h = Math.floor(totalMin / 60);
  const m = totalMin % 60;
  return m > 0 ? `${h}h ${m}m` : `${h}h`;
}

function aiStatusInfo(analyzedAt: string | null): { label: string; cls: string } {
  if (!analyzedAt) return { label: "Not yet analysed", cls: "pending" };
  const ageMs = Date.now() - new Date(analyzedAt).getTime();
  const expiresInMs = ANALYSIS_TTL_MS - ageMs;
  if (expiresInMs <= 0) {
    return {
      label: `Last analysed ${fmtDuration(ageMs)} ago - will refresh on next click`,
      cls: "stale",
    };
  }
  return {
    label: `Analysed ${fmtDuration(ageMs)} ago - cached for ${fmtDuration(expiresInMs)} more`,
    cls: "fresh",
  };
}

/** Round to integer, but keep one decimal for small non-zero values so a real
 * fractional score (e.g. 0.3%) is never displayed as a flat "0". */
function fmtPct(pct: number): string {
  return pct > 0 && pct < 0.95 ? pct.toFixed(1) : pct.toFixed(0);
}

function Cell({ pct }: { pct: number }) {
  const c = scoreColor(pct);
  return (
    <div
      className={`cell num${pct === 0 ? " zero" : ""}`}
      style={{ color: c, background: `color-mix(in srgb, ${c} 14%, transparent)` }}
    >
      {fmtPct(pct)}
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
        <div className="heat-scroll">
        <div className="heat">
          <div className="heat-head">
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
          </div>

          {rows.map((c) => (
            <Row key={c.ticker} c={c} onSelect={onSelect} />
          ))}
        </div>
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
  const { label, cls } = aiStatusInfo(c.analyzed_at);
  return (
    <div
      className="heat-row"
      role="button"
      tabIndex={0}
      onClick={() => onSelect(c.ticker)}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onSelect(c.ticker);
        }
      }}
    >
      <div className="co">
        <span className="co-ticker">{c.ticker}</span>
        <span className="co-name muted">{c.name}</span>
        <div className={`ai-tag ${cls}`}>{label}</div>
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
        {fmtPct(c.composite_pct)}
      </div>
    </div>
  );
}
