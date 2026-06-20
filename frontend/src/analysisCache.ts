import type { DimensionDetail } from "./types";
import type { Stage } from "./components/ThinkingStream";

/** Client-side cache of a completed live analysis, keyed by ticker. Mirrors the
 * backend's 4h analysis TTL so the thinking stream, narrative, citations and the
 * live Promoter score survive navigating back to the leaderboard and returning,
 * instead of being lost when CompanyDetail unmounts. */
export interface CachedAnalysis {
  ticker: string;
  stages: Stage[];
  citations: Array<{ title: string; url: string; domain?: string }>;
  narrative: string | null;
  scores: Record<string, DimensionDetail> | null;
  completedAt: number; // epoch ms
}

const TTL_MS = 4 * 60 * 60 * 1000; // 4h, matches backend _ANALYSIS_TTL_S
// Bump the version suffix when the cached shape changes (e.g. citation `domain`
// added) so stale pre-change entries are ignored instead of overriding fresh data.
const key = (ticker: string) => `sf-analysis-v3-${ticker.toUpperCase()}`;

export function loadAnalysis(ticker: string): CachedAnalysis | null {
  try {
    const raw = localStorage.getItem(key(ticker));
    if (!raw) return null;
    const parsed = JSON.parse(raw) as CachedAnalysis;
    if (Date.now() - parsed.completedAt >= TTL_MS) {
      localStorage.removeItem(key(ticker));
      return null;
    }
    return parsed;
  } catch {
    return null;
  }
}

export function saveAnalysis(a: CachedAnalysis): void {
  try {
    localStorage.setItem(key(a.ticker), JSON.stringify(a));
  } catch {
    /* quota / serialisation failures are non-fatal: we simply re-stream next time */
  }
}
