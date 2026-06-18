import { useState } from "react";
import { recalculate } from "../api";
import type { DimensionDetail } from "../types";

interface Crit {
  key: string;
  label: string;
  enabled: boolean;
  weight: number;
}

export function WeightEditor({
  ticker,
  dimKey,
  dim,
  onClose,
  onApply,
}: {
  ticker: string;
  dimKey: string;
  dim: DimensionDetail;
  onClose: () => void;
  onApply: (d: DimensionDetail) => void;
}) {
  const init = (): Crit[] =>
    dim.breakdown.map((b) => ({
      key: b.key,
      label: b.criterion,
      enabled: b.status !== "NA",
      weight: b.weight,
    }));
  const [crits, setCrits] = useState<Crit[]>(init);
  const [busy, setBusy] = useState(false);

  const enabledSum = crits.filter((c) => c.enabled).reduce((s, c) => s + c.weight, 0) || 1;

  const apply = async () => {
    setBusy(true);
    try {
      const weights = {
        [dimKey]: Object.fromEntries(
          crits.map((c) => [c.key, c.enabled ? c.weight : null]),
        ),
      };
      const res = await recalculate(ticker, weights);
      onApply(res.recalculated[dimKey]);
      onClose();
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="hdr">
          <h1 style={{ fontSize: 18 }}>Edit {dim.name} weights</h1>
        </div>
        <div className="row" style={{ fontWeight: 700, color: "var(--mut)" }}>
          <div>Criterion</div>
          <div>Weight</div>
          <div className="r">Norm</div>
          <div className="r">Pts</div>
        </div>
        {crits.map((c, i) => {
          const norm = c.enabled ? c.weight / enabledSum : 0;
          return (
            <div className="row" key={c.key} style={{ opacity: c.enabled ? 1 : 0.5 }}>
              <label>
                <input
                  type="checkbox"
                  checked={c.enabled}
                  onChange={(e) =>
                    setCrits((p) =>
                      p.map((x, j) => (j === i ? { ...x, enabled: e.target.checked } : x)),
                    )
                  }
                />{" "}
                {c.label}
              </label>
              <input
                type="range"
                min={0.01}
                max={0.5}
                step={0.01}
                value={c.weight}
                disabled={!c.enabled}
                onChange={(e) =>
                  setCrits((p) =>
                    p.map((x, j) => (j === i ? { ...x, weight: Number(e.target.value) } : x)),
                  )
                }
              />
              <div className="r num">{(norm * 100).toFixed(0)}%</div>
              <div className="r num">{(dim.nominal_max * norm).toFixed(2)}</div>
            </div>
          );
        })}
        <div className="foot">
          Disabling a criterion redistributes its weight proportionally. Code recomputes the
          score deterministically from stored inputs; no refetch, no LLM.
        </div>
        <div style={{ display: "flex", gap: 8, justifyContent: "flex-end", marginTop: 12 }}>
          <button className="btn ghost" onClick={() => setCrits(init)}>
            Reset
          </button>
          <button className="btn ghost" onClick={onClose}>
            Cancel
          </button>
          <button className="btn" disabled={busy} onClick={apply}>
            {busy ? "…" : "Apply"}
          </button>
        </div>
      </div>
    </div>
  );
}
