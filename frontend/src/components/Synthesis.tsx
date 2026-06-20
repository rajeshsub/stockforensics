/** Pretty renderer for the AI's qualitative narrative (display-only). Turns the
 * raw markdown-ish narrative into a styled article: a short "In brief" extract
 * panel, then the rest broken into headed sections separated by elegant, partial
 * dividers, plus a strip of source cards (with the publisher's favicon) drawn
 * from live web citations. */

import { useState, useEffect, type ReactNode } from "react";

type Block = { kind: "li"; items: string[] } | { kind: "p"; text: string };

/** How many source cards to show inline before collapsing the rest behind a
 * "Show all sources" button that opens the full list in a modal. */
const SOURCE_PREVIEW = 5;

interface Section {
  heading: string | null;
  blocks: Block[];
}

export function parseNarrative(md: string): { summary: string; sections: Section[] } {
  const lines = md.replace(/\r\n/g, "\n").split("\n");
  const sections: Section[] = [];
  let current: Section = { heading: null, blocks: [] };
  let buf: string[] = [];

  const flushPara = () => {
    const text = buf.join("\n").trim();
    buf = [];
    if (!text) return;
    const ls = text.split("\n");
    if (ls.every((l) => /^\s*[-*•]\s+/.test(l))) {
      current.blocks.push({
        kind: "li",
        items: ls.map((l) => l.replace(/^\s*[-*•]\s+/, "").trim()),
      });
    } else {
      current.blocks.push({ kind: "p", text: text.replace(/\n/g, " ") });
    }
  };
  const flushSection = () => {
    flushPara();
    if (current.heading !== null || current.blocks.length) sections.push(current);
    current = { heading: null, blocks: [] };
  };

  for (const line of lines) {
    const h = line.match(/^#{1,3}\s+(.*)$/);
    if (h) {
      flushSection();
      current = { heading: h[1].trim(), blocks: [] };
    } else if (line.trim() === "") {
      flushPara();
    } else {
      buf.push(line);
    }
  }
  flushSection();

  // Lift the opening (heading-less) paragraph into the "In brief" extract panel;
  // anything else in that lead block stays as an untitled section.
  let summary = "";
  if (sections.length && sections[0].heading === null) {
    const lead = sections[0];
    const firstP = lead.blocks.find((b) => b.kind === "p") as
      | { kind: "p"; text: string }
      | undefined;
    if (firstP) {
      summary = firstP.text;
      lead.blocks = lead.blocks.filter((b) => b !== firstP);
      if (lead.blocks.length === 0) sections.shift();
    }
  }
  return { summary, sections };
}

/** Minimal inline markdown -> React: **bold**, *italic*, `code`. */
export function inline(text: string, keyBase: string): ReactNode[] {
  const out: ReactNode[] = [];
  const re = /\*\*([^*]+)\*\*|\*([^*]+)\*|`([^`]+)`/g;
  let last = 0;
  let m: RegExpExecArray | null;
  let i = 0;
  while ((m = re.exec(text)) !== null) {
    if (m.index > last) out.push(text.slice(last, m.index));
    const k = `${keyBase}-${i++}`;
    if (m[1]) out.push(<strong key={k}>{m[1]}</strong>);
    else if (m[2]) out.push(<em key={k}>{m[2]}</em>);
    else if (m[3]) out.push(<code key={k}>{m[3]}</code>);
    last = re.lastIndex;
  }
  if (last < text.length) out.push(text.slice(last));
  return out;
}

function hostOf(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return url;
  }
}

const CRIT_LABEL: Record<string, string> = {
  sec_enforcement: "SEC enforcement",
  criminal_record: "Criminal record",
  related_party: "Related-party",
  ceo_tenure: "CEO tenure",
  public_co_experience: "Public-co experience",
};

function snippet(text: string, max = 110): string {
  const clean = text.replace(/\s+/g, " ").trim();
  const dot = clean.indexOf(". ");
  const head = dot > 30 && dot < max ? clean.slice(0, dot + 1) : clean;
  return head.length > max ? head.slice(0, max - 1).trimEnd() + "…" : head;
}

interface Source {
  title: string;
  url: string;
  label: string;
  /** real publisher domain for the favicon (URLs are opaque grounding redirects) */
  iconDomain: string;
}

const DOMAIN_RE = /^[a-z0-9-]+(\.[a-z0-9-]+)+$/i;
/** Opaque redirect hosts that carry no publisher identity. */
const REDIRECT_HOSTS = new Set(["vertexaisearch.cloud.google.com"]);

/** Gemini grounding gives the publisher domain in `domain` (or as the `title`),
 * while the URL is an opaque vertexaisearch redirect. Prefer the real domain so
 * the favicon is the publisher's, not a generic globe. Falls back to scanning the
 * title for a domain-shaped token before giving up. */
function iconDomainFor(domain: string | undefined, title: string, url: string): string {
  if (domain && DOMAIN_RE.test(domain)) return domain;
  const t = title.trim().toLowerCase();
  if (DOMAIN_RE.test(t)) return t;
  const host = hostOf(url);
  if (host && !REDIRECT_HOSTS.has(host)) return host;
  // scan title for a domain-shaped token (e.g. "Reuters.com - Finance")
  const fromTitle = t.split(/[\s|·–\-,]+/).find((tok) => DOMAIN_RE.test(tok));
  if (fromTitle) return fromTitle;
  return host; // last resort - may be the redirect host but that's all we have
}

/** Build the "In the news" cards from live web citations PLUS the persisted
 * promoter findings' source URLs (so the news survives cached / return views,
 * where streamed citations are no longer available). Deduped by URL. */
function buildSources(
  citations: Array<{ title: string; url: string; domain?: string }>,
  findings: Array<Record<string, unknown>>,
): Source[] {
  const seen = new Set<string>();
  const out: Source[] = [];
  const add = (title: string, url: string, label: string, iconDomain: string) => {
    if (!url || seen.has(url)) return;
    seen.add(url);
    out.push({ title: title || label || url, url, label, iconDomain });
  };
  for (const c of citations) {
    const dom = iconDomainFor(c.domain, c.title, c.url);
    add(c.title, c.url, dom, dom);
  }
  for (const f of findings) {
    const urls = (f.source_urls as string[] | undefined) ?? [];
    if (!urls.length) continue;
    const crit = String(f.criterion ?? "");
    const label = CRIT_LABEL[crit] ?? crit.replace(/_/g, " ");
    add(snippet(String(f.finding ?? "")), urls[0], label, hostOf(urls[0]));
  }
  return out;
}

// ---------------------------------------------------------------------------
// Favicon cache — stores data URIs in localStorage so favicons survive
// page reloads and cached-analysis loads without a network round-trip.
// ---------------------------------------------------------------------------

const FAVI_STORE = "sf-fav-v1";
let _faviMem: Record<string, string> | null = null;

function getFaviCache(): Record<string, string> {
  if (!_faviMem) {
    try { _faviMem = JSON.parse(localStorage.getItem(FAVI_STORE) || "{}"); }
    catch { _faviMem = {}; }
  }
  return _faviMem!;
}

function setCachedFavi(domain: string, dataUrl: string): void {
  const c = getFaviCache();
  c[domain] = dataUrl;
  const keys = Object.keys(c);
  if (keys.length > 300) delete c[keys[0]]; // simple LRU
  try { localStorage.setItem(FAVI_STORE, JSON.stringify(c)); } catch { /* quota */ }
}

async function fetchFaviDataUrl(domain: string): Promise<string | null> {
  try {
    const url = `https://www.google.com/s2/favicons?domain=${encodeURIComponent(domain)}&sz=64`;
    const res = await fetch(url);
    if (!res.ok) return null;
    const blob = await res.blob();
    if (blob.size > 20_000) return null; // skip unexpectedly large responses
    return new Promise((resolve) => {
      const reader = new FileReader();
      reader.onload = () => resolve(reader.result as string);
      reader.onerror = () => resolve(null);
      reader.readAsDataURL(blob);
    });
  } catch {
    return null;
  }
}

function FaviconImg({ domain }: { domain: string }) {
  const letter = (domain || "?").charAt(0).toUpperCase();
  const [src, setSrc] = useState<string | null>(() => getFaviCache()[domain] ?? null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    if (src || !domain || REDIRECT_HOSTS.has(domain)) return;
    let cancelled = false;
    fetchFaviDataUrl(domain).then((dataUrl) => {
      if (cancelled) return;
      if (dataUrl) {
        setCachedFavi(domain, dataUrl);
        setSrc(dataUrl);
      } else {
        setFailed(true);
      }
    });
    return () => { cancelled = true; };
  }, [domain, src]);

  if (failed || (!src && REDIRECT_HOSTS.has(domain))) {
    return (
      <div className="source-favicon source-favicon-letter" aria-hidden="true">
        {letter}
      </div>
    );
  }

  if (!src) {
    return <div className="source-favicon source-favicon-skeleton" aria-hidden="true" />;
  }

  return (
    <img
      className="source-favicon"
      src={src}
      alt=""
      onError={() => { setSrc(null); setFailed(true); }}
    />
  );
}

function SourceCard({ s }: { s: Source }) {
  return (
    <a
      className="source-card"
      href={s.url}
      target="_blank"
      rel="noreferrer"
      title={s.title}
    >
      <FaviconImg domain={s.iconDomain} />
      <div className="source-meta">
        <div className="source-title">{s.title}</div>
        <div className="source-host">{s.label}</div>
      </div>
    </a>
  );
}

export function Blocks({ blocks, kb }: { blocks: Block[]; kb: string }) {
  return (
    <>
      {blocks.map((b, i) =>
        b.kind === "li" ? (
          <ul key={i} className="synth-list">
            {b.items.map((it, j) => (
              <li key={j}>{inline(it, `${kb}-li${i}-${j}`)}</li>
            ))}
          </ul>
        ) : (
          <p key={i} className="synth-p">
            {inline(b.text, `${kb}-p${i}`)}
          </p>
        ),
      )}
    </>
  );
}

export function Synthesis({
  narrative,
  citations,
  findings = [],
  streaming,
}: {
  narrative: string | null;
  citations: Array<{ title: string; url: string; domain?: string }>;
  findings?: Array<Record<string, unknown>>;
  streaming: boolean;
}) {
  const [showAllSources, setShowAllSources] = useState(false);

  if (!narrative) {
    return (
      <div className="synth-empty">
        {streaming ? "Synthesising the qualitative narrative…" : "No narrative yet."}
      </div>
    );
  }

  const { summary, sections } = parseNarrative(narrative);
  const sources = buildSources(citations, findings);
  const preview = sources.slice(0, SOURCE_PREVIEW);
  const hidden = sources.length - preview.length;

  return (
    <div className="synth">
      <div className="synth-scroll">
        {summary && (
          <div className="synth-extract">
            <div className="synth-extract-label">In brief</div>
            <p className="synth-extract-text">{inline(summary, "sum")}</p>
          </div>
        )}

        {sections.map((s, si) => (
          <section key={si} className="synth-section">
            {(si > 0 || !!summary) && <hr className="synth-divider" />}
            {s.heading && <h4 className="synth-h">{inline(s.heading, `h${si}`)}</h4>}
            <Blocks blocks={s.blocks} kb={`s${si}`} />
          </section>
        ))}
      </div>

      {sources.length > 0 && (
        <div className="synth-sources">
          <div className="synth-sources-title">In the news · live web grounding</div>
          <div className="source-cards source-cards-row">
            {preview.map((s, i) => (
              <SourceCard key={i} s={s} />
            ))}
          </div>
          {hidden > 0 && (
            <button className="source-showall" onClick={() => setShowAllSources(true)}>
              Show all {sources.length} sources
            </button>
          )}
        </div>
      )}

      {showAllSources && (
        <div className="overlay" onClick={() => setShowAllSources(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="hdr">
              <h1 style={{ fontSize: 18 }}>In the news · all {sources.length} sources</h1>
            </div>
            <div className="muted" style={{ marginBottom: 12 }}>
              Live web grounding behind the AI synthesis. Each links to the original publisher.
            </div>
            <div className="source-cards">
              {sources.map((s, i) => (
                <SourceCard key={i} s={s} />
              ))}
            </div>
            <div style={{ marginTop: 16, textAlign: "right" }}>
              <button className="btn" onClick={() => setShowAllSources(false)}>
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
