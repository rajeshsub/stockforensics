import type { DimensionDetail } from "../types";

export function Breakdown({ dim, onClose }: { dim: DimensionDetail; onClose: () => void }) {
  return (
    <div className="overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="hdr">
          <h1 style={{ fontSize: 18 }}>
            {dim.name}: {dim.score.toFixed(1)} / {dim.max_score.toFixed(1)}
          </h1>
          <span className="chip num">{dim.normalized_pct.toFixed(0)}%</span>
        </div>
        <table>
          <thead>
            <tr>
              <th>Criterion</th>
              <th>Src</th>
              <th className="r">Value</th>
              <th>Window</th>
              <th>St</th>
              <th className="r">Pts</th>
            </tr>
          </thead>
          <tbody>
            {dim.breakdown.map((b) => (
              <tr key={b.key}>
                <td title={b.reason ?? ""}>{b.criterion}</td>
                <td>
                  <span className={`tag ${b.provenance === "CODE" ? "code" : "llm"}`}>
                    {b.provenance === "CODE" ? "SEC EDGAR" : "LLM"}
                  </span>
                </td>
                <td className="r num">{b.value ?? "–"}</td>
                <td className="muted">{b.window_used ?? ""}</td>
                <td className={b.status === "PASS" ? "ok" : b.status === "FAIL" ? "no" : "na"}>
                  {b.symbol}
                </td>
                <td className="r num">{b.earned.toFixed(2)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <div style={{ marginTop: 16, textAlign: "right" }}>
          <button className="btn" onClick={onClose}>
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
