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
  return (
    <div className="card">
      <div className="icons">
        {onInfo && (
          <button title="breakdown" onClick={onInfo}>
            ⓘ
          </button>
        )}
        {onEdit && (
          <button title="edit weights" onClick={onEdit}>
            ⚙
          </button>
        )}
      </div>
      <div className="label">{label}</div>
      <div className="score num">
        {dim.score.toFixed(1)}
        <span className="den">/{dim.max_score.toFixed(1)}</span>
      </div>
      <div className="bar">
        <i style={{ width: `${pct}%`, background: scoreColor(pct) }} />
      </div>
      <div className="meta">
        <span>{pct.toFixed(0)}%</span>
        <span>conf {dim.confidence.toFixed(2)}</span>
      </div>
    </div>
  );
}
