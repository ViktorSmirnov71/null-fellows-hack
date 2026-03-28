import httpx
from app.config import settings

class AIservice:

    def __init__(self):
        self.base_url = settings.ai_url
        self.headers = {}
        if settings.ai_api:
            self.headers["Authorization"] = f"Bearer {settings.ai_api}"

    async def get_portfolio_recommendation(
        self,
        portfolio: dict,
        market_data: dict,
        research_signals: list[dict]
    ) -> dict:
        """
        Send current portfolio state + market data + research signals
        to the AI model, get back recommended target weights.

        Expected response:
        {
            "target_weights": {"AAPL": 0.30, "MSFT": 0.20, ...},
            "reasoning": "string",
            "confidence": 0.85
        }
        """
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{self.base_url}/recommend",
                headers=self.headers,
                json={
                    "portfolio": portfolio,
                    "market_data": market_data,
                    "research_signals": research_signals
                }
            )
            resp.raise_for_status()
            return resp.json()

    async def score_research(self, raw_research: str, ticker: str) -> dict:
        """
        Send raw Kùrthapy research text to the AI model for scoring.

        Expected response:
        {
            "score": 0.75,
            "signal_type": "bullish",
            "summary": "string"
        }
        """
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{self.base_url}/score-research",
                headers=self.headers,
                json={
                    "ticker": ticker,
                    "research": raw_research
                }
            )
            resp.raise_for_status()
            return resp.json()

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{self.base_url}/health")
                return resp.status_code == 200
        except Exception:
            return False