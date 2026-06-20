import { useCallback, useEffect, useState } from "react";
import { getCompanies } from "./api";
import type { CompanySummary } from "./types";
import { THEMES, useTheme } from "./themes";
import { Leaderboard } from "./components/Leaderboard";
import { CompanyDetail } from "./components/CompanyDetail";

export default function App() {
  const [theme, setTheme] = useTheme();
  const [companies, setCompanies] = useState<CompanySummary[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refreshCompanies = useCallback(() => {
    getCompanies()
      .then(setCompanies)
      .catch((e) => setError(String(e)));
  }, []);

  useEffect(() => {
    refreshCompanies();
  }, [refreshCompanies]);

  // Returning from a stock refetches the leaderboard so a just-finished analysis
  // (Promoter score + "analysed N ago" status) is reflected instead of going stale.
  const handleBack = useCallback(() => {
    setSelected(null);
    refreshCompanies();
  }, [refreshCompanies]);

  return (
    <>
      <div className="topbar">
        <div className="logo">
          Stock<b>Forensics</b>
        </div>
        <div className="disclaimer">Educational research · never buy/sell advice</div>
        <div className="spacer" />
        <select value={theme} onChange={(e) => setTheme(e.target.value as typeof theme)}>
          {THEMES.map((t) => (
            <option key={t.id} value={t.id}>
              {t.label}
            </option>
          ))}
        </select>
      </div>

      <div className="container">
        {error && <div className="card">Backend not reachable: {error}</div>}
        {selected ? (
          <CompanyDetail ticker={selected} onBack={handleBack} />
        ) : (
          <Leaderboard companies={companies} onSelect={setSelected} />
        )}
      </div>
    </>
  );
}
