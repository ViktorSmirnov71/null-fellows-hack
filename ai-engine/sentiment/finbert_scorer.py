"""
FinBERT Sentiment Scorer
Uses ProsusAI/finBERT for financial-domain sentiment analysis.
Output: softmax probabilities -> scalar score in [-1, +1]
"""

import re
from dataclasses import dataclass

import torch
from loguru import logger
from transformers import AutoModelForSequenceClassification, AutoTokenizer


@dataclass
class FinBERTScore:
    sentiment: float  # P(positive) - P(negative), in [-1, +1]
    positive: float
    neutral: float
    negative: float
    ticker: str | None
    sector: str | None


# Common ticker patterns in headlines
TICKER_PATTERN = re.compile(r"\b([A-Z]{1,5})\b")

SECTOR_KEYWORDS = {
    "technology": ["tech", "software", "AI", "semiconductor", "chip", "cloud", "SaaS"],
    "energy": ["oil", "gas", "energy", "crude", "OPEC", "pipeline", "solar", "wind"],
    "financials": ["bank", "financial", "lending", "credit", "insurance", "fintech"],
    "healthcare": ["pharma", "biotech", "drug", "FDA", "health", "medical", "hospital"],
    "consumer": ["retail", "consumer", "shopping", "e-commerce", "brand"],
    "industrials": ["manufacturing", "industrial", "construction", "aerospace", "defense"],
    "materials": ["mining", "metals", "gold", "copper", "lithium", "steel"],
    "real_estate": ["real estate", "REIT", "housing", "mortgage", "property"],
    "utilities": ["utility", "electric", "water", "power grid"],
    "crypto": ["bitcoin", "crypto", "ethereum", "blockchain", "DeFi"],
}


class FinBERTScorer:
    def __init__(self, model_name: str = "ProsusAI/finbert"):
        logger.info(f"Loading FinBERT model: {model_name}")
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModelForSequenceClassification.from_pretrained(model_name)
        self.model.eval()
        logger.info("FinBERT model loaded")

    def score(self, text: str) -> FinBERTScore:
        """Score a single text. Returns sentiment in [-1, +1]."""
        inputs = self.tokenizer(text, return_tensors="pt", truncation=True, max_length=512)

        with torch.no_grad():
            outputs = self.model(**inputs)
            probs = torch.nn.functional.softmax(outputs.logits, dim=-1)[0]

        positive = probs[0].item()
        negative = probs[1].item()
        neutral = probs[2].item()

        return FinBERTScore(
            sentiment=positive - negative,
            positive=positive,
            neutral=neutral,
            negative=negative,
            ticker=self._extract_ticker(text),
            sector=self._extract_sector(text),
        )

    def score_batch(self, articles: list) -> list[tuple]:
        """Score a batch of articles. Returns list of (article, score) tuples."""
        results = []
        for article in articles:
            text = f"{article.title}. {article.body[:500]}" if article.body else article.title
            score = self.score(text)
            results.append((article, score))
        return results

    def _extract_ticker(self, text: str) -> str | None:
        """Naive ticker extraction from text. Returns first plausible ticker."""
        matches = TICKER_PATTERN.findall(text)
        # Filter out common English words that look like tickers
        noise = {"THE", "AND", "FOR", "BUT", "NOT", "YOU", "ALL", "CAN", "HER", "WAS", "ONE", "OUR", "OUT", "ARE", "HAS", "HIS", "HOW", "ITS", "MAY", "NEW", "NOW", "OLD", "SEE", "WAY", "WHO", "DID", "GET", "LET", "SAY", "SHE", "TOO", "USE"}
        for match in matches:
            if match not in noise and len(match) >= 2:
                return match
        return None

    def _extract_sector(self, text: str) -> str | None:
        """Extract sector from text based on keyword matching."""
        text_lower = text.lower()
        for sector, keywords in SECTOR_KEYWORDS.items():
            if any(kw.lower() in text_lower for kw in keywords):
                return sector
        return None
