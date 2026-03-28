"""
Parallax Intelligence API Server
Serves live market data, risk scores, and portfolio allocations to the frontend.
Run with: uvicorn server:app --port 8000 --reload
"""

import os
import time
import math
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv(".env.local")
load_dotenv(".env")

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import yfinance as yf
import requests

app = FastAPI(title="Parallax Intelligence API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

# ── Investment Universe ──────────────────────────────────────────────────────

UNIVERSE = {
    "SPY":  {"name": "S&P 500 ETF",           "class": "Equity",           "color": "#3498db", "weight": 0.20},
    "VTI":  {"name": "Total Stock Market",     "class": "Equity",           "color": "#2980b9", "weight": 0.10},
    "DBMF": {"name": "Managed Futures",        "class": "Managed Futures",  "color": "#9b59b6", "weight": 0.10},
    "KMLM": {"name": "Mount Lucas Futures",    "class": "Managed Futures",  "color": "#8e44ad", "weight": 0.05},
    "RPAR": {"name": "Risk Parity",            "class": "Managed Futures",  "color": "#7d3c98", "weight": 0.05},
    "JAAA": {"name": "AAA CLO ETF",            "class": "Structured Credit","color": "#1abc9c", "weight": 0.10},
    "CLOA": {"name": "iShares AAA CLO",        "class": "Structured Credit","color": "#16a085", "weight": 0.05},
    "ARCC": {"name": "Ares Capital",           "class": "Private Credit",   "color": "#e67e22", "weight": 0.08},
    "BXSL": {"name": "Blackstone Lending",     "class": "Private Credit",   "color": "#d35400", "weight": 0.07},
    "GLDM": {"name": "Gold MiniShares",        "class": "Real Assets",      "color": "#f1c40f", "weight": 0.05},
    "PDBC": {"name": "Diversified Commodity",  "class": "Real Assets",      "color": "#f39c12", "weight": 0.05},
    "AGG":  {"name": "US Aggregate Bond",      "class": "Fixed Income",     "color": "#95a5a6", "weight": 0.05},
    "SRLN": {"name": "Senior Loan ETF",        "class": "Fixed Income",     "color": "#7f8c8d", "weight": 0.05},
}

TOTAL_INVESTMENT = 10000

# ── Caches (avoid hammering APIs) ────────────────────────────────────────────

_price_cache: dict = {}
_price_cache_time: float = 0
PRICE_CACHE_TTL = 120  # seconds

_risk_cache: dict = {}
_risk_cache_time: float = 0
RISK_CACHE_TTL = 300

_gdelt_cache: dict = {}
_gdelt_cache_time: float = 0
GDELT_CACHE_TTL = 600


def _get_prices() -> dict[str, float]:
    global _price_cache, _price_cache_time
    if time.time() - _price_cache_time < PRICE_CACHE_TTL and _price_cache:
        return _price_cache
    prices = {}
    tickers = list(UNIVERSE.keys())
    try:
        data = yf.download(tickers, period="2d", auto_adjust=True, progress=False, threads=True)
        closes = data["Close"]
        for ticker in tickers:
            try:
                prices[ticker] = round(float(closes[ticker].iloc[-1]), 2)
            except Exception:
                prices[ticker] = 0
    except Exception:
        # Fallback to individual fetches
        for ticker in tickers:
            try:
                prices[ticker] = round(float(yf.Ticker(ticker).fast_info.get("lastPrice", 0)), 2)
            except Exception:
                prices[ticker] = 0
            time.sleep(0.3)
    if prices:
        _price_cache = prices
        _price_cache_time = time.time()
    return prices


def _get_gdelt_signal() -> dict:
    global _gdelt_cache, _gdelt_cache_time
    if time.time() - _gdelt_cache_time < GDELT_CACHE_TTL and _gdelt_cache:
        return _gdelt_cache
    try:
        tone_resp = requests.get(
            "https://api.gdeltproject.org/api/v2/doc/doc",
            params={"query": "market OR economy", "mode": "TimelineTone", "timespan": "7d", "format": "json"},
            timeout=15,
        )
        tone_data = tone_resp.json()
        tones = []
        for series in tone_data.get("timeline", []):
            for pt in series.get("data", []):
                tones.append(pt.get("value", 0))
        tone_avg = sum(tones) / len(tones) if tones else 0

        vol_resp = requests.get(
            "https://api.gdeltproject.org/api/v2/doc/doc",
            params={"query": "market OR economy", "mode": "TimelineVol", "timespan": "7d", "format": "json"},
            timeout=15,
        )
        vol_data = vol_resp.json()
        vols = []
        for series in vol_data.get("timeline", []):
            for pt in series.get("data", []):
                vols.append(pt.get("value", 0))
        vol_avg = sum(vols) / len(vols) if vols else 0

        result = {"tone_avg": round(tone_avg, 3), "volume_avg": round(vol_avg, 4)}
        _gdelt_cache = result
        _gdelt_cache_time = time.time()
        return result
    except Exception:
        return {"tone_avg": 0, "volume_avg": 0}


def _get_fred_value(series_id: str) -> float | None:
    """Fetch latest value from FRED. Returns None if no key or error."""
    key = os.getenv("FRED_API_KEY")
    if not key:
        return None
    try:
        resp = requests.get(
            "https://api.stlouisfed.org/fred/series/observations",
            params={
                "series_id": series_id,
                "api_key": key,
                "file_type": "json",
                "sort_order": "desc",
                "limit": 1,
            },
            timeout=10,
        )
        obs = resp.json().get("observations", [])
        if obs and obs[0].get("value", ".") != ".":
            return float(obs[0]["value"])
    except Exception:
        pass
    return None


# ── API Endpoints ────────────────────────────────────────────────────────────

@app.get("/api/portfolio")
def get_portfolio():
    """Live portfolio positions with current prices."""
    prices = _get_prices()
    positions = []
    for ticker, info in UNIVERSE.items():
        price = prices.get(ticker, 0)
        value = round(TOTAL_INVESTMENT * info["weight"])
        shares = round(value / price, 4) if price > 0 else 0
        # Simulate daily change as % of price (small random-ish based on ticker hash)
        seed = hash(ticker + datetime.now(timezone.utc).strftime("%Y-%m-%d")) % 1000
        daily_pct = (seed - 500) / 5000  # roughly -10% to +10% range / 100
        daily_change = round(value * daily_pct, 2)
        positions.append({
            "ticker": ticker,
            "name": info["name"],
            "weight": info["weight"],
            "value": value,
            "price": price,
            "shares": shares,
            "assetClass": info["class"],
            "color": info["color"],
            "dailyChange": daily_change,
        })
    return {
        "totalValue": TOTAL_INVESTMENT,
        "positions": positions,
        "lastRebalance": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
    }


@app.get("/api/risk")
def get_risk():
    """Composite risk score from GDELT + FRED."""
    global _risk_cache, _risk_cache_time
    if time.time() - _risk_cache_time < RISK_CACHE_TTL and _risk_cache:
        return _risk_cache

    gdelt = _get_gdelt_signal()

    # GDELT components
    gdelt_tone = max(0, min(1, 0.5 - gdelt["tone_avg"] / 20))
    gdelt_volume = min(1, gdelt["volume_avg"] * 10)

    # FRED components (gracefully degrade if no key)
    vix_raw = _get_fred_value("VIXCLS")
    spread_raw = _get_fred_value("T10Y2Y")
    sentiment_raw = _get_fred_value("UMCSENT")
    unemployment_raw = _get_fred_value("UNRATE")

    vix = max(0, min(1, (vix_raw - 12) / 30)) if vix_raw else 0.5
    yield_inv = max(0, min(1, 0.5 - (spread_raw or 0) / 4))
    consumer = max(0, min(1, 1 - (sentiment_raw or 50) / 100))
    unemp = max(0, min(1, (unemployment_raw or 5) / 10))

    # Weighted composite
    total = (
        0.20 * gdelt_tone
        + 0.15 * gdelt_volume
        + 0.20 * yield_inv
        + 0.20 * vix
        + 0.10 * consumer
        + 0.15 * unemp
    )

    result = {
        "total": round(total, 3),
        "geopolitical": round((gdelt_tone + gdelt_volume) / 2, 3),
        "macro": round((yield_inv + consumer + unemp) / 3, 3),
        "volatility": round(vix, 3),
        "components": {
            "gdelt_tone": round(gdelt_tone, 3),
            "gdelt_volume": round(gdelt_volume, 3),
            "yield_inversion": round(yield_inv, 3),
            "vix": round(vix, 3),
            "consumer_sentiment": round(consumer, 3),
            "unemployment_trend": round(unemp, 3),
        },
        "raw": {
            "vix": vix_raw,
            "yield_spread": spread_raw,
            "consumer_sentiment": sentiment_raw,
            "unemployment": unemployment_raw,
            "gdelt_tone": gdelt["tone_avg"],
            "gdelt_volume": gdelt["volume_avg"],
        },
    }
    _risk_cache = result
    _risk_cache_time = time.time()
    return result


@app.get("/api/macro")
def get_macro():
    """Live macro indicators from FRED."""
    return {
        "fedFundsRate": _get_fred_value("FEDFUNDS"),
        "yield10y": _get_fred_value("DGS10"),
        "yield2y": _get_fred_value("DGS2"),
        "yieldSpread": _get_fred_value("T10Y2Y"),
        "vix": _get_fred_value("VIXCLS"),
        "unemployment": _get_fred_value("UNRATE"),
        "consumerSentiment": _get_fred_value("UMCSENT"),
        "cpi": _get_fred_value("CPIAUCSL"),
    }


@app.get("/api/gdelt/articles")
def get_gdelt_articles(query: str = "market economy finance", max_records: int = 20):
    """Recent articles from GDELT for sentiment display."""
    try:
        resp = requests.get(
            "https://api.gdeltproject.org/api/v2/doc/doc",
            params={"query": query, "mode": "ArtList", "timespan": "24h", "maxrecords": max_records, "format": "json"},
            timeout=15,
        )
        data = resp.json()
        return [
            {
                "title": a.get("title", ""),
                "url": a.get("url", ""),
                "source": a.get("domain", ""),
                "tone": round(a.get("tone", 0), 2),
                "date": a.get("seendate", ""),
            }
            for a in data.get("articles", [])
        ]
    except Exception:
        return []


@app.get("/api/health")
def health():
    return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}
