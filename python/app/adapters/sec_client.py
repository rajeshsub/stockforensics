"""Live SEC EDGAR client (httpx). companyfacts XBRL + filings text. Requires a
descriptive User-Agent per SEC policy. Smoke-tested, not in the gating suite."""

from __future__ import annotations

import re

import httpx

from app.adapters.protocols import FilingDoc, InsiderSummary

TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
ARCHIVE_URL = "https://www.sec.gov/Archives/edgar/data/{cik}/{acc}/{doc}"
MAX_DOC_CHARS = 40_000


class HttpxSecClient:
    def __init__(self, user_agent: str) -> None:
        self._client = httpx.Client(headers={"User-Agent": user_agent}, timeout=30.0)
        self._cik_map: dict[str, str] | None = None

    def _get(self, url: str) -> httpx.Response:
        r = self._client.get(url)
        r.raise_for_status()
        return r

    def resolve_cik(self, ticker: str) -> str | None:
        if self._cik_map is None:
            try:
                data = self._get(TICKERS_URL).json()
                self._cik_map = {
                    str(row["ticker"]).upper(): f"{int(row['cik_str']):010d}"
                    for row in data.values()
                }
            except Exception:
                self._cik_map = {}  # empty on failure so subsequent calls skip the network
        t = ticker.upper()
        return self._cik_map.get(t) or self._cik_map.get(t.replace(".", "-"))

    def get_company_facts(self, cik: str) -> dict:
        try:
            return self._get(FACTS_URL.format(cik=cik)).json()
        except httpx.HTTPError:
            return {"facts": {"us-gaap": {}}}

    def get_insider_summary(self, cik: str) -> InsiderSummary:
        # Form 4 ownership/insider-selling parsing is a follow-up; absent data ->
        # the CODE promoter criteria evaluate NA and renormalise (Q9).
        return InsiderSummary()

    def get_filings(self, cik: str, forms: tuple[str, ...]) -> list[FilingDoc]:
        out: list[FilingDoc] = []
        try:
            recent = self._get(SUBMISSIONS_URL.format(cik=cik)).json()["filings"]["recent"]
        except (httpx.HTTPError, KeyError):
            return out
        seen: set[str] = set()
        for form, acc, doc in zip(
            recent.get("form", []),
            recent.get("accessionNumber", []),
            recent.get("primaryDocument", []),
            strict=False,
        ):
            if form not in forms or form in seen:
                continue
            seen.add(form)
            url = ARCHIVE_URL.format(cik=int(cik), acc=acc.replace("-", ""), doc=doc)
            out.append(FilingDoc(acc, form, url, self._fetch_text(url)))
            if len(seen) == len(forms):
                break
        return out

    def _fetch_text(self, url: str) -> str:
        try:
            html = self._get(url).text
        except httpx.HTTPError:
            return ""
        text = re.sub(r"<[^>]+>", " ", html)
        return re.sub(r"\s+", " ", text)[:MAX_DOC_CHARS]
