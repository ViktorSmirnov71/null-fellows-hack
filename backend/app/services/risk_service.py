from app.database import get_supabase, get_service_supabase
from app.model.schemas import RiskScore, SignalIngest
from app.cache import cache_get, cache_set
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class RiskService:

    async def ingest_signal(self, body: SignalIngest) -> dict:
        """
        Receives a processed signal from the AI engine
        (post Groq → FinBERT → Claude pipeline) and stores it.
        Also recomputes the composite risk score for that ticker.
        """
        db = get_service_supabase()

        signal_data = {
            "ticker": body.ticker,
            "source": body.source,
            "signal_type": body.direction,
            "score": body.conviction,
            "summary": body.claude_analysis or body.raw_headline or "",
            "raw_data": {
                "groq_filtered": body.groq_filtered,
                "finbert_scores": body.finbert_scores.dict() if body.finbert_scores else {},
                "second_order_effects": body.second_order_effects,
                "sector": body.sector,
                "raw_headline": body.raw_headline
            },
            "fetched_at": (body.timestamp or datetime.utcnow()).isoformat()
        }

        result = (
            db.table("research_signals")
            .insert(signal_data)
            .execute()
        )

        # Recompute and cache the composite risk score for this ticker
        await self._recompute_risk_score(body.ticker)

        return result.data[0]

    async def get_risk_score(self, ticker: str) -> RiskScore | None:
        """Single ticker risk score — checks cache first."""
        cached = await cache_get(f"risk:{ticker}")
        if cached:
            return RiskScore(**cached)

        return await self._recompute_risk_score(ticker)

    async def get_risk_scores_bulk(self, tickers: list[str]) -> dict[str, RiskScore | None]:
        """Bulk fetch for portfolio enrichment."""
        results = {}
        for ticker in tickers:
            try:
                results[ticker] = await self.get_risk_score(ticker)
            except Exception as e:
                logger.warning(f"Risk score fetch failed for {ticker}: {e}")
                results[ticker] = None
        return results

    async def get_signals_for_ticker(
        self, ticker: str, limit: int = 20
    ) -> list:
        db = get_supabase()
        return (
            db.table("research_signals")
            .select("*")
            .eq("ticker", ticker)
            .order("fetched_at", desc=True)
            .limit(limit)
            .execute()
            .data
        )

    async def get_latest_signals(self, limit: int = 50) -> list:
        """All recent signals across all tickers — for the frontend feed."""
        db = get_supabase()
        return (
            db.table("research_signals")
            .select("*")
            .order("fetched_at", desc=True)
            .limit(limit)
            .execute()
            .data
        )

    async def _recompute_risk_score(self, ticker: str) -> RiskScore | None:
        """
        Pulls the last 20 signals for a ticker and computes a
        weighted composite score broken down by source type.
        """
        db = get_service_supabase()
        signals = (
            db.table("research_signals")
            .select("*")
            .eq("ticker", ticker)
            .order("fetched_at", desc=True)
            .limit(20)
            .execute()
            .data
        )

        if not signals:
            return None

        # Group by source type
        source_groups = {
            "macro": [],       # fred
            "geo": [],         # gdelt, acled
            "sentiment": [],   # news, groq/finbert
            "conflict": [],    # acled specifically
            "supply_chain": [] # aisstream
        }

        for s in signals:
            source = s.get("source", "")
            score = s.get("score", 0)
            if source == "fred":
                source_groups["macro"].append(score)
            elif source in ("gdelt", "acled"):
                source_groups["geo"].append(score)
                if source == "acled":
                    source_groups["conflict"].append(score)
            elif source == "aisstream":
                source_groups["supply_chain"].append(score)
            else:
                source_groups["sentiment"].append(score)

        def avg(lst): return sum(lst) / len(lst) if lst else None

        macro = avg(source_groups["macro"])
        geo = avg(source_groups["geo"])
        sentiment = avg(source_groups["sentiment"])
        conflict = avg(source_groups["conflict"])
        supply = avg(source_groups["supply_chain"])

        # Weighted composite — sentiment carries most weight
        # since FinBERT scores are most reliable
        weights = {"sentiment": 0.4, "macro": 0.25, "geo": 0.2, "conflict": 0.1, "supply": 0.05}
        components = {
            "sentiment": sentiment,
            "macro": macro,
            "geo": geo,
            "conflict": conflict,
            "supply": supply
        }

        weighted_sum = sum(
            v * weights[k]
            for k, v in components.items()
            if v is not None
        )
        total_weight = sum(
            weights[k]
            for k, v in components.items()
            if v is not None
        )
        composite = round(weighted_sum / total_weight, 4) if total_weight > 0 else 0.0
        confidence = round(min(len(signals) / 20, 1.0), 2)

        risk_score = RiskScore(
            ticker=ticker,
            composite_score=composite,
            macro_component=round(macro, 4) if macro is not None else None,
            geo_component=round(geo, 4) if geo is not None else None,
            sentiment_component=round(sentiment, 4) if sentiment is not None else None,
            conflict_component=round(conflict, 4) if conflict is not None else None,
            supply_chain_component=round(supply, 4) if supply is not None else None,
            confidence=confidence,
            signal_count=len(signals),
            computed_at=datetime.utcnow()
        )

        # Cache for 15 minutes — GDELT updates every 15 min
        await cache_set(f"risk:{ticker}", risk_score.dict(), ttl_seconds=900)

        return risk_score