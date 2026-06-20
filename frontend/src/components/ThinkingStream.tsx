export interface Stage {
  stage: string;
  message: string;
}

export function ThinkingStream({
  active,
  stages,
  tokens,
  citations,
  error,
}: {
  active: boolean;
  stages: Stage[];
  tokens: string;
  citations: Array<{ title: string; url: string }>;
  error: string | null;
}) {
  return (
    <div className="thinking">
      <div className="section-title" style={{ display: "flex", justifyContent: "space-between" }}>
        <span>AI thinking stream</span>
        {active ? (
          <span className="live-badge">
            {stages.length === 0
              ? <span className="spinner" />
              : <span className="live-dot" />}
            live · working
          </span>
        ) : (
          <span className="muted">done</span>
        )}
      </div>

      <div className="thinking-stages">
        {stages.map((s, i) => {
          const isLast = i === stages.length - 1;
          const done = !isLast || !active;
          return (
            <div key={i} className={`stage ${isLast && active ? "active" : ""}`}>
              <span className="check">{done ? "✓" : "▸"}</span> {s.message}
            </div>
          );
        })}

        {tokens && <div className="tokens">{tokens}</div>}

        {citations.length > 0 && (
          <div className="citations">
            <div className="muted">Sources (live web grounding):</div>
            {citations.map((c, i) => (
              <a key={i} href={c.url} target="_blank" rel="noreferrer">
                {c.title || c.url}
              </a>
            ))}
          </div>
        )}

        {error && <div className="no">{error}</div>}
      </div>
    </div>
  );
}
