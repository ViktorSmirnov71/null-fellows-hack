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
    def __init__(self, api_key: str | None = None):
        key = api_key or os.getenv("FRED_API_KEY")
        if not key:
            logger.warning("No FRED API key — macro data will be unavailable")
            self.fred = None
        else:
            self.fred = Fred(api_key=key)

    def get_series(self, series_id: str, start: str = "2020-01-01") -> pd.Series | None:
        """Fetch a single FRED series."""
        if not self.fred:
            return None
        try:
            return self.fred.get_series(series_id, observation_start=start)
        except Exception as e:
            logger.error(f"Failed to fetch FRED series {series_id}: {e}")
            return None

    def get_all_macro(self, start: str = "2020-01-01") -> dict[str, pd.Series]:
        """Fetch all key macro series."""
        data = {}
        for series_id in MACRO_SERIES:
            series = self.get_series(series_id, start=start)
            if series is not None:
                data[series_id] = series
        return data

    def get_macro_snapshot(self) -> MacroSnapshot:
        """Get the latest values for key indicators."""
        def latest(series_id: str) -> float | None:
            s = self.get_series(series_id)
            if s is not None and len(s) > 0:
                return float(s.iloc[-1])
            return None

        return MacroSnapshot(
            gdp_growth=latest("GDP"),
            cpi_yoy=latest("CPIAUCSL"),
            unemployment=latest("UNRATE"),
            fed_funds_rate=latest("FEDFUNDS"),
            yield_10y=latest("DGS10"),
            yield_2y=latest("DGS2"),
            yield_spread=latest("T10Y2Y"),
            vix=latest("VIXCLS"),
            consumer_sentiment=latest("UMCSENT"),
        )

    def is_yield_curve_inverted(self) -> bool | None:
        """Check if the yield curve is inverted (recession signal)."""
        spread = self.get_series("T10Y2Y")
        if spread is not None and len(spread) > 0:
            return float(spread.iloc[-1]) < 0
        return None
