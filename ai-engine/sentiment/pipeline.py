"""
Sentiment Analysis Pipeline
Three-tier cascade: Groq (speed) -> FinBERT (accuracy) -> Claude (deep reasoning)
"""

import os
from dataclasses import dataclass
from datetime import datetime

from dotenv import load_dotenv
from loguru import logger

from .finbert_scorer import FinBERTScorer
from .groq_filter import GroqFilter
from .claude_analyst import ClaudeAnalyst
from .signal_aggregator import SignalAggregator

load_dotenv()


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
    direction: float  # -1.0 to +1.0
    conviction: float  # 0.0 to 1.0
    timestamp: datetime
    source_headline: str
    reasoning: str | None = None


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
        self.groq_filter = GroqFilter(api_key=groq_api_key or os.getenv("GROQ_API_KEY"))
        self.finbert = FinBERTScorer()
        self.claude = ClaudeAnalyst(api_key=anthropic_api_key or os.getenv("ANTHROPIC_API_KEY"))
        self.aggregator = SignalAggregator()
        self.claude_threshold = claude_threshold

    async def process_articles(self, articles: list[RawArticle]) -> list[SentimentSignal]:
        """Process a batch of articles through the full pipeline."""
        signals = []

        # Stage 1: Groq fast filter — keep only financially relevant articles
        logger.info(f"Stage 1: Filtering {len(articles)} articles via Groq")
        relevant = await self.groq_filter.filter_relevant(articles)
        logger.info(f"Stage 1 complete: {len(relevant)}/{len(articles)} articles are financially relevant")

        # Stage 2: FinBERT scoring on relevant articles
        logger.info(f"Stage 2: Scoring {len(relevant)} articles via FinBERT")
        scored = self.finbert.score_batch(relevant)
        logger.info(f"Stage 2 complete: scored {len(scored)} articles")

        for article, score in scored:
            signal = SentimentSignal(
                ticker=score.ticker,
                sector=score.sector,
                direction=score.sentiment,  # P(positive) - P(negative)
                conviction=abs(score.sentiment),
                timestamp=article.published_at,
                source_headline=article.title,
            )

            # Stage 3: Claude deep analysis on high-conviction signals only
            if abs(score.sentiment) >= self.claude_threshold:
                logger.info(f"Stage 3: Deep analysis on '{article.title[:60]}...'")
                reasoning = await self.claude.analyze(article, score)
                signal.reasoning = reasoning

            signals.append(signal)

        # Aggregate signals per ticker/sector with time-weighting
        aggregated = self.aggregator.aggregate(signals)
        logger.info(f"Pipeline complete: {len(aggregated)} aggregated signals")

        return aggregated
