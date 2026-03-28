"""
Portfolio Allocator — THE AGENT-MODIFIED FILE
This is the equivalent of train.py in autoresearch.
The AI agent proposes changes to this file, backtests them, and keeps/discards.

Current allocation strategy: Risk-weighted with sentiment overlay.
"""

import bt
import pandas as pd


# === ALLOCATION WEIGHTS ===
# These weights define the portfolio allocation.
# The AutoAllocator loop will modify these based on backtesting results.

BASE_WEIGHTS = {
    # Core equity (30%)
    "SPY": 0.20,
    "VTI": 0.10,
    # Managed futures / trend-following (20%)
    "DBMF": 0.10,
    "KMLM": 0.05,
    "RPAR": 0.05,
    # CLO / structured credit (15%)
    "JAAA": 0.10,
    "CLOA": 0.05,
    # Private credit BDCs (15%)
    "ARCC": 0.08,
    "BXSL": 0.07,
    # Real assets (10%)
    "GLDM": 0.05,
    "PDBC": 0.05,
    # Bonds (10%)
    "AGG": 0.05,
    "SRLN": 0.05,
}

# === RISK REGIME ADJUSTMENTS ===
# When risk score > threshold, shift toward defensive allocations

RISK_THRESHOLD_HIGH = 0.7   # High risk: shift to defensive
RISK_THRESHOLD_LOW = 0.3    # Low risk: shift to growth

DEFENSIVE_OVERWEIGHT = ["GLDM", "AGG", "JAAA", "DBMF"]  # Increase in high-risk
GROWTH_OVERWEIGHT = ["SPY", "VTI", "ARCC", "BXSL"]       # Increase in low-risk

REGIME_SHIFT_MAGNITUDE = 0.03  # How much to shift per asset on regime change

# === REBALANCE SETTINGS ===
REBALANCE_FREQUENCY = "monthly"  # "weekly", "monthly", "quarterly"

# === SENTIMENT SIGNAL SETTINGS ===
SENTIMENT_WEIGHT = 0.15     # How much sentiment tilts allocation (0 = ignore, 1 = full)
MIN_CONVICTION = 0.3        # Minimum conviction to act on a signal


def get_weights(risk_score: float = 0.5, sentiment_signals: dict | None = None) -> dict[str, float]:
    """
    Compute final portfolio weights based on risk regime and sentiment.
    This is the function the AutoAllocator loop will evolve.
    """
    weights = BASE_WEIGHTS.copy()

    # Apply risk regime adjustment
    if risk_score > RISK_THRESHOLD_HIGH:
        for ticker in DEFENSIVE_OVERWEIGHT:
            if ticker in weights:
                weights[ticker] += REGIME_SHIFT_MAGNITUDE
        for ticker in GROWTH_OVERWEIGHT:
            if ticker in weights:
                weights[ticker] -= REGIME_SHIFT_MAGNITUDE
    elif risk_score < RISK_THRESHOLD_LOW:
        for ticker in GROWTH_OVERWEIGHT:
            if ticker in weights:
                weights[ticker] += REGIME_SHIFT_MAGNITUDE
        for ticker in DEFENSIVE_OVERWEIGHT:
            if ticker in weights:
                weights[ticker] -= REGIME_SHIFT_MAGNITUDE

    # Apply sentiment overlay
    if sentiment_signals:
        for ticker, signal in sentiment_signals.items():
            if ticker in weights and abs(signal) >= MIN_CONVICTION:
                tilt = signal * SENTIMENT_WEIGHT * REGIME_SHIFT_MAGNITUDE
                weights[ticker] = max(0.01, weights[ticker] + tilt)

    # Normalize to sum to 1.0
    total = sum(weights.values())
    weights = {k: v / total for k, v in weights.items()}

    return weights


def build_strategy(prices: pd.DataFrame, risk_score: float = 0.5) -> bt.Strategy:
    """Build a bt Strategy with current allocation weights."""
    weights = get_weights(risk_score)

    # Filter to tickers we have price data for
    available = [t for t in weights if t in prices.columns]
    filtered_weights = {t: weights[t] for t in available}

    # Re-normalize
    total = sum(filtered_weights.values())
    filtered_weights = {k: v / total for k, v in filtered_weights.items()}

    rebalance_algo = {
        "weekly": bt.algos.RunWeekly(),
        "monthly": bt.algos.RunMonthly(),
        "quarterly": bt.algos.RunQuarterly(),
    }.get(REBALANCE_FREQUENCY, bt.algos.RunMonthly())

    strategy = bt.Strategy(
        "NullFellows_Portfolio",
        [
            rebalance_algo,
            bt.algos.SelectAll(),
            bt.algos.WeighSpecified(**filtered_weights),
            bt.algos.Rebalance(),
        ],
    )

    return strategy


def run_backtest(prices: pd.DataFrame, risk_score: float = 0.5) -> bt.Result:
    """Run a full backtest with current settings. Returns bt.Result."""
    strategy = build_strategy(prices, risk_score)
    test = bt.Backtest(strategy, prices)

    # Also create a 60/40 benchmark
    benchmark = bt.Strategy(
        "60_40_Benchmark",
        [
            bt.algos.RunMonthly(),
            bt.algos.SelectAll(),
            bt.algos.WeighSpecified(SPY=0.60, AGG=0.40),
            bt.algos.Rebalance(),
        ],
    )
    benchmark_test = bt.Backtest(benchmark, prices[["SPY", "AGG"]])

    return bt.run(test, benchmark_test)
