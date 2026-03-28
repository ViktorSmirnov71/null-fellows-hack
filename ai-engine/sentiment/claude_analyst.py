"""
Claude Deep Analyst
Used only for high-magnitude signals — analyzes second-order market effects.
"""

import anthropic
from loguru import logger


SYSTEM_PROMPT = """You are a senior financial analyst. Given a news article and its sentiment score,
analyze the second-order effects on financial markets. Be specific about:
1. Which sectors/tickers are most affected
2. The direction and magnitude of expected impact
3. The time horizon (immediate, short-term, medium-term)
4. Any non-obvious knock-on effects

Keep your analysis to 2-3 sentences. Be concrete, not generic."""


class ClaudeAnalyst:
    def __init__(self, api_key: str | None = None):
        self.client = anthropic.AsyncAnthropic(api_key=api_key) if api_key else None

    async def analyze(self, article, score) -> str | None:
        """Deep analysis on a high-conviction signal."""
        if not self.client:
            logger.warning("No Anthropic API key — skipping deep analysis")
            return None

        try:
            message = await self.client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=300,
                system=SYSTEM_PROMPT,
                messages=[
                    {
                        "role": "user",
                        "content": (
                            f"Headline: {article.title}\n"
                            f"Source: {article.source}\n"
                            f"Snippet: {(article.body or '')[:500]}\n"
                            f"FinBERT sentiment: {score.sentiment:+.3f} "
                            f"(pos={score.positive:.3f}, neg={score.negative:.3f}, neu={score.neutral:.3f})\n"
                            f"Detected sector: {score.sector or 'unknown'}\n"
                            f"Detected ticker: {score.ticker or 'none'}"
                        ),
                    }
                ],
                timeout=15.0,
            )

            if not message.content:
                logger.warning(f"Claude returned empty content for '{article.title[:50]}'")
                return None

            return message.content[0].text

        except anthropic.APITimeoutError:
            logger.warning(f"Claude timed out for '{article.title[:50]}' — skipping")
            return None
        except anthropic.RateLimitError:
            logger.warning("Claude rate limit hit — skipping deep analysis for this batch")
            return None
        except Exception as e:
            logger.error(f"Claude analysis error: {e}")
            return None
