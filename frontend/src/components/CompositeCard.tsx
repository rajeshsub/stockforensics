import { useState } from "react";
import { scoreColor } from "../themes";
import { parseNarrative, inline, Blocks } from "./Synthesis";

/** First real (non-heading) paragraph: the AI's executive verdict for the card summary. */
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
        <p className="composite-verdict">{inline(verdict, "cv")}</p>
        {narrative && (
          <button className="info-pill" onClick={() => setOpen(true)}>
            More info
          </button>
        )}
      </div>

      {open && narrative && (
        <div className="overlay" onClick={() => setOpen(false)}>
          <div className="modal composite-modal" onClick={(e) => e.stopPropagation()}>
            <div className="hdr">
              <h1 style={{ fontSize: 17 }}>Composite AI synthesis</h1>
              <span className="chip num" style={{ color: scoreColor(compositePct) }}>
                {compositePct.toFixed(0)}%
              </span>
              <button className="btn ghost sm" style={{ marginLeft: "auto" }} onClick={() => setOpen(false)}>
                ✕
              </button>
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
              {(() => {
                const { summary, sections } = parseNarrative(narrative);
                return (
                  <>
                    {summary && (
                      <p className="cm-summary">{inline(summary, "csum")}</p>
                    )}
                    <div className="cm-sections">
                      {sections.map((s, si) => (
                        <div key={si} className="cm-section">
                          {s.heading && (
                            <h4 className="cm-heading">{inline(s.heading, `cmh${si}`)}</h4>
                          )}
                          <Blocks blocks={s.blocks} kb={`cms${si}`} />
                        </div>
                      ))}
                    </div>
                  </>
                );
              })()}
            </div>

            <div style={{ marginTop: 14, textAlign: "right" }}>
              <button className="btn" onClick={() => setOpen(false)}>Close</button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
