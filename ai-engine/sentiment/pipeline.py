"""
Sentiment Analysis Pipeline
Three-tier cascade: Groq (speed) -> FinBERT (accuracy) -> Claude (deep reasoning)
"""

import asyncio
import os
from dataclasses import dataclass
from datetime import datetime

from dotenv import load_dotenv
from loguru import logger

from .finbert_scorer import FinBERTScorer
from .groq_filter import GroqFilter
from .claude_analyst import ClaudeAnalyst
from .signal_aggregator import SignalAggregator


@dataclass
class RawArticle:
    title: str
    body: str
    source: str
    published_at: datetime
    url: str


@dataclass
class SentimentSignal:
    ticker: str | None
    sector: str | None
    direction: float        # -1.0 to +1.0
    conviction: float       # 0.0 to 1.0
    timestamp: datetime
    source_headline: str
    reasoning: str | None = None


# ── FinBERT singleton ─────────────────────────────────────────────────────────
# Loaded once per process lifetime. Every SentimentPipeline instance
# reuses the same model — never loads 400MB from disk twice.
_finbert_instance: FinBERTScorer | None = None

def _get_finbert() -> FinBERTScorer:
    global _finbert_instance
    if _finbert_instance is None:
        _finbert_instance = FinBERTScorer()
    return _finbert_instance
# ─────────────────────────────────────────────────────────────────────────────


class SentimentPipeline:
    """
    Three-tier sentiment cascade:
    1. Groq + Llama 3: Fast pre-filter (is this financially relevant?)
    2. FinBERT: Domain-specific sentiment scoring
    3. Claude: Deep analysis on high-magnitude signals only
    """

    def __init__(
        self,
        groq_api_key: str | None = None,
        anthropic_api_key: str | None = None,
        claude_threshold: float = 0.7,
    ):
        # Moved from module level — load_dotenv now runs when the pipeline
        # is instantiated, not when the file is imported. Returns True if
        # a .env file was found, False if not — log a warning so we know.
        loaded = load_dotenv()
        if not loaded:
            logger.warning(
                "No .env file found — relying on system environment variables"
            )

        self.groq_filter = GroqFilter(
            api_key=groq_api_key or os.getenv("GROQ_API_KEY")
        )
        self.finbert = _get_finbert()       # singleton — never loads twice
        self.claude = ClaudeAnalyst(
            api_key=anthropic_api_key or os.getenv("ANTHROPIC_API_KEY")
        )
        self.aggregator = SignalAggregator()
        self.claude_threshold = claude_threshold

    async def process_articles(self, articles: list[RawArticle]) -> list[SentimentSignal]:
        """Process a batch of articles through the full pipeline."""

        # Stage 1: Groq fast filter — concurrent internally (fixed in groq_filter.py)
        logger.info(f"Stage 1: Filtering {len(articles)} articles via Groq")
        relevant = await self.groq_filter.filter_relevant(articles)
        logger.info(
            f"Stage 1 complete: {len(relevant)}/{len(articles)} articles relevant"
        )

        # Stage 2: FinBERT — CPU-bound, batched internally (fixed in finbert_scorer.py)
        logger.info(f"Stage 2: Scoring {len(relevant)} articles via FinBERT")
        scored = self.finbert.score_batch(relevant)
        logger.info(f"Stage 2 complete: {len(scored)} scored")

        # First pass — build all signals, collect which need Claude
        # No awaiting here — pure CPU work
        signals: list[SentimentSignal] = []
        needs_claude: list[tuple] = []

        for article, score in scored:
            signal = SentimentSignal(
                ticker=score.ticker,
                sector=score.sector,
                direction=score.sentiment,
                conviction=abs(score.sentiment),
                timestamp=article.published_at,
                source_headline=article.title,
            )
            signals.append(signal)

            if abs(score.sentiment) >= self.claude_threshold:
                needs_claude.append((signal, article, score))

        # Stage 3 — fire ALL Claude calls concurrently in one gather
        # Time cost = one Claude call, regardless of how many signals qualify
        if needs_claude:
            logger.info(
                f"Stage 3: Deep analysis on {len(needs_claude)} "
                f"high-conviction signals"
            )
            reasonings = await asyncio.gather(
                *[
                    self.claude.analyze(article, score)
                    for _, article, score in needs_claude
                ],
                return_exceptions=True
            )
            for (signal, _, _), reasoning in zip(needs_claude, reasonings):
                if isinstance(reasoning, str):
                    signal.reasoning = reasoning
                elif isinstance(reasoning, Exception):
                    logger.error(
                        f"Claude failed for {signal.ticker}: {reasoning}"
                    )

        aggregated = self.aggregator.aggregate(signals)
        logger.info(f"Pipeline complete: {len(aggregated)} aggregated signals")
        return aggregated