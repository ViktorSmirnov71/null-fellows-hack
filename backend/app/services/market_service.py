import yfinance as yf
import httpx
import logging
from datetime import datetime
from app.cache import cache_get, cache_set
from app.config import settings

logger = logging.getLogger(__name__)

# TTLs in seconds
TTL_PRICE = 300        # 5 min
TTL_HISTORY = 1800     # 30 min
TTL_SECTORS = 900      # 15 min

# Sector ETFs — maps sector name to representative ETF
SECTOR_ETFS = {
    "Technology":        "XLK",
    "Healthcare":        "XLV",
    "Financials":        "XLF",
    "Energy":            "XLE",
    "Consumer Staples":  "XLP",
    "Industrials":       "XLI",
    "Utilities":         "XLU",
    "Real Estate":       "XLRE",
    "Materials":         "XLB",
    "Communication":     "XLC",
    "Consumer Disc.":    "XLY",
}


class MarketService:

    # ─── Single price ─────────────────────────────────────────────────────────

    async def get_price(self, ticker: str) -> dict | None:
        ticker = ticker.upper()
        cache_key = f"backend:price:{ticker}"

        cached = await cache_get(cache_key)
        if cached:
            cached["from_cache"] = True
            return cached

        try:
            data = await self._fetch_yahoo_price(ticker)
            await cache_set(cache_key, data, ttl_seconds=TTL_PRICE)
            return data
        except Exception as primary_err:
            logger.warning(f"yfinance failed for {ticker}: {primary_err}")

        # Fallback to Alpha Vantage if key is available
        if settings.alpha_vantage_api_key and settings.alpha_vantage_api_key != "placeholder":
            try:
                data = await self._fetch_alpha_vantage_price(ticker)
                await cache_set(cache_key, data, ttl_seconds=TTL_PRICE)
                return data
            except Exception as fallback_err:
                logger.error(f"Alpha Vantage fallback failed for {ticker}: {fallback_err}")

        return None

    # ─── Bulk prices ──────────────────────────────────────────────────────────

    async def get_prices(self, tickers: list[str]) -> dict[str, dict | None]:
        """
        Fetches multiple tickers efficiently.
        Checks cache per ticker first, batches any misses into
        one yfinance call instead of N individual calls.
        """
        tickers = [t.upper() for t in tickers]
        results = {}
        cache_misses = []

        # Check cache for each ticker first
        for ticker in tickers:
            cached = await cache_get(f"backend:price:{ticker}")
            if cached:
                cached["from_cache"] = True
                results[ticker] = cached
            else:
                cache_misses.append(ticker)

        # Batch fetch all misses in one yfinance call
        if cache_misses:
            try:
                batch_data = await self._fetch_yahoo_bulk(cache_misses)
                for ticker, data in batch_data.items():
                    if data:
                        await cache_set(
                            f"backend:price:{ticker}",
                            data,
                            ttl_seconds=TTL_PRICE
                        )
                    results[ticker] = data
            except Exception as e:
                logger.error(f"Bulk price fetch failed: {e}")
                for ticker in cache_misses:
                    results[ticker] = None

        return results

    # ─── Price history ────────────────────────────────────────────────────────

    async def get_price_history(
        self, ticker: str, period: str = "1mo"
    ) -> dict | None:
        """
        Returns OHLCV history for charting.
        period options: 1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y
        """
        ticker = ticker.upper()
        cache_key = f"backend:history:{ticker}:{period}"

        cached = await cache_get(cache_key)
        if cached:
            return cached

        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(period=period)

            if hist.empty:
                return None

            # Format for frontend charting (d3/recharts friendly)
            candles = []
            for date, row in hist.iterrows():
                candles.append({
                    "date": date.strftime("%Y-%m-%d"),
                    "open":   round(float(row["Open"]), 2),
                    "high":   round(float(row["High"]), 2),
                    "low":    round(float(row["Low"]), 2),
                    "close":  round(float(row["Close"]), 2),
                    "volume": int(row["Volume"])
                })

            data = {
                "ticker": ticker,
                "period": period,
                "candles": candles,
                "fetched_at": datetime.utcnow().isoformat()
            }

            await cache_set(cache_key, data, ttl_seconds=TTL_HISTORY)
            return data

        except Exception as e:
            logger.error(f"History fetch failed for {ticker}: {e}")
            return None

    # ─── Sector snapshot ──────────────────────────────────────────────────────

    async def get_sector_snapshot(self) -> dict:
        """
        Returns performance of all 11 sectors using their ETFs.
        Used by the frontend sector performance panel.
        """
        cache_key = "backend:sectors"
        cached = await cache_get(cache_key)
        if cached:
            return cached

        etf_tickers = list(SECTOR_ETFS.values())
        prices = await self.get_prices(etf_tickers)

        sectors = []
        for sector_name, etf in SECTOR_ETFS.items():
            price_data = prices.get(etf)
            sectors.append({
                "sector": sector_name,
                "etf": etf,
                "price": price_data["price"] if price_data else None,
                "change_pct": price_data["change_pct"] if price_data else None,
                "performance": (
                    "up" if price_data and price_data["change_pct"] > 0
                    else "down" if price_data and price_data["change_pct"] < 0
                    else "flat"
                )
            })

        # Sort by change_pct descending for easy frontend rendering
        sectors.sort(
            key=lambda s: s["change_pct"] or 0,
            reverse=True
        )

        data = {
            "sectors": sectors,
            "best_sector": sectors[0]["sector"] if sectors else None,
            "worst_sector": sectors[-1]["sector"] if sectors else None,
            "computed_at": datetime.utcnow().isoformat()
        }

        await cache_set(cache_key, data, ttl_seconds=TTL_SECTORS)
        return data

    # ─── Private fetchers ─────────────────────────────────────────────────────

    async def _fetch_yahoo_price(self, ticker: str) -> dict:
        stock = yf.Ticker(ticker)
        info = stock.fast_info
        price = round(float(info.last_price), 2)
        prev = round(float(info.previous_close), 2)
        change_pct = round(((price - prev) / prev) * 100, 2) if prev else 0

        return {
            "ticker": ticker,
            "price": price,
            "prev_close": prev,
            "change_pct": change_pct,
            "currency": getattr(info, "currency", "USD"),
            "source": "yfinance",
            "from_cache": False,
            "fetched_at": datetime.utcnow().isoformat()
        }

    async def _fetch_yahoo_bulk(self, tickers: list[str]) -> dict[str, dict]:
        """Single yfinance call for multiple tickers."""
        results = {}
        try:
            data = yf.download(
                tickers,
                period="2d",
                auto_adjust=True,
                progress=False
            )

            # yfinance returns different shapes for 1 vs multiple tickers
            if len(tickers) == 1:
                ticker = tickers[0]
                closes = data["Close"]
                if len(closes) >= 2:
                    price = round(float(closes.iloc[-1]), 2)
                    prev = round(float(closes.iloc[-2]), 2)
                    change_pct = round(((price - prev) / prev) * 100, 2)
                    results[ticker] = {
                        "ticker": ticker,
                        "price": price,
                        "prev_close": prev,
                        "change_pct": change_pct,
                        "source": "yfinance",
                        "from_cache": False,
                        "fetched_at": datetime.utcnow().isoformat()
                    }
            else:
                closes = data["Close"]
                for ticker in tickers:
                    try:
                        price = round(float(closes[ticker].iloc[-1]), 2)
                        prev = round(float(closes[ticker].iloc[-2]), 2)
                        change_pct = round(((price - prev) / prev) * 100, 2)
                        results[ticker] = {
                            "ticker": ticker,
                            "price": price,
                            "prev_close": prev,
                            "change_pct": change_pct,
                            "source": "yfinance",
                            "from_cache": False,
                            "fetched_at": datetime.utcnow().isoformat()
                        }
                    except Exception:
                        results[ticker] = None

        except Exception as e:
            logger.error(f"yfinance bulk download failed: {e}")
            for ticker in tickers:
                results[ticker] = None

        return results

    async def _fetch_alpha_vantage_price(self, ticker: str) -> dict:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                "https://www.alphavantage.co/query",
                params={
                    "function": "GLOBAL_QUOTE",
                    "symbol": ticker,
                    "apikey": settings.alpha_vantage_api_key
                },
                timeout=10.0
            )
            quote = resp.json().get("Global Quote", {})
            price = round(float(quote["05. price"]), 2)
            prev = round(float(quote["08. previous close"]), 2)
            change_pct = round(((price - prev) / prev) * 100, 2)
            return {
                "ticker": ticker,
                "price": price,
                "prev_close": prev,
                "change_pct": change_pct,
                "source": "alpha_vantage",
                "from_cache": False,
                "fetched_at": datetime.utcnow().isoformat()
            }

async def get_macro_snapshot(self) -> dict:
    cache_key = "backend:macro:snapshot"
    cached = await cache_get(cache_key)
    if cached:
        return cached

    # Key FRED series for the demo
    series = {
        "fed_funds_rate":     "FEDFUNDS",
        "yield_10y":          "DGS10",
        "yield_2y":           "DGS2",
        "yield_spread":       "T10Y2Y",
        "cpi_yoy":            "CPIAUCSL",
        "unemployment":       "UNRATE",
        "vix":                "VIXCLS",
        "consumer_sentiment": "UMCSENT"
    }

    results = {}
    async with httpx.AsyncClient() as client:
        for name, series_id in series.items():
            try:
                resp = await client.get(
                    "https://api.stlouisfed.org/fred/series/observations",
                    params={
                        "series_id": series_id,
                        "api_key": settings.fred_api_key,
                        "sort_order": "desc",
                        "limit": 1,
                        "file_type": "json"
                    },
                    timeout=10.0
                )
                data = resp.json()
                observations = data.get("observations", [])
                value = float(observations[0]["value"]) if observations else None
                results[name] = value
            except Exception as e:
                logger.warning(f"FRED fetch failed for {series_id}: {e}")
                results[name] = None

    # Compute yield spread manually if both yields present
    if results.get("yield_10y") and results.get("yield_2y"):
        results["yield_spread"] = round(
            results["yield_10y"] - results["yield_2y"], 3
        )
        results["yield_curve_inverted"] = results["yield_spread"] < 0

    results["fetched_at"] = datetime.utcnow().isoformat()
    results["source"] = "fred"

    await cache_set(cache_key, results, ttl_seconds=1800)  # 30 min
    return results