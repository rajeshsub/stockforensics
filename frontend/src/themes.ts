import { useEffect, useState } from "react";

export const THEMES = [
  { id: "fintech-light", label: "Fintech Light" },
  { id: "sb-minimal", label: "SB Minimal" },
  { id: "slate-pro", label: "Slate Pro" },
  { id: "swiss-minimal", label: "Swiss Minimal" },
  { id: "warm-dashboard", label: "Warm Dashboard" },
] as const;

export type ThemeId = (typeof THEMES)[number]["id"];
const KEY = "sf-theme";

const isThemeId = (v: string | null): v is ThemeId =>
  THEMES.some((t) => t.id === v);

export function useTheme(): [ThemeId, (t: ThemeId) => void] {
  const [theme, setTheme] = useState<ThemeId>(() => {
    const stored = localStorage.getItem(KEY);
    return isThemeId(stored) ? stored : "sb-minimal";
  });
  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem(KEY, theme);
  }, [theme]);
  return [theme, setTheme];
}

export function scoreColor(pct: number): string {
  if (pct >= 75) return "var(--good)";
  if (pct >= 45) return "var(--fair)";
  return "var(--bad)";
}
