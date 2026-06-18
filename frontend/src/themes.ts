import { useEffect, useState } from "react";

export const THEMES = [
  { id: "fintech-light", label: "Fintech Light" },
  { id: "glass-aurora", label: "Glass Aurora" },
  { id: "slate-pro", label: "Slate Pro" },
  { id: "swiss-minimal", label: "Swiss Minimal" },
  { id: "warm-dashboard", label: "Warm Dashboard" },
] as const;

export type ThemeId = (typeof THEMES)[number]["id"];
const KEY = "sf-theme";

export function useTheme(): [ThemeId, (t: ThemeId) => void] {
  const [theme, setTheme] = useState<ThemeId>(
    () => (localStorage.getItem(KEY) as ThemeId) || "fintech-light",
  );
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
