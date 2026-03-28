"""
AutoAllocator Loop
The autonomous research loop that evolves portfolio allocations.
Adapted from karpathy/autoresearch: propose -> backtest -> keep/discard -> repeat.
"""

import csv
import os
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

from loguru import logger

from .backtest_runner import BacktestRunner

ALLOCATOR_PATH = Path(__file__).parent / "allocator.py"
EXPERIMENT_LOG = Path(__file__).parent / "experiment_log.tsv"
MAX_DRAWDOWN_LIMIT = -0.25  # Never accept a strategy with worse than -25% drawdown


class AutoAllocatorLoop:
    """
    The core autonomous loop:
    1. LLM proposes a change to allocator.py
    2. Change is applied
    3. Backtest is run (~5 min)
    4. If Sharpe improves AND max drawdown is within limits -> KEEP
    5. Otherwise -> REVERT
    6. Log result to experiment_log.tsv
    7. Repeat forever
    """

    def __init__(self):
        self.runner = BacktestRunner()
        self.best_sharpe = float("-inf")
        self.experiment_count = 0
        self._init_log()

    def _init_log(self):
        """Initialize experiment log if it doesn't exist."""
        if not EXPERIMENT_LOG.exists():
            with open(EXPERIMENT_LOG, "w", newline="") as f:
                writer = csv.writer(f, delimiter="\t")
                writer.writerow([
                    "experiment", "timestamp", "status", "sharpe", "sortino",
                    "max_drawdown", "calmar", "tail_ratio", "cagr",
                    "description", "benchmark_sharpe",
                ])

    def _log_experiment(self, status: str, result, description: str):
        """Append an experiment result to the log."""
        with open(EXPERIMENT_LOG, "a", newline="") as f:
            writer = csv.writer(f, delimiter="\t")
            writer.writerow([
                self.experiment_count,
                datetime.now(timezone.utc).isoformat(),
                status,
                f"{result.sharpe_ratio:.4f}",
                f"{result.sortino_ratio:.4f}",
                f"{result.max_drawdown:.4f}",
                f"{result.calmar_ratio:.4f}",
                f"{result.tail_ratio:.4f}",
                f"{result.cagr:.4f}",
                description,
                f"{result.benchmark_sharpe:.4f}",
            ])

    def _git_commit(self, message: str):
        """Commit the current state of allocator.py."""
        subprocess.run(["git", "add", str(ALLOCATOR_PATH)], check=True)
        subprocess.run(["git", "commit", "-m", message], check=True)

    def _git_revert(self):
        """Revert allocator.py to the last committed state."""
        subprocess.run(["git", "checkout", str(ALLOCATOR_PATH)], check=True)

    def evaluate_current(self) -> float:
        """Run backtest on current allocator.py and return Sharpe ratio."""
        result = self.runner.run()
        logger.info(
            f"Current performance: Sharpe={result.sharpe_ratio:.4f}, "
            f"MaxDD={result.max_drawdown:.4f}, "
            f"Benchmark Sharpe={result.benchmark_sharpe:.4f}"
        )
        self.best_sharpe = result.sharpe_ratio
        return result.sharpe_ratio

    def evaluate_and_decide(self, description: str) -> bool:
        """
        After a change has been applied to allocator.py:
        - Run backtest
        - If improved: keep and commit
        - If worse: revert
        Returns True if change was kept.
        """
        self.experiment_count += 1
        logger.info(f"Experiment #{self.experiment_count}: {description}")

        try:
            result = self.runner.run()
        except Exception as e:
            logger.error(f"Backtest crashed: {e}")
            self._git_revert()
            self._log_experiment("CRASH", _dummy_result(), description)
            return False

        improved = (
            result.sharpe_ratio > self.best_sharpe
            and result.max_drawdown > MAX_DRAWDOWN_LIMIT
        )

        if improved:
            self.best_sharpe = result.sharpe_ratio
            self._git_commit(f"autoallocator: {description} (Sharpe {result.sharpe_ratio:.4f})")
            self._log_experiment("KEPT", result, description)
            logger.info(
                f"KEPT: Sharpe {result.sharpe_ratio:.4f} "
                f"(+{result.sharpe_ratio - self.best_sharpe:.4f})"
            )
            return True
        else:
            self._git_revert()
            self._log_experiment("DISCARDED", result, description)
            logger.info(
                f"DISCARDED: Sharpe {result.sharpe_ratio:.4f} "
                f"(best={self.best_sharpe:.4f})"
            )
            return False


def _dummy_result():
    """Placeholder result for crashed experiments."""
    from .backtest_runner import BacktestResult
    return BacktestResult(
        sharpe_ratio=0, sortino_ratio=0, max_drawdown=-1, calmar_ratio=0,
        tail_ratio=0, cagr=0, volatility=0, win_rate=0, var_95=0,
        benchmark_sharpe=0,
    )
