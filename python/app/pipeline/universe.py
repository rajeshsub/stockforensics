"""S&P 500 universe from BlackRock iShares IVV holdings (Q8). Vendored snapshot +
24h-TTL refresh; dynamic header detection (no hardcoded skiprows); equity-only.
`python -m app.pipeline.universe --refresh` force-refreshes. Network code -> smoke."""

from __future__ import annotations

import csv
import io
import os
import re
import sys
import time

import httpx

IVV_URL = (
    "https://www.ishares.com/us/products/239726/ishares-core-sp-500-etf/"
    "1467271812596.ajax?fileType=csv&fileName=IVV_holdings&dataType=fund"
)
DEFAULT_SNAPSHOT = "data/universe/sp500.csv"
_TICKER_RE = re.compile(r"^[A-Z][A-Z.\-]*$")


def fetch_ishares_rows(url: str = IVV_URL) -> list[dict[str, str]]:
    """Download IVV holdings; find the header row dynamically; keep equity tickers."""
    r = httpx.get(url, timeout=60.0, follow_redirects=True)
    r.raise_for_status()
    lines = r.text.splitlines()
    hdr = next(
        (i for i, ln in enumerate(lines) if ln.lower().lstrip('"').startswith("ticker")),
        None,
    )
    if hdr is None:
        return []
    rows: list[dict[str, str]] = []
    for row in csv.DictReader(io.StringIO("\n".join(lines[hdr:]))):
        tk = (row.get("Ticker") or "").strip()
        asset = row.get("Asset Class") or ""
        if not _TICKER_RE.match(tk) or (asset and "Equity" not in asset):
            continue
        rows.append(
            {
                "ticker": tk,
                "name": (row.get("Name") or "").strip(),
                "sector": (row.get("Sector") or "").strip(),
            }
        )
    return rows


def refresh_snapshot(path: str = DEFAULT_SNAPSHOT, url: str = IVV_URL) -> int:
    rows = fetch_ishares_rows(url)
    if not rows:
        return 0
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["ticker", "name", "sector"])
        w.writeheader()
        w.writerows(rows)
    return len(rows)


def snapshot_age_hours(path: str = DEFAULT_SNAPSHOT) -> float | None:
    if not os.path.exists(path):
        return None
    return (time.time() - os.path.getmtime(path)) / 3600.0


def load_snapshot(path: str = DEFAULT_SNAPSHOT) -> list[dict[str, str]]:
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def main() -> None:  # pragma: no cover - CLI entry
    if "--refresh" in sys.argv:
        n = refresh_snapshot()
        print(f"refreshed universe: {n} constituents -> {DEFAULT_SNAPSHOT}")
    else:
        print(f"snapshot age: {snapshot_age_hours()} h; rows: {len(load_snapshot())}")


if __name__ == "__main__":  # pragma: no cover
    main()
