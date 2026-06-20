import type { DimensionDetail } from "../types";
import { scoreColor } from "../themes";

export function ScoreCard({
  label,
  dim,
  pending,
  stageLine,
  onInfo,
  onEdit,
}: {
  label: string;
  dim: DimensionDetail | null;
  pending?: string;
  stageLine?: string; // live stage message shown with spinner while computing
  onInfo?: () => void;
  onEdit?: () => void;
}) {
  if (!dim) {
    return (
      <div className="card">
        <div className="label">{label}</div>
        {stageLine ? (
          <div className="pending-stage">
            <span className="spinner" />
            <span>{stageLine}</span>
          </div>
        ) : (
          <div className="score" style={{ fontSize: 18, color: "var(--mut)" }}>
            {pending || "–"}
          </div>
        )}
      </div>
    );
  }
  const pct = dim.normalized_pct;
  const isZero = dim.max_score > 0 && dim.score === 0; // genuinely scored 0 (not NA)
  return (
    <div className={`card${isZero ? " card-zero" : ""}`}>
      <div className="icons">
        {onEdit && (
          <button title="edit weights" onClick={onEdit}>
            ⚙
          </button>
        )}
      </div>
      <div className="label">{label}</div>
      <div className="score num">
        {isZero ? (
          <span className="zero-ring" title="Scored zero: every evaluated criterion failed">
            0
          </span>
        ) : (
          dim.score.toFixed(1)
        )}
        <span className="den">/{dim.max_score.toFixed(1)}</span>
      </div>
      <div className="bar">
        <i style={{ width: `${pct}%`, background: scoreColor(pct) }} />
      </div>
      <div className="meta">
        <span>{pct > 0 && pct < 0.95 ? pct.toFixed(1) : pct.toFixed(0)}%</span>
        <span>conf {dim.confidence.toFixed(2)}</span>
      </div>
      {onInfo && (
        <button className="info-pill" onClick={onInfo}>
          Click for info
        </button>
      )}
    </div>
  );
}
