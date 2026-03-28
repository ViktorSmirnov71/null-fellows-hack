"""
Backtest Runner
Runs the allocator against historical data and computes fitness metrics.
Used by the AutoAllocator loop to evaluate proposed changes.
"""

from dataclasses import dataclass

import pandas as pd
import quantstats as qs
from loguru import logger

from ..data import YFinanceClient


@dataclass
class BacktestResult:
    sharpe_ratio: float
    sortino_ratio: float
    max_drawdown: float
    calmar_ratio: float
    tail_ratio: float
    cagr: float
    volatility: float
    win_rate: float
    var_95: float
    benchmark_sharpe: float  # 60/40 benchmark


class BacktestRunner:
    def __init__(self):
        self.yf_client = YFinanceClient()
        self._cached_prices: pd.DataFrame | None = None

    def get_prices(self, period: str = "5y") -> pd.DataFrame:
        """Get historical prices, cached for the session."""
        if self._cached_prices is None:
            self._cached_prices = self.yf_client.get_universe_prices(period=period)
        return self._cached_prices

    def run(self, risk_score: float = 0.5) -> BacktestResult:
        """Run backtest with current allocator.py settings and return fitness metrics."""
        # Import allocator dynamically so we always get the latest version
        from . import allocator

        prices = self.get_prices()
        result = allocator.run_backtest(prices, risk_score)

        # Extract returns for our strategy
        strategy_returns = result["NullFellows_Portfolio"].daily_prices.pct_change().dropna()
        benchmark_returns = result["60_40_Benchmark"].daily_prices.pct_change().dropna()

        # Compute metrics using quantstats
        return BacktestResult(
            sharpe_ratio=float(qs.stats.sharpe(strategy_returns)),
            sortino_ratio=float(qs.stats.sortino(strategy_returns)),
            max_drawdown=float(qs.stats.max_drawdown(strategy_returns)),
            calmar_ratio=float(qs.stats.calmar(strategy_returns)),
            tail_ratio=float(qs.stats.tail_ratio(strategy_returns)),
            cagr=float(qs.stats.cagr(strategy_returns)),
            volatility=float(qs.stats.volatility(strategy_returns)),
            win_rate=float(qs.stats.win_rate(strategy_returns)),
            var_95=float(qs.stats.value_at_risk(strategy_returns)),
            benchmark_sharpe=float(qs.stats.sharpe(benchmark_returns)),
        )

    def generate_tearsheet(self, output_path: str = "tearsheet.html"):
        """Generate a full QuantStats HTML tearsheet."""
        from . import allocator

        prices = self.get_prices()
        result = allocator.run_backtest(prices)

        strategy_returns = result["NullFellows_Portfolio"].daily_prices.pct_change().dropna()

        qs.reports.html(strategy_returns, benchmark="SPY", output=output_path)
        logger.info(f"Tearsheet saved to {output_path}")
