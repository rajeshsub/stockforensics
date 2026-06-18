"""Live market data via yfinance. Smoke-tested, not in the gating suite."""

from __future__ import annotations

import yfinance as yf

from app.adapters.protocols import MarketData


class YFinanceMarketClient:
    def get_market_data(self, ticker: str) -> MarketData:
        try:
            info = yf.Ticker(ticker).info
        except Exception:
            return MarketData(ticker.upper())
        return MarketData(
            ticker=ticker.upper(),
            price=info.get("currentPrice") or info.get("regularMarketPrice"),
            market_cap=info.get("marketCap"),
            pe=info.get("trailingPE"),
            pb=info.get("priceToBook"),
            current_ratio=info.get("currentRatio"),
        )
