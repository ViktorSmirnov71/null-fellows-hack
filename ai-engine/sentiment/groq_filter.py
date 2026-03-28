"""
Groq Fast Filter
Uses Groq's LPU for sub-second classification of article financial relevance.
"""

import json
import asyncio
from groq import AsyncGroq
from loguru import logger


SYSTEM_PROMPT = """You are a financial relevance classifier. Given a news article headline and snippet,
determine if it is relevant to financial markets, investing, economics, or geopolitical events that
could impact markets.

Respond with JSON only: {"relevant": true/false, "reason": "brief reason"}"""


class GroqFilter:
    def __init__(self, api_key: str | None = None, model: str = "llama-3.3-70b-versatile"):
        self.client = AsyncGroq(api_key=api_key) if api_key else None
        self.model = model

    async def filter_relevant(self, articles: list) -> list:
        """Filter articles to only financially relevant ones."""
        if not self.client:
            logger.warning("No Groq API key — skipping filter, passing all articles through")
            return articles

        relevant = []
        for article in articles:
            try:
                response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": f"Headline: {article.title}\nSnippet: {(article.body or '')[:300]}"},
                    ],
                    temperature=0,
                    max_tokens=100,
                    response_format={"type": "json_object"},
                )
                result = json.loads(response.choices[0].message.content)
                if result.get("relevant", False):
                    relevant.append(article)
            except Exception as e:
                logger.error(f"Groq filter error for '{article.title[:50]}': {e}")
                relevant.append(article)  # On error, include the article

        return relevant
