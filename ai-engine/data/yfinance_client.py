"""
yfinance Market Data Client
Pulls live prices, historical OHLCV, ETF holdings, and fund info from Yahoo Finance.
"""

import time
from dataclasses import dataclass
from datetime import datetime

import pandas as pd
import yfinance as yf
from loguru import logger


@dataclass
class AssetInfo:
    ticker: str
    name: str
    price: float
    currency: str
    asset_type: str  # "equity", "etf", "bond", "commodity"
    sector: str | None = None
    dividend_yield: float | None = None
    expense_ratio: float | None = None


# The vehicles from our investment universe
PORTFOLIO_UNIVERSE = {
    # Core equity ETFs
    "SPY": "SPDR S&P 500 ETF",
    "VTI": "Vanguard Total Stock Market ETF",
    "VEA": "Vanguard FTSE Developed Markets ETF",
    "VWO": "Vanguard FTSE Emerging Markets ETF",
    # Managed futures / trend-following
    "DBMF": "iMGP DBi Managed Futures Strategy ETF",
    "KMLM": "KraneShares Mount Lucas Managed Futures",
    "CTA": "Simplify Managed Futures Strategy ETF",
    "RPAR": "RPAR Risk Parity ETF",
    # CLO / structured credit
    "JAAA": "Janus Henderson AAA CLO ETF",
    "CLOA": "iShares AAA CLO Active ETF",
    "JBBB": "Janus Henderson B-BBB CLO ETF",
    # BDCs (private credit via stock market)
    "ARCC": "Ares Capital Corporation",
    "BXSL": "Blackstone Secured Lending",
    "OBDC": "Blue Owl Capital Corp",
    # Real assets / commodities
    "PDBC": "Invesco Optimum Yield Diversified Commodity",
    "GLDM": "SPDR Gold MiniShares",
    "SRLN": "State Street Blackstone Senior Loan ETF",
    # Bonds / treasuries
    "TLT": "iShares 20+ Year Treasury Bond ETF",
    "SHY": "iShares 1-3 Year Treasury Bond ETF",
    "AGG": "iShares Core US Aggregate Bond ETF",
}


class YFinanceClient:
    def __init__(self, request_delay: float = 0.5):
        self.request_delay = request_delay

    def get_asset_info(self, ticker: str) -> AssetInfo | None:
        """Get current info for a single ticker."""
        try:
            t = yf.Ticker(ticker)
            info = t.info
            return AssetInfo(
                ticker=ticker,
                name=info.get("shortName", ticker),
                price=info.get("regularMarketPrice", 0.0),
                currency=info.get("currency", "USD"),
                asset_type=self._classify_type(info),
                sector=info.get("sector"),
                dividend_yield=info.get("dividendYield"),
                expense_ratio=info.get("annualReportExpenseRatio"),
            )
        except Exception as e:
            logger.error(f"Failed to get info for {ticker}: {e}")
            return None

    def get_historical(
        self,
        tickers: list[str],
        period: str = "5y",
        interval: str = "1d",
    ) -> pd.DataFrame:
        """
        Download historical close prices for multiple tickers.
        Returns DataFrame with tickers as columns, dates as index.
        """
        logger.info(f"Downloading {period} history for {len(tickers)} tickers")
        data = yf.download(tickers, period=period, interval=interval, auto_adjust=True)
        if "Close" in data.columns.get_level_values(0):
            return data["Close"]
        return data

    def get_universe_prices(self, period: str = "5y") -> pd.DataFrame:
        """Get historical prices for all tickers in our investment universe."""
        tickers = list(PORTFOLIO_UNIVERSE.keys())
        return self.get_historical(tickers, period=period)

    def get_live_quotes(self, tickers: list[str] | None = None) -> dict[str, float]:
        """Get current prices for tickers. Defaults to full universe."""
        tickers = tickers or list(PORTFOLIO_UNIVERSE.keys())
        quotes = {}
        for ticker in tickers:
            try:
                t = yf.Ticker(ticker)
                price = t.fast_info.get("lastPrice", 0.0)
                quotes[ticker] = price
                time.sleep(self.request_delay)
            except Exception as e:
                logger.error(f"Failed to get quote for {ticker}: {e}")
        return quotes

    def _classify_type(self, info: dict) -> str:
        qtype = info.get("quoteType", "").lower()
        if qtype == "etf":
            return "etf"
        if qtype == "bond":
            return "bond"
        if info.get("sector"):
            return "equity"
        return "other"
