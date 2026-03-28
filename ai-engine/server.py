"""
Parallax Intelligence API Server — Live AutoAllocator
Runs a real optimization loop in the background that evolves portfolio weights
by backtesting allocation changes against Yahoo Finance historical data.
"""

import os
import time
import threading
import random
import copy
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv(".env.local")
load_dotenv(".env")

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import yfinance as yf
import requests
import bt
import quantstats as qs
import pandas as pd

app = FastAPI(title="Parallax Intelligence API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET"], allow_headers=["*"])

# ── Shared State (thread-safe via GIL for reads, lock for writes) ────────────

INITIAL_INVESTMENT = 700000

TICKER_INFO = {
    "SPY":  {"name": "S&P 500 ETF",           "class": "Equity",           "color": "#3498db"},
    "VTI":  {"name": "Total Stock Market",     "class": "Equity",           "color": "#2980b9"},
    "DBMF": {"name": "Managed Futures",        "class": "Managed Futures",  "color": "#9b59b6"},
    "KMLM": {"name": "Mount Lucas Futures",    "class": "Managed Futures",  "color": "#8e44ad"},
    "RPAR": {"name": "Risk Parity",            "class": "Managed Futures",  "color": "#7d3c98"},
    "JAAA": {"name": "AAA CLO ETF",            "class": "Structured Credit","color": "#1abc9c"},
    "CLOA": {"name": "iShares AAA CLO",        "class": "Structured Credit","color": "#16a085"},
    "ARCC": {"name": "Ares Capital",           "class": "Private Credit",   "color": "#e67e22"},
    "BXSL": {"name": "Blackstone Lending",     "class": "Private Credit",   "color": "#d35400"},
    "GLDM": {"name": "Gold MiniShares",        "class": "Real Assets",      "color": "#f1c40f"},
    "PDBC": {"name": "Diversified Commodity",  "class": "Real Assets",      "color": "#f39c12"},
    "AGG":  {"name": "US Aggregate Bond",      "class": "Fixed Income",     "color": "#95a5a6"},
    "SRLN": {"name": "Senior Loan ETF",        "class": "Fixed Income",     "color": "#7f8c8d"},
}

# Live mutable state
state_lock = threading.Lock()

live_weights = {
    "SPY": 0.20, "VTI": 0.10, "DBMF": 0.10, "KMLM": 0.05, "RPAR": 0.05,
    "JAAA": 0.10, "CLOA": 0.05, "ARCC": 0.08, "BXSL": 0.07,
    "GLDM": 0.05, "PDBC": 0.05, "AGG": 0.05, "SRLN": 0.05,
}

live_metrics = {
    "sharpe": 0.0, "sortino": 0.0, "cagr": 0.0, "maxDrawdown": 0.0,
    "volatility": 0.0, "calmar": 0.0, "winRate": 0.0,
}

live_experiments: list[dict] = []
optimizer_status = {"running": False, "iteration": 0, "best_sharpe": 0.0, "benchmark_sharpe": 0.0}

# Price cache
price_cache: dict = {}
price_cache_time: float = 0
PRICE_TTL = 120

# 7-day price history for portfolio valuation
seven_day_prices: pd.DataFrame | None = None
seven_day_cache_time: float = 0

# Historical data cache (loaded once)
hist_data: pd.DataFrame | None = None


# ── Data Fetching ────────────────────────────────────────────────────────────

def get_seven_day_data() -> pd.DataFrame | None:
    """Get last 10 trading days of data for portfolio valuation."""
    global seven_day_prices, seven_day_cache_time
    if time.time() - seven_day_cache_time < 300 and seven_day_prices is not None:
        return seven_day_prices
    tickers = list(TICKER_INFO.keys())
    try:
        raw = yf.download(tickers, period="10d", auto_adjust=True, progress=False)["Close"].ffill().dropna()
        seven_day_prices = raw
        seven_day_cache_time = time.time()
        return raw
    except Exception:
        return seven_day_prices


def compute_portfolio_value(weights: dict) -> dict:
    """
    Compute the dynamic portfolio value as if £700K was invested 7 days ago
    with the given weights, based on real market returns.
    Returns: {current_value, pnl, pnl_pct, daily_values: [{date, value}]}
    """
    data = get_seven_day_data()
    if data is None or len(data) < 2:
        return {"current_value": INITIAL_INVESTMENT, "pnl": 0, "pnl_pct": 0, "daily_values": []}

    avail = [t for t in weights if t in data.columns and weights[t] > 0.005]
    if not avail:
        return {"current_value": INITIAL_INVESTMENT, "pnl": 0, "pnl_pct": 0, "daily_values": []}

    w = {t: weights[t] for t in avail}
    tot = sum(w.values())
    w = {k: v / tot for k, v in w.items()}

    # Compute daily weighted portfolio returns
    returns = data[avail].pct_change().dropna()
    portfolio_returns = sum(returns[t] * w[t] for t in avail)

    # Build cumulative value series
    cumulative = (1 + portfolio_returns).cumprod()
    daily_values = []
    for date, cum_ret in cumulative.items():
        daily_values.append({
            "date": date.strftime("%Y-%m-%d"),
            "value": round(INITIAL_INVESTMENT * float(cum_ret)),
        })

    current_value = round(INITIAL_INVESTMENT * float(cumulative.iloc[-1]))
    pnl = current_value - INITIAL_INVESTMENT
    pnl_pct = round((pnl / INITIAL_INVESTMENT) * 100, 2)

    return {
        "current_value": current_value,
        "pnl": pnl,
        "pnl_pct": pnl_pct,
        "daily_values": daily_values,
    }


def load_historical():
    """Load 3 years of daily closes for all tickers."""
    global hist_data
    tickers = list(TICKER_INFO.keys())
    print("[Data] Downloading 3 years of historical data...")
    raw = yf.download(tickers, period="3y", auto_adjust=True, progress=False)["Close"]
    hist_data = raw.ffill().dropna()
    print(f"[Data] Loaded {len(hist_data)} days, {len(hist_data.columns)} tickers")


def get_live_prices() -> dict:
    global price_cache, price_cache_time
    if time.time() - price_cache_time < PRICE_TTL and price_cache:
        return price_cache
    tickers = list(TICKER_INFO.keys())
    result = {}
    try:
        data = yf.download(tickers, period="5d", auto_adjust=True, progress=False, threads=True)["Close"]
        for t in tickers:
            try:
                col = data[t].dropna()
                if len(col) >= 2:
                    result[t] = {"price": round(float(col.iloc[-1]), 2), "prev": round(float(col.iloc[-2]), 2),
                                 "pct": round(((float(col.iloc[-1]) - float(col.iloc[-2])) / float(col.iloc[-2])) * 100, 2)}
                else:
                    result[t] = {"price": round(float(col.iloc[-1]), 2) if len(col) else 0, "prev": 0, "pct": 0}
            except Exception:
                result[t] = {"price": 0, "prev": 0, "pct": 0}
    except Exception:
        pass
    if result:
        price_cache = result
        price_cache_time = time.time()
    return result


# ── Backtesting Engine ───────────────────────────────────────────────────────

def run_backtest(weights: dict) -> dict | None:
    """Run a real backtest with given weights. Returns metrics dict or None on failure."""
    if hist_data is None:
        return None
    avail = [t for t in weights if t in hist_data.columns and weights[t] > 0.005]
    if len(avail) < 5:
        return None
    w = {t: weights[t] for t in avail}
    total = sum(w.values())
    w = {k: v / total for k, v in w.items()}
    try:
        strategy = bt.Strategy("test", [
            bt.algos.RunMonthly(), bt.algos.SelectAll(),
            bt.algos.WeighSpecified(**w), bt.algos.Rebalance(),
        ])
        result = bt.run(bt.Backtest(strategy, hist_data[avail]))
        ret = result["test"].daily_prices.pct_change().dropna()
        return {
            "sharpe": round(float(qs.stats.sharpe(ret)), 3),
            "sortino": round(float(qs.stats.sortino(ret)), 3),
            "cagr": round(float(qs.stats.cagr(ret) * 100), 2),
            "maxDrawdown": round(float(qs.stats.max_drawdown(ret) * 100), 2),
            "volatility": round(float(qs.stats.volatility(ret) * 100), 2),
            "calmar": round(float(qs.stats.calmar(ret)), 3),
            "winRate": round(float(qs.stats.win_rate(ret) * 100), 2),
        }
    except Exception as e:
        print(f"[Backtest] Failed: {e}")
        return None


def run_benchmark() -> dict | None:
    """Run 60/40 benchmark backtest."""
    if hist_data is None:
        return None
    try:
        bench = bt.Strategy("bench", [
            bt.algos.RunMonthly(), bt.algos.SelectAll(),
            bt.algos.WeighSpecified(SPY=0.60, AGG=0.40), bt.algos.Rebalance(),
        ])
        result = bt.run(bt.Backtest(bench, hist_data[["SPY", "AGG"]]))
        ret = result["bench"].daily_prices.pct_change().dropna()
        return {"sharpe": round(float(qs.stats.sharpe(ret)), 3)}
    except Exception:
        return None


# ── Optimizer Loop ───────────────────────────────────────────────────────────

DEFENSIVE = ["GLDM", "AGG", "JAAA", "DBMF", "KMLM"]
GROWTH = ["SPY", "VTI", "ARCC", "BXSL"]
ALL_TICKERS = list(TICKER_INFO.keys())

MUTATION_STRATEGIES = [
    "shift_pair",       # Move weight from one ticker to another
    "tilt_defensive",   # Shift toward defensive assets
    "tilt_growth",      # Shift toward growth assets
    "random_perturb",   # Small random changes to all weights
    "concentrate",      # Increase best-performing category
    "world_signal",     # React to live world events data
]

# ── World Signals Collector ──────────────────────────────────────────────────

world_signals: dict = {"signals": [], "last_updated": ""}
world_signals_lock = threading.Lock()

# Map world events to portfolio sectors
SECTOR_SENSITIVITY = {
    "energy": {"tickers": ["PDBC"], "keywords": ["oil", "crude", "opec", "gas", "energy", "pipeline", "saudi", "iran"]},
    "metals": {"tickers": ["GLDM", "PDBC"], "keywords": ["gold", "silver", "copper", "lithium", "mining", "metals", "commodity"]},
    "conflict": {"tickers": ["GLDM", "AGG", "DBMF"], "keywords": ["war", "conflict", "military", "attack", "missile", "sanctions", "invasion"]},
    "rates": {"tickers": ["AGG", "SRLN", "JAAA"], "keywords": ["fed", "rate", "yield", "treasury", "bond", "inflation", "cpi"]},
    "equity": {"tickers": ["SPY", "VTI"], "keywords": ["stocks", "rally", "selloff", "nasdaq", "s&p", "dow", "earnings", "recession"]},
    "credit": {"tickers": ["ARCC", "BXSL", "JAAA", "CLOA"], "keywords": ["credit", "lending", "default", "spread", "loan", "clo", "debt"]},
    "trade": {"tickers": ["SPY", "VTI", "PDBC"], "keywords": ["tariff", "trade war", "supply chain", "shipping", "china", "import", "export"]},
}


def collect_world_signals():
    """Background thread that collects signals from the same sources WorldMonitor uses."""
    global world_signals
    while True:
        signals = []

        # 1. GDELT: Latest financial headlines with tone scoring
        try:
            art_resp = requests.get("https://api.gdeltproject.org/api/v2/doc/doc",
                params={"query": "market economy finance oil gold conflict trade tariff",
                        "mode": "ArtList", "timespan": "12h", "maxrecords": 30, "format": "json"}, timeout=15)
            articles = art_resp.json().get("articles", [])
            for art in articles:
                title = art.get("title", "").lower()
                tone = art.get("tone", 0)
                # Match to sectors
                for sector, config in SECTOR_SENSITIVITY.items():
                    if any(kw in title for kw in config["keywords"]):
                        direction = "defensive" if tone < -3 else "growth" if tone > 3 else "neutral"
                        signals.append({
                            "source": "GDELT",
                            "sector": sector,
                            "tickers": config["tickers"],
                            "direction": direction,
                            "tone": round(tone, 1),
                            "headline": art.get("title", "")[:100],
                            "timestamp": art.get("seendate", ""),
                        })
        except Exception as e:
            print(f"[Signals] GDELT fetch failed: {e}")

        # 2. USGS: Recent significant earthquakes (infrastructure/supply chain risk)
        try:
            eq_resp = requests.get("https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/significant_week.geojson", timeout=10)
            quakes = eq_resp.json().get("features", [])
            for q in quakes[:3]:
                props = q.get("properties", {})
                mag = props.get("mag", 0)
                place = props.get("place", "")
                if mag >= 5:
                    signals.append({
                        "source": "USGS",
                        "sector": "trade",
                        "tickers": ["PDBC", "GLDM"],
                        "direction": "defensive",
                        "tone": round(-mag, 1),
                        "headline": f"M{mag:.1f} earthquake: {place}",
                        "timestamp": datetime.fromtimestamp(props.get("time", 0) / 1000, tz=timezone.utc).isoformat(),
                    })
        except Exception:
            pass

        # 3. Commodity prices from Yahoo Finance (oil, gold spot changes)
        try:
            commodity_tickers = {"GC=F": "Gold", "CL=F": "Crude Oil", "SI=F": "Silver", "NG=F": "Natural Gas"}
            cdata = yf.download(list(commodity_tickers.keys()), period="2d", auto_adjust=True, progress=False)["Close"]
            for sym, name in commodity_tickers.items():
                try:
                    col = cdata[sym].dropna()
                    if len(col) >= 2:
                        pct = ((float(col.iloc[-1]) - float(col.iloc[-2])) / float(col.iloc[-2])) * 100
                        if abs(pct) > 1:  # Only significant moves
                            sector = "energy" if sym in ["CL=F", "NG=F"] else "metals"
                            signals.append({
                                "source": "Yahoo Finance",
                                "sector": sector,
                                "tickers": SECTOR_SENSITIVITY[sector]["tickers"],
                                "direction": "growth" if pct > 0 else "defensive",
                                "tone": round(pct, 1),
                                "headline": f"{name} {'+' if pct > 0 else ''}{pct:.1f}% today",
                                "timestamp": datetime.now(timezone.utc).isoformat(),
                            })
                except Exception:
                    pass
        except Exception:
            pass

        # 4. VIX from Yahoo Finance (fear gauge)
        try:
            vix_data = yf.download("^VIX", period="2d", auto_adjust=True, progress=False)["Close"].dropna()
            if len(vix_data) >= 1:
                vix_val = float(vix_data.iloc[-1])
                if vix_val > 25:
                    signals.append({
                        "source": "Yahoo Finance",
                        "sector": "equity",
                        "tickers": ["GLDM", "AGG", "DBMF"],
                        "direction": "defensive",
                        "tone": round(-vix_val / 5, 1),
                        "headline": f"VIX at {vix_val:.1f} — elevated volatility",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    })
                elif vix_val < 15:
                    signals.append({
                        "source": "Yahoo Finance",
                        "sector": "equity",
                        "tickers": ["SPY", "VTI", "ARCC"],
                        "direction": "growth",
                        "tone": round(3, 1),
                        "headline": f"VIX at {vix_val:.1f} — low volatility, risk-on",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    })
        except Exception:
            pass

        # Deduplicate and keep the strongest signals
        seen = set()
        unique = []
        for s in signals:
            key = s["headline"][:50]
            if key not in seen:
                seen.add(key)
                unique.append(s)
        unique.sort(key=lambda s: abs(s["tone"]), reverse=True)

        with world_signals_lock:
            world_signals = {
                "signals": unique[:20],
                "last_updated": datetime.now(timezone.utc).isoformat(),
                "defensive_count": sum(1 for s in unique if s["direction"] == "defensive"),
                "growth_count": sum(1 for s in unique if s["direction"] == "growth"),
                "neutral_count": sum(1 for s in unique if s["direction"] == "neutral"),
            }

        print(f"[Signals] Collected {len(unique)} signals: {world_signals['defensive_count']} defensive, {world_signals['growth_count']} growth, {world_signals['neutral_count']} neutral")
        time.sleep(180)  # Refresh every 3 minutes


signals_thread = threading.Thread(target=collect_world_signals, daemon=True)
signals_thread.start()


def propose_change(current_weights: dict, experiment_history: list) -> tuple[dict, str]:
    """Propose a weight change. Returns (new_weights, description)."""
    w = copy.deepcopy(current_weights)
    strategy = random.choice(MUTATION_STRATEGIES)

    if strategy == "shift_pair":
        src = random.choice([t for t in ALL_TICKERS if w.get(t, 0) > 0.03])
        dst = random.choice([t for t in ALL_TICKERS if t != src])
        shift = round(random.uniform(0.02, 0.06), 2)
        shift = min(shift, w[src] - 0.01)
        w[src] -= shift
        w[dst] = w.get(dst, 0) + shift
        desc = f"Shift {shift*100:.0f}% from {src} to {dst}"

    elif strategy == "tilt_defensive":
        shift = round(random.uniform(0.01, 0.03), 2)
        targets = random.sample(DEFENSIVE, min(3, len(DEFENSIVE)))
        sources = random.sample(GROWTH, min(3, len(GROWTH)))
        for t in targets:
            w[t] = w.get(t, 0) + shift
        for s in sources:
            w[s] = max(0.01, w.get(s, 0) - shift)
        desc = f"Defensive tilt: +{shift*100:.0f}% to {','.join(targets)}"

    elif strategy == "tilt_growth":
        shift = round(random.uniform(0.01, 0.03), 2)
        targets = random.sample(GROWTH, min(3, len(GROWTH)))
        sources = random.sample(DEFENSIVE, min(3, len(DEFENSIVE)))
        for t in targets:
            w[t] = w.get(t, 0) + shift
        for s in sources:
            w[s] = max(0.01, w.get(s, 0) - shift)
        desc = f"Growth tilt: +{shift*100:.0f}% to {','.join(targets)}"

    elif strategy == "random_perturb":
        for t in ALL_TICKERS:
            w[t] = max(0.01, w.get(t, 0) + random.uniform(-0.02, 0.02))
        desc = "Random perturbation across all positions"

    elif strategy == "world_signal":
        # React to live world events
        with world_signals_lock:
            sigs = world_signals.get("signals", [])
        if sigs:
            sig = random.choice(sigs[:10])  # Pick from top 10 strongest signals
            shift = round(random.uniform(0.02, 0.04), 2)
            if sig["direction"] == "defensive":
                for t in sig["tickers"]:
                    if t in w:
                        w[t] += shift / len(sig["tickers"])
                src = random.choice([t for t in GROWTH if t not in sig["tickers"] and w.get(t, 0) > 0.03])
                w[src] = max(0.01, w[src] - shift)
                desc = f"World signal [{sig['source']}]: {sig['headline'][:50]} → +{shift*100:.0f}% {','.join(sig['tickers'])}"
            elif sig["direction"] == "growth":
                for t in sig["tickers"]:
                    if t in w:
                        w[t] += shift / len(sig["tickers"])
                src = random.choice([t for t in DEFENSIVE if t not in sig["tickers"] and w.get(t, 0) > 0.03])
                w[src] = max(0.01, w[src] - shift)
                desc = f"World signal [{sig['source']}]: {sig['headline'][:50]} → +{shift*100:.0f}% {','.join(sig['tickers'])}"
            else:
                desc = f"World signal [{sig['source']}]: {sig['headline'][:50]} (neutral — no action)"
        else:
            # Fallback to random perturbation if no signals yet
            for t in ALL_TICKERS:
                w[t] = max(0.01, w.get(t, 0) + random.uniform(-0.02, 0.02))
            desc = "No world signals yet — random perturbation"

    else:  # concentrate
        best_ticker = max(w, key=lambda t: w.get(t, 0))
        shift = round(random.uniform(0.02, 0.05), 2)
        worst_ticker = min(w, key=lambda t: w.get(t, 0))
        w[best_ticker] += shift
        w[worst_ticker] = max(0.01, w[worst_ticker] - shift)
        desc = f"Concentrate: +{shift*100:.0f}% {best_ticker}, -{shift*100:.0f}% {worst_ticker}"

    # Normalize
    total = sum(w.values())
    w = {k: round(v / total, 4) for k, v in w.items()}
    return w, desc


def optimizer_loop():
    """Background thread that continuously optimizes portfolio weights."""
    global live_weights, live_metrics, live_experiments, optimizer_status

    print("[Optimizer] Starting... loading historical data")
    load_historical()

    # Run initial backtest
    initial = run_backtest(live_weights)
    bench = run_benchmark()
    if initial:
        with state_lock:
            live_metrics = initial
            optimizer_status["best_sharpe"] = initial["sharpe"]
            optimizer_status["benchmark_sharpe"] = bench["sharpe"] if bench else 0
            optimizer_status["running"] = True
        print(f"[Optimizer] Initial Sharpe: {initial['sharpe']} (benchmark: {bench['sharpe'] if bench else '?'})")

    iteration = 0
    while True:
        iteration += 1
        optimizer_status["iteration"] = iteration

        # Propose a change
        proposed_weights, description = propose_change(live_weights, live_experiments)

        # Backtest it
        result = run_backtest(proposed_weights)

        if result is None:
            exp = {"id": iteration, "status": "CRASH", "sharpe": 0, "maxDrawdown": 0,
                   "description": description, "timestamp": datetime.now(timezone.utc).isoformat()}
            with state_lock:
                live_experiments.append(exp)
            print(f"[Optimizer] #{iteration} CRASH | {description}")
            time.sleep(5)
            continue

        # Decision gate: keep if Sharpe improved and drawdown within limits
        current_best = optimizer_status["best_sharpe"]
        kept = result["sharpe"] > current_best and result["maxDrawdown"] > -25

        exp = {
            "id": iteration,
            "status": "KEPT" if kept else "DISCARDED",
            "sharpe": result["sharpe"],
            "maxDrawdown": result["maxDrawdown"],
            "description": description,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        with state_lock:
            live_experiments.append(exp)
            if kept:
                live_weights = proposed_weights
                live_metrics = result
                optimizer_status["best_sharpe"] = result["sharpe"]

        status = "KEPT" if kept else "DISCARDED"
        print(f"[Optimizer] #{iteration} {status} | Sharpe {result['sharpe']:.3f} (best {optimizer_status['best_sharpe']:.3f}) | {description}")

        # Wait between experiments (15-25 seconds)
        time.sleep(random.uniform(15, 25))


# Start optimizer in background thread
optimizer_thread = threading.Thread(target=optimizer_loop, daemon=True)
optimizer_thread.start()


# ── API Endpoints ────────────────────────────────────────────────────────────

@app.get("/api/portfolio")
def get_portfolio():
    """Live portfolio with dynamic value based on real 7-day market returns."""
    prices = get_live_prices()
    with state_lock:
        weights = copy.deepcopy(live_weights)

    # Compute dynamic portfolio value from real market data
    valuation = compute_portfolio_value(weights)
    current_value = valuation["current_value"]

    positions = []
    total_daily = 0
    for ticker, weight in weights.items():
        info = TICKER_INFO.get(ticker, {})
        pd_data = prices.get(ticker, {"price": 0, "prev": 0, "pct": 0})
        value = round(current_value * weight)
        shares = round(value / pd_data["price"], 2) if pd_data["price"] > 0 else 0
        daily_change = round(value * pd_data["pct"] / 100, 2)
        total_daily += daily_change
        positions.append({
            "ticker": ticker, "name": info.get("name", ticker),
            "weight": round(weight, 4), "value": value,
            "price": pd_data["price"], "shares": shares,
            "assetClass": info.get("class", ""), "color": info.get("color", "#888"),
            "dailyChange": daily_change, "changePct": pd_data["pct"],
        })
    return {
        "totalValue": current_value,
        "initialInvestment": INITIAL_INVESTMENT,
        "pnl": valuation["pnl"],
        "pnlPct": valuation["pnl_pct"],
        "totalDailyChange": round(total_daily, 2),
        "totalDailyChangePct": round((total_daily / max(current_value, 1)) * 100, 2),
        "dailyValues": valuation["daily_values"],
        "positions": sorted(positions, key=lambda p: p["weight"], reverse=True),
        "lastRebalance": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "dataSource": "Yahoo Finance (live)",
        "optimizerIteration": optimizer_status["iteration"],
    }


# ── Background Risk Scorer ───────────────────────────────────────────────────

live_risk = {
    "total": 0.5, "geopolitical": 0.5, "macro": 0.5, "volatility": 0.5,
    "components": {},
    "headlines": [],
    "last_updated": "",
}
risk_lock = threading.Lock()


def risk_scorer_loop():
    """Background thread that continuously updates the world risk score."""
    global live_risk
    while True:
        components = {}
        headlines = []

        # 1. GDELT: global market/economy tone (updated every 15 min)
        try:
            tone_resp = requests.get("https://api.gdeltproject.org/api/v2/doc/doc",
                params={"query": "market economy finance", "mode": "TimelineTone", "timespan": "3d", "format": "json"}, timeout=12)
            tones = [pt.get("value", 0) for s in tone_resp.json().get("timeline", []) for pt in s.get("data", [])]
            components["gdelt_market_tone"] = max(0, min(1, 0.5 - (sum(tones) / len(tones) if tones else 0) / 20))
        except Exception:
            components["gdelt_market_tone"] = 0.5

        # 2. GDELT: conflict/crisis tone
        try:
            crisis_resp = requests.get("https://api.gdeltproject.org/api/v2/doc/doc",
                params={"query": "conflict war crisis sanctions", "mode": "TimelineTone", "timespan": "3d", "format": "json"}, timeout=12)
            crisis_tones = [pt.get("value", 0) for s in crisis_resp.json().get("timeline", []) for pt in s.get("data", [])]
            components["gdelt_crisis_tone"] = max(0, min(1, 0.5 - (sum(crisis_tones) / len(crisis_tones) if crisis_tones else 0) / 15))
        except Exception:
            components["gdelt_crisis_tone"] = 0.5

        # 3. GDELT: volume spike (attention indicator)
        try:
            vol_resp = requests.get("https://api.gdeltproject.org/api/v2/doc/doc",
                params={"query": "market crash recession crisis", "mode": "TimelineVol", "timespan": "3d", "format": "json"}, timeout=12)
            vols = [pt.get("value", 0) for s in vol_resp.json().get("timeline", []) for pt in s.get("data", [])]
            components["gdelt_crisis_volume"] = min(1, (sum(vols) / len(vols) if vols else 0) * 15)
        except Exception:
            components["gdelt_crisis_volume"] = 0.3

        # 4. Recent negative headlines for display
        try:
            art_resp = requests.get("https://api.gdeltproject.org/api/v2/doc/doc",
                params={"query": "market economy finance", "mode": "ArtList", "timespan": "24h", "maxrecords": 8,
                         "sort": "ToneAsc", "format": "json"}, timeout=12)
            for a in art_resp.json().get("articles", [])[:5]:
                headlines.append({"title": a.get("title", "")[:100], "tone": round(a.get("tone", 0), 1), "source": a.get("domain", "")})
        except Exception:
            pass

        # 5. FRED data (if key available)
        fred_key = os.getenv("FRED_API_KEY")
        if fred_key:
            for series_id, key_name, transform in [
                ("VIXCLS", "vix", lambda v: max(0, min(1, (v - 12) / 30))),
                ("T10Y2Y", "yield_spread", lambda v: max(0, min(1, 0.5 - v / 4))),
                ("UMCSENT", "consumer_sentiment", lambda v: max(0, min(1, 1 - v / 100))),
                ("UNRATE", "unemployment", lambda v: max(0, min(1, v / 10))),
            ]:
                try:
                    r = requests.get("https://api.stlouisfed.org/fred/series/observations",
                        params={"series_id": series_id, "api_key": fred_key, "file_type": "json", "sort_order": "desc", "limit": 1}, timeout=8)
                    val = r.json().get("observations", [{}])[0].get("value", ".")
                    if val != ".":
                        components[key_name] = transform(float(val))
                except Exception:
                    pass

        # Without FRED, estimate volatility from recent market data
        if "vix" not in components:
            try:
                spy = yf.download("SPY", period="5d", auto_adjust=True, progress=False)["Close"].pct_change().dropna()
                recent_vol = float(spy.std()) * (252 ** 0.5) * 100  # annualized
                components["vix"] = max(0, min(1, (recent_vol - 8) / 30))
            except Exception:
                components["vix"] = 0.5

        # Composite score (weighted)
        weights = {
            "gdelt_market_tone": 0.20, "gdelt_crisis_tone": 0.15, "gdelt_crisis_volume": 0.10,
            "vix": 0.20, "yield_spread": 0.15, "consumer_sentiment": 0.10, "unemployment": 0.10,
        }
        total = sum(components.get(k, 0.5) * w for k, w in weights.items())

        geo = (components.get("gdelt_market_tone", 0.5) + components.get("gdelt_crisis_tone", 0.5) + components.get("gdelt_crisis_volume", 0.3)) / 3
        macro = (components.get("yield_spread", 0.5) + components.get("consumer_sentiment", 0.5) + components.get("unemployment", 0.5)) / 3
        vol = components.get("vix", 0.5)

        with risk_lock:
            live_risk = {
                "total": round(total, 3),
                "geopolitical": round(geo, 3),
                "macro": round(macro, 3),
                "volatility": round(vol, 3),
                "components": {k: round(v, 3) for k, v in components.items()},
                "headlines": headlines,
                "last_updated": datetime.now(timezone.utc).isoformat(),
            }

        print(f"[Risk] Updated: total={total:.3f} geo={geo:.3f} macro={macro:.3f} vol={vol:.3f} ({len(components)} signals, {len(headlines)} headlines)")

        # Refresh every 2 minutes
        time.sleep(120)


risk_thread = threading.Thread(target=risk_scorer_loop, daemon=True)
risk_thread.start()


@app.get("/api/risk")
def get_risk():
    """Live world risk score — updated every 2 minutes from GDELT + FRED."""
    with risk_lock:
        return copy.deepcopy(live_risk)


@app.get("/api/backtest")
def get_backtest():
    """Current portfolio performance metrics from real backtest."""
    with state_lock:
        metrics = copy.deepcopy(live_metrics)
    return {
        "portfolio": metrics,
        "benchmark": {"sharpe": optimizer_status["benchmark_sharpe"]},
        "initialInvestment": INITIAL_INVESTMENT,
    }


@app.get("/api/experiments")
def get_experiments():
    """Live experiment history from the running optimizer."""
    with state_lock:
        exps = copy.deepcopy(live_experiments)
    return {
        "totalExperiments": len(exps),
        "bestSharpe": optimizer_status["best_sharpe"],
        "benchmarkSharpe": optimizer_status["benchmark_sharpe"],
        "iteration": optimizer_status["iteration"],
        "running": optimizer_status["running"],
        "currentWeights": copy.deepcopy(live_weights),
        "experiments": exps[-50:],  # Last 50
    }


@app.get("/api/signals")
def get_signals():
    """Live world event signals feeding the portfolio optimizer."""
    with world_signals_lock:
        return copy.deepcopy(world_signals)


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "optimizer": "running" if optimizer_status["running"] else "starting",
        "iteration": optimizer_status["iteration"],
        "bestSharpe": optimizer_status["best_sharpe"],
    }
