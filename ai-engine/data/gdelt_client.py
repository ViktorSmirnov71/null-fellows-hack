"""
GDELT Client
Queries the GDELT DOC 2.0 API for news volume, tone, and themes.
No auth required. Updated every 15 minutes.
"""

from dataclasses import dataclass

import requests
from loguru import logger

BASE_URL = "https://api.gdeltproject.org/api/v2/doc/doc"
GEO_URL = "https://api.gdeltproject.org/api/v2/geo/geo"


@dataclass
class GDELTTonePoint:
    date: str
    tone: float  # average tone, negative = bad


@dataclass
class GDELTVolumePoint:
    date: str
    volume: float  # % of global coverage


@dataclass
class GDELTArticle:
    title: str
    url: str
    source: str
    date: str
    tone: float
    image: str | None


class GDELTClient:
    def __init__(self, timeout: int = 30):
        self.timeout = timeout

    def get_tone_timeline(
        self,
        query: str,
        timespan: str = "7d",
    ) -> list[GDELTTonePoint]:
        """Get tone timeline for a query. Falling tone = rising risk."""
        params = {
            "query": query,
            "mode": "TimelineTone",
            "timespan": timespan,
            "format": "json",
        }
        try:
            resp = requests.get(BASE_URL, params=params, timeout=self.timeout)
            resp.raise_for_status()
            data = resp.json()
            points = []
            for series in data.get("timeline", []):
                for point in series.get("data", []):
                    points.append(GDELTTonePoint(
                        date=point.get("date", ""),
                        tone=point.get("value", 0.0),
                    ))
            return points
        except Exception as e:
            logger.error(f"GDELT tone query failed: {e}")
            return []

    def get_volume_timeline(
        self,
        query: str,
        timespan: str = "7d",
    ) -> list[GDELTVolumePoint]:
        """Get volume timeline for a query. Rising volume = rising attention."""
        params = {
            "query": query,
            "mode": "TimelineVol",
            "timespan": timespan,
            "format": "json",
        }
        try:
            resp = requests.get(BASE_URL, params=params, timeout=self.timeout)
            resp.raise_for_status()
            data = resp.json()
            points = []
            for series in data.get("timeline", []):
                for point in series.get("data", []):
                    points.append(GDELTVolumePoint(
                        date=point.get("date", ""),
                        volume=point.get("value", 0.0),
                    ))
            return points
        except Exception as e:
            logger.error(f"GDELT volume query failed: {e}")
            return []

    def get_articles(
        self,
        query: str,
        timespan: str = "24h",
        max_records: int = 50,
    ) -> list[GDELTArticle]:
        """Get matching articles for sentiment analysis input."""
        params = {
            "query": query,
            "mode": "ArtList",
            "timespan": timespan,
            "maxrecords": max_records,
            "format": "json",
        }
        try:
            resp = requests.get(BASE_URL, params=params, timeout=self.timeout)
            resp.raise_for_status()
            data = resp.json()
            articles = []
            for art in data.get("articles", []):
                articles.append(GDELTArticle(
                    title=art.get("title", ""),
                    url=art.get("url", ""),
                    source=art.get("domain", ""),
                    date=art.get("seendate", ""),
                    tone=art.get("tone", 0.0),
                    image=art.get("socialimage"),
                ))
            return articles
        except Exception as e:
            logger.error(f"GDELT article query failed: {e}")
            return []

    def get_geojson(self, query: str) -> dict | None:
        """Get geographic heatmap data for map visualization."""
        params = {"query": query, "format": "GeoJSON"}
        try:
            resp = requests.get(GEO_URL, params=params, timeout=self.timeout)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.error(f"GDELT geo query failed: {e}")
            return None

    def get_country_risk_signal(self, country_code: str, timespan: str = "7d") -> dict:
        """
        Compute a risk signal for a country by combining tone change and volume change.
        Returns: {"tone_avg": float, "volume_avg": float, "risk_direction": float}
        """
        tone = self.get_tone_timeline(f"sourcecountry:{country_code}", timespan)
        volume = self.get_volume_timeline(f"sourcecountry:{country_code}", timespan)

        tone_avg = sum(p.tone for p in tone) / len(tone) if tone else 0.0
        vol_avg = sum(p.volume for p in volume) / len(volume) if volume else 0.0

        # Negative tone + high volume = high risk
        risk_direction = (-tone_avg * 0.6) + (vol_avg * 0.4)

        return {
            "tone_avg": tone_avg,
            "volume_avg": vol_avg,
            "risk_direction": risk_direction,
        }
