"""
FRED API Client
Fetches macroeconomic indicators from the Federal Reserve Economic Data API.
"""

import os
from dataclasses import dataclass
from datetime import datetime

import pandas as pd
from fredapi import Fred
from loguru import logger

import asyncio
import time
from concurrent.futures import ThreadPoolExecutor

# Key macro series for our risk model
MACRO_SERIES = {
    # Growth
    "GDP": {"name": "GDP", "frequency": "quarterly", "signal": "growth"},
    "PAYEMS": {"name": "Nonfarm Payrolls", "frequency": "monthly", "signal": "growth"},
    # Inflation
    "CPIAUCSL": {"name": "CPI (All Urban)", "frequency": "monthly", "signal": "inflation"},
    "PCEPI": {"name": "PCE Price Index", "frequency": "monthly", "signal": "inflation"},
    # Rates
    "FEDFUNDS": {"name": "Federal Funds Rate", "frequency": "daily", "signal": "rates"},
    "DGS10": {"name": "10-Year Treasury Yield", "frequency": "daily", "signal": "rates"},
    "DGS2": {"name": "2-Year Treasury Yield", "frequency": "daily", "signal": "rates"},
    "T10Y2Y": {"name": "10Y-2Y Spread", "frequency": "daily", "signal": "recession"},
    # Sentiment
    "UMCSENT": {"name": "Consumer Sentiment (UMich)", "frequency": "monthly", "signal": "sentiment"},
    "VIXCLS": {"name": "VIX", "frequency": "daily", "signal": "volatility"},
    # Labor
    "UNRATE": {"name": "Unemployment Rate", "frequency": "monthly", "signal": "labor"},
    "ICSA": {"name": "Initial Jobless Claims", "frequency": "weekly", "signal": "labor"},
    # Money supply
    "M2SL": {"name": "M2 Money Supply", "frequency": "monthly", "signal": "liquidity"},
}


@dataclass
class MacroSnapshot:
    """Current state of key macro indicators."""
    gdp_growth: float | None
    cpi_yoy: float | None
    unemployment: float | None
    fed_funds_rate: float | None
    yield_10y: float | None
    yield_2y: float | None
    yield_spread: float | None  # 10Y - 2Y (negative = inverted = recession signal)
    vix: float | None
    consumer_sentiment: float | None


class FREDClient:
    class FREDClient:
        def __init__(self, api_key: str | None = None):
            key = api_key or os.getenv("FRED_API_KEY")
            if not key:
                logger.warning("No FRED API key — macro data will be unavailable")
                self.fred = None
            else:
                self.fred = Fred(api_key=key)
            self._cache: dict = {}
            self._cache_time: float = 0
            self._cache_ttl: float = 1800  # 30 min — FRED doesn't update faster

        def get_series(self, series_id: str, start: str = "2020-01-01") -> pd.Series | None:
            if not self.fred:
                return None
            try:
                return self.fred.get_series(series_id, observation_start=start)
            except Exception as e:
                logger.error(f"Failed to fetch FRED series {series_id}: {e}")
                return None

        def get_macro_snapshot(self) -> MacroSnapshot:
            """Parallel fetch with local cache — no repeated calls within 30 min."""
            now = time.time()
            if self._cache and (now - self._cache_time) < self._cache_ttl:
                return self._cache["snapshot"]

            # Fetch all series in parallel using thread pool
            series_to_fetch = [
                "GDP", "CPIAUCSL", "UNRATE", "FEDFUNDS",
                "DGS10", "DGS2", "T10Y2Y", "VIXCLS", "UMCSENT"
            ]

            results = {}
            with ThreadPoolExecutor(max_workers=9) as executor:
                futures = {
                    series_id: executor.submit(self.get_series, series_id)
                    for series_id in series_to_fetch
                }
                for series_id, future in futures.items():
                    try:
                        s = future.result(timeout=10)
                        results[series_id] = float(s.iloc[-1]) if s is not None and len(s) > 0 else None
                    except Exception:
                        results[series_id] = None

            snapshot = MacroSnapshot(
                gdp_growth=results.get("GDP"),
                cpi_yoy=results.get("CPIAUCSL"),
                unemployment=results.get("UNRATE"),
                fed_funds_rate=results.get("FEDFUNDS"),
                yield_10y=results.get("DGS10"),
                yield_2y=results.get("DGS2"),
                yield_spread=results.get("T10Y2Y"),
                vix=results.get("VIXCLS"),
                consumer_sentiment=results.get("UMCSENT"),
            )

            self._cache = {"snapshot": snapshot}
            self._cache_time = now
            return snapshot

        def get_all_macro(self, start: str = "2020-01-01") -> dict[str, pd.Series]:
            data = {}
            with ThreadPoolExecutor(max_workers=len(MACRO_SERIES)) as executor:
                futures = {
                    series_id: executor.submit(self.get_series, series_id, start)
                    for series_id in MACRO_SERIES
                }
                for series_id, future in futures.items():
                    try:
                        s = future.result(timeout=15)
                        if s is not None:
                            data[series_id] = s
                    except Exception:
                        pass
            return data

        def is_yield_curve_inverted(self) -> bool | None:
            snapshot = self.get_macro_snapshot()
            if snapshot.yield_spread is not None:
                return snapshot.yield_spread < 0
            return None