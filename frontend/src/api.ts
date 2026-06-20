import type {
  CompanyDetail,
  CompanySummary,
  DimensionDetail,
  MarketQuote,
  StreamHandlers,
} from "./types";

const API_KEY = import.meta.env.VITE_API_KEY ?? "";

const authHeaders = (): HeadersInit => (API_KEY ? { "X-Api-Key": API_KEY } : {});

async function getJSON<T>(url: string): Promise<T> {
  const r = await fetch(url, { headers: authHeaders() });
  if (!r.ok) throw new Error(`${r.status} ${url}`);
  return r.json() as Promise<T>;
}

export const getCompanies = () => getJSON<CompanySummary[]>("/api/companies");
export const getCompany = (t: string) => getJSON<CompanyDetail>(`/api/companies/${t}`);
export const getMarket = (t: string) => getJSON<MarketQuote>(`/api/market/${t}`);

export async function recalculate(
  ticker: string,
  weights: Record<string, Record<string, number | null>>,
): Promise<{ recalculated: Record<string, DimensionDetail>; composite_pct: number }> {
  const r = await fetch("/api/score/recalculate", {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify({ ticker, weights }),
  });
  if (!r.ok) throw new Error(`recalc ${r.status}`);
  return r.json();
}

/** Open the SSE thinking-stream for a stock. Returns a close() fn. */
export function analyzeStream(ticker: string, h: StreamHandlers): () => void {
  const qs = API_KEY ? `?api_key=${encodeURIComponent(API_KEY)}` : "";
  const es = new EventSource(`/api/analyze/${ticker}/stream${qs}`);
  const on = (name: string, cb: (d: any) => void) =>
    es.addEventListener(name, (e) => cb(JSON.parse((e as MessageEvent).data)));
  if (h.onStage) on("stage", h.onStage);
  if (h.onToken) on("token", h.onToken);
  if (h.onThought) on("thought", h.onThought);
  if (h.onCitation) on("citation", h.onCitation);
  if (h.onScores) on("scores", h.onScores);
  if (h.onCached) on("cached", h.onCached);
  if (h.onError) on("error", h.onError);
  on("done", () => {
    h.onDone?.();
    es.close();
  });
  es.onerror = () => es.close();
  return () => es.close();
}
