import { useState } from "react";
import { scoreColor } from "../themes";

/** First real (non-heading) paragraph of the narrative: the AI's executive verdict. */
function verdictOf(narrative: string): string {
  return (
    narrative
      .replace(/\r\n/g, "\n")
      .split(/\n{2,}/)
      .map((s) => s.trim())
      .find((s) => s && !/^#{1,3}\s/.test(s)) ?? narrative.trim()
  );
}

type DimSummary = { dim: string; pct: number };

export function CompositeCard({
  compositePct,
  narrative,
  dims,
  streaming,
}: {
  compositePct: number;
  narrative: string | null;
  dims: DimSummary[];
  streaming: boolean;
}) {
  const [open, setOpen] = useState(false);
  const verdict = narrative
    ? verdictOf(narrative)
    : streaming
      ? "Synthesising the AI's overall view…"
      : "No AI synthesis yet.";

  return (
    <>
      <div className="card composite-card">
        <div className="label">Composite result (AI generated)</div>
        <div className="score num" style={{ color: scoreColor(compositePct) }}>
          {compositePct.toFixed(0)}
          <span className="den">%</span>
        </div>
        <p className="composite-verdict">{verdict}</p>
        {narrative && (
          <button className="info-pill" onClick={() => setOpen(true)}>
            Click for info
          </button>
        )}
      </div>

      {open && narrative && (
        <div className="overlay" onClick={() => setOpen(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="hdr">
              <h1 style={{ fontSize: 18 }}>Composite result · why the AI thinks so</h1>
              <span className="chip num" style={{ color: scoreColor(compositePct) }}>
                {compositePct.toFixed(0)}%
              </span>
            </div>

            <div className="muted" style={{ marginBottom: 10 }}>
              The composite blends the deterministic, code-computed dimensions below; the
              narrative is the AI's qualitative read of those results.
            </div>

            <div className="composite-dims">
              {dims.map((d) => (
                <div key={d.dim} className="composite-dim">
                  <span>{d.dim}</span>
                  <div className="bar" style={{ flex: 1 }}>
                    <i style={{ width: `${d.pct}%`, background: scoreColor(d.pct) }} />
                  </div>
                  <b className="num" style={{ color: scoreColor(d.pct) }}>
                    {d.pct.toFixed(0)}%
                  </b>
                </div>
              ))}
            </div>

            <div className="composite-narrative">
              {narrative
                .replace(/\r\n/g, "\n")
                .split(/\n{2,}/)
                .map((p, i) => {
                  const h = p.trim().match(/^#{1,3}\s+(.*)$/);
                  return h ? (
                    <h4 key={i} className="synth-h">
                      {h[1]}
                    </h4>
                  ) : (
                    <p key={i} className="synth-p">
                      {p.trim()}
                    </p>
                  );
                })}
            </div>

            <div style={{ marginTop: 16, textAlign: "right" }}>
              <button className="btn" onClick={() => setOpen(false)}>
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
