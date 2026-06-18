import { useEffect, useRef, useState } from "react";
import { analyzeStream, getCompany, getMarket } from "../api";
import { DIMENSIONS, type CompanyDetail as Detail, type DimensionDetail } from "../types";
import { scoreColor } from "../themes";
import { ScoreCard } from "./ScoreCard";
import { RadarPanel } from "./RadarPanel";
import { ThinkingStream, type Stage } from "./ThinkingStream";
import { Breakdown } from "./Breakdown";
import { WeightEditor } from "./WeightEditor";

export function CompanyDetail({ ticker, onBack }: { ticker: string; onBack: () => void }) {
  const [detail, setDetail] = useState<Detail | null>(null);
  const [live, setLive] = useState<Record<string, DimensionDetail> | null>(null);
  const [overrides, setOverrides] = useState<Record<string, DimensionDetail>>({});
  const [streaming, setStreaming] = useState(false);
  const [stages, setStages] = useState<Stage[]>([]);
  const [tokens, setTokens] = useState("");
  const [citations, setCitations] = useState<Array<{ title: string; url: string }>>([]);
  const [error, setError] = useState<string | null>(null);
  const [breakdown, setBreakdown] = useState<DimensionDetail | null>(null);
  const [editing, setEditing] = useState<string | null>(null);

  // 1. fetch stored (deterministic 4-dim) detail
  useEffect(() => {
    getCompany(ticker).then(setDetail).catch((e) => setError(String(e)));
  }, [ticker]);

  // 2. open the live SSE thinking-stream
  useEffect(() => {
    setStreaming(true);
    setStages([]);
    setTokens("");
    setCitations([]);
    setLive(null);
    return analyzeStream(ticker, {
      onStage: (s) => setStages((p) => [...p, s]),
      onToken: (t) => setTokens((p) => p + t.text),
      onCitation: (c) => setCitations((p) => [...p, c]),
      onScores: (d) => setLive(d.scores),
      onError: (e) => {
        setError(e.message);
        setStreaming(false);
      },
      onDone: () => setStreaming(false),
    });
  }, [ticker]);

  // 3. live market poll (10s, market-hours gated, capped): refreshes valuation only
  const pollCount = useRef(0);
  useEffect(() => {
    if (!detail) return;
    pollCount.current = 0;
    let timer: ReturnType<typeof setTimeout>;
    let cancelled = false;
    const poll = async () => {
      try {
        const q = await getMarket(ticker);
        if (cancelled || !q.market_open) return;
        if (q.recomputed?.graham) {
          setOverrides((p) => ({ ...p, graham: q.recomputed!.graham }));
        }
        pollCount.current += 1;
        if (pollCount.current < q.poll_max) {
          timer = setTimeout(poll, q.poll_interval_s * 1000);
        }
      } catch {
        /* stop polling on error */
      }
    };
    poll();
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [detail?.ticker]);

  if (!detail) {
    return (
      <div className="card">
        {error ? `Error: ${error}` : `Loading ${ticker}…`}
        <div style={{ marginTop: 12 }}>
          <button className="btn ghost" onClick={onBack}>
            ← Back
          </button>
        </div>
      </div>
    );
  }

  const dimOf = (key: string): DimensionDetail | null =>
    overrides[key] ?? live?.[key] ?? detail.scores[key] ?? null;

  const promoterDim = live?.promoter_integrity ?? (detail.promoter_live ? detail.scores.promoter_integrity : null);
  const radar = DIMENSIONS.map((d) => {
    const dim = d.key === "promoter_integrity" ? promoterDim : dimOf(d.key);
    return { dim: d.label.split(" ")[0], pct: dim && dim.max_score > 0 ? dim.normalized_pct : 0 };
  });
  const composite = live ? detail.composite_pct_full : detail.composite_pct_4dim;

  return (
    <>
      <div className="hdr">
        <button className="btn ghost sm" onClick={onBack}>
          ← Back
        </button>
        <h1>{detail.name || detail.ticker}</h1>
        <span className="chip">{detail.ticker}</span>
        {detail.sector && <span className="chip">{detail.sector}</span>}
        <span className="chip num" style={{ color: scoreColor(composite) }}>
          composite {composite.toFixed(0)}%
        </span>
        {streaming && (
          <span className="live-badge">
            <span className="live-dot" /> AI analysing live, fetching up-to-the-minute data
          </span>
        )}
      </div>

      <div className="grid">
        {DIMENSIONS.map((d) => {
          if (d.key === "promoter_integrity") {
            const lastStage = stages.length > 0 ? stages[stages.length - 1].message : undefined;
            return (
              <ScoreCard
                key={d.key}
                label={d.label}
                dim={promoterDim}
                pending={streaming ? undefined : "select to calculate"}
                stageLine={streaming && !promoterDim ? lastStage : undefined}
                onInfo={promoterDim ? () => setBreakdown(promoterDim) : undefined}
              />
            );
          }
          const dim = dimOf(d.key);
          return (
            <ScoreCard
              key={d.key}
              label={d.label}
              dim={dim}
              onInfo={dim ? () => setBreakdown(dim) : undefined}
              onEdit={dim ? () => setEditing(d.key) : undefined}
            />
          );
        })}
      </div>

      <div className="cols">
        <RadarPanel data={radar} />
        <div className="panel">
          <div className="section-title">Qualitative synthesis (AI, display-only)</div>
          <div style={{ lineHeight: 1.55 }}>
            {tokens || detail.narrative || (streaming ? "…" : "No narrative yet.")}
          </div>
        </div>
      </div>

      <div style={{ marginTop: 16 }}>
        <ThinkingStream
          active={streaming}
          stages={stages}
          tokens=""
          citations={citations}
          error={error}
        />
      </div>

      {breakdown && <Breakdown dim={breakdown} onClose={() => setBreakdown(null)} />}
      {editing && dimOf(editing) && (
        <WeightEditor
          ticker={ticker}
          dimKey={editing}
          dim={dimOf(editing)!}
          onClose={() => setEditing(null)}
          onApply={(nd) => setOverrides((p) => ({ ...p, [editing]: nd }))}
        />
      )}
    </>
  );
}
