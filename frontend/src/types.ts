export interface DimScore {
  score: number;
  max_score: number;
  normalized_pct: number;
  confidence: number;
}

export interface PromoterCell {
  live: boolean;
  normalized_pct?: number;
  placeholder?: string;
}

export interface CompanySummary {
  ticker: string;
  name: string | null;
  sector: string | null;
  market_cap: number | null;
  composite_pct: number; // 4-dim deterministic
  scores: Record<string, DimScore>;
  promoter: PromoterCell;
}

export interface BreakdownRow {
  key: string;
  criterion: string;
  weight: number;
  provenance: "CODE" | "LLM-EVIDENCE";
  status: "PASS" | "FAIL" | "NA";
  symbol: string;
  value: string | number | null;
  window_used: string | null;
  reason: string | null;
  max_points: number;
  earned: number;
  url: string[];
}

export interface DimensionDetail {
  name: string;
  score: number;
  max_score: number;
  nominal_max: number;
  normalized_pct: number;
  confidence: number;
  breakdown: BreakdownRow[];
}

export interface CompanyDetail {
  ticker: string;
  name: string | null;
  sector: string | null;
  market_cap: number | null;
  composite_pct_4dim: number;
  composite_pct_full: number;
  promoter_live: boolean;
  scores: Record<string, DimensionDetail>;
  narrative: string | null;
  promoter_findings: Array<Record<string, unknown>>;
}

export interface MarketQuote {
  ticker: string;
  market_open: boolean;
  poll_interval_s: number;
  poll_max: number;
  market?: { price: number | null; pe: number | null; pb: number | null; market_cap: number | null };
  recomputed?: { graham: DimensionDetail };
}

export const DIMENSIONS = [
  { key: "graham", label: "Graham", max: 7 },
  { key: "buffett", label: "Buffett Quality", max: 10 },
  { key: "munger", label: "Munger Composite", max: 10 },
  { key: "earnings_quality", label: "Earnings Quality", max: 10 },
  { key: "promoter_integrity", label: "Promoter Integrity", max: 10 },
] as const;

export type DimKey = (typeof DIMENSIONS)[number]["key"];

export type StreamHandlers = {
  onStage?: (d: { stage: string; message: string }) => void;
  onToken?: (d: { text: string }) => void;
  onCitation?: (d: { title: string; url: string }) => void;
  onScores?: (d: { ticker: string; promoter: DimensionDetail; composite_pct: number; scores: Record<string, DimensionDetail> }) => void;
  onError?: (d: { message: string }) => void;
  onDone?: () => void;
};
