"""
Composite Risk Scorer
Combines signals from GDELT, FRED, and other sources into a single risk score.
"""

from dataclasses import dataclass

from loguru import logger

from .fred_client import FREDClient
from .gdelt_client import GDELTClient


@dataclass
class RiskScore:
    """Composite risk score. Higher = more risk = shift to defensive allocations."""
    total: float  # 0.0 (calm) to 1.0 (crisis)
    geopolitical: float
    macro: float
    volatility: float
    components: dict[str, float]


# Weights for composite score
WEIGHTS = {
    "gdelt_tone": 0.20,
    "gdelt_volume": 0.15,
    "yield_inversion": 0.20,
    "vix": 0.20,
    "consumer_sentiment": 0.10,
    "unemployment_trend": 0.15,
}


class RiskScorer:
    def __init__(self, fred_client: FREDClient, gdelt_client: GDELTClient):
        self.fred = fred_client
        self.gdelt = gdelt_client

    def compute(self, regions: list[str] | None = None) -> RiskScore:
        """Compute the composite risk score from all data sources."""
        components = {}

        # GDELT: global tone and volume
        try:
            gdelt_signal = self.gdelt.get_country_risk_signal("US", timespan="7d")
            # Normalize tone: very negative (-10) maps to 1.0, neutral (0) maps to 0.5
            components["gdelt_tone"] = max(0, min(1, 0.5 - gdelt_signal["tone_avg"] / 20))
            # Normalize volume: higher volume = higher risk signal
            components["gdelt_volume"] = min(1, gdelt_signal["volume_avg"] * 10)
        except Exception as e:
            logger.error(f"GDELT risk component failed: {e}")
            components["gdelt_tone"] = 0.5
            components["gdelt_volume"] = 0.5

        # FRED: yield curve, VIX, consumer sentiment, unemployment
        try:
            macro = self.fred.get_macro_snapshot()

            # Yield curve inversion: negative spread = high recession risk
            if macro.yield_spread is not None:
                components["yield_inversion"] = max(0, min(1, 0.5 - macro.yield_spread / 4))
            else:
                components["yield_inversion"] = 0.5

            # VIX: >30 = crisis, <15 = calm
            if macro.vix is not None:
                components["vix"] = max(0, min(1, (macro.vix - 12) / 30))
            else:
                components["vix"] = 0.5

            # Consumer sentiment: lower = worse
            if macro.consumer_sentiment is not None:
                components["consumer_sentiment"] = max(0, min(1, 1 - macro.consumer_sentiment / 100))
            else:
                components["consumer_sentiment"] = 0.5

            # Unemployment: higher = worse
            if macro.unemployment is not None:
                components["unemployment_trend"] = max(0, min(1, macro.unemployment / 10))
            else:
                components["unemployment_trend"] = 0.5

        except Exception as e:
            logger.error(f"FRED risk components failed: {e}")
            for key in ["yield_inversion", "vix", "consumer_sentiment", "unemployment_trend"]:
                components[key] = 0.5

        # Compute weighted total
        total = sum(components.get(k, 0.5) * v for k, v in WEIGHTS.items())

        return RiskScore(
            total=total,
            geopolitical=(components.get("gdelt_tone", 0.5) + components.get("gdelt_volume", 0.5)) / 2,
            macro=(components.get("yield_inversion", 0.5) + components.get("consumer_sentiment", 0.5) + components.get("unemployment_trend", 0.5)) / 3,
            volatility=components.get("vix", 0.5),
            components=components,
        )
