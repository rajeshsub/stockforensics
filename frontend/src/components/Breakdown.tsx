import type { BreakdownRow, DimensionDetail } from "../types";

const STATUS_CLS: Record<BreakdownRow["status"], string> = {
  PASS: "pass",
  FAIL: "fail",
  NA: "na",
};

export function Breakdown({ dim, onClose }: { dim: DimensionDetail; onClose: () => void }) {
  const fails = dim.breakdown.filter((b) => b.status === "FAIL").length;
  return (
    <div className="overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="hdr">
          <h1 style={{ fontSize: 18 }}>
            {dim.name}: {dim.score.toFixed(1)} / {dim.max_score.toFixed(1)}
          </h1>
          <span className="chip num">{dim.normalized_pct.toFixed(1)}%</span>
          {fails > 0 && <span className="chip bd-failchip">{fails} failed</span>}
        </div>
        <div className="muted" style={{ marginBottom: 12 }}>
          Every criterion is PASS / FAIL / NA. The reasoning below is exactly what the
          code thresholded; LLM-sourced rows cite live web/SEC evidence.
        </div>

        <div className="bd-list">
          {dim.breakdown.map((b) => (
            <div key={b.key} className={`bd-row ${STATUS_CLS[b.status]}`}>
              <div className="bd-head">
                <span className={`bd-badge ${STATUS_CLS[b.status]}`}>
                  {b.symbol} {b.status}
                </span>
                <span className="bd-crit">{b.criterion}</span>
                <span className={`tag ${b.provenance === "CODE" ? "code" : "llm"}`}>
                  {b.provenance === "CODE" ? "SEC EDGAR" : "LLM evidence"}
                </span>
                <span className="bd-pts num">
                  {b.earned.toFixed(2)} / {b.max_points.toFixed(2)} pts
                </span>
              </div>

              {(b.value != null || b.window_used) && (
                <div className="bd-value">
                  {b.value != null && (
                    <span>
                      value <b className="num">{b.value}</b>
                    </span>
                  )}
                  {b.window_used && <span className="muted">window {b.window_used}</span>}
                </div>
              )}

              {b.reason && <div className="bd-reason">{b.reason}</div>}

              {b.url.length > 0 && (
                <div className="bd-sources">
                  {b.url.map((u, i) => (
                    <a key={i} href={u} target="_blank" rel="noreferrer">
                      source {i + 1}
                    </a>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>

        <div style={{ marginTop: 16, textAlign: "right" }}>
          <button className="btn" onClick={onClose}>
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
