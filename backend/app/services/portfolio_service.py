from app.database import get_supabase, get_service_supabase
from app.model.schemas import (
    PortfolioCreate, PortfolioUpdate, RebalancePreviewRequest,
    HoldingDetail, PerformanceSummary, TradeRecord,
    RebalancePreview, ProposedTrade, BacktestIngest
)
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class PortfolioService:

    # ─── CRUD ─────────────────────────────────────────────────────────────────

    async def get_user_portfolios(self, user_id: str) -> list:
        db = get_supabase()
        result = (
            db.table("portfolios")
            .select("*")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .execute()
        )
        return result.data

    async def create(self, user_id: str, body: PortfolioCreate) -> dict:
        db = get_service_supabase()
        portfolio = (
            db.table("portfolios")
            .insert({
                "user_id": user_id,
                "name": body.name,
                "risk_profile": body.risk_profile,
                "rebalance_trigger": body.rebalance_trigger,
                "currency": body.currency,
                "total_value": 0
            })
            .execute()
            .data[0]
        )

        if body.holdings:
            holdings = [
                {
                    "portfolio_id": portfolio["id"],
                    "ticker": h.ticker,
                    "asset_type": h.asset_type,
                    "weight": h.weight,
                    "quantity": h.quantity,
                    "avg_cost": h.avg_cost,
                    "metadata": h.metadata or {}
                }
                for h in body.holdings
            ]
            db.table("holdings").insert(holdings).execute()

        return portfolio

    async def get(self, portfolio_id: str, user_id: str) -> dict | None:
        db = get_supabase()

        portfolio_result = (
            db.table("portfolios")
            .select("*")
            .eq("id", portfolio_id)
            .eq("user_id", user_id)
            .execute()
        )

        if not portfolio_result.data:
            return None

        portfolio = portfolio_result.data[0]

        holdings_raw = (
            db.table("holdings")
            .select("*")
            .eq("portfolio_id", portfolio_id)
            .execute()
            .data
        )

        trades_raw = (
            db.table("trades")
            .select("*")
            .eq("portfolio_id", portfolio_id)
            .order("executed_at", desc=True)
            .limit(50)
            .execute()
            .data
        )

        # Get latest backtest if available
        backtest = await self._get_latest_backtest(portfolio_id)

        # Enrich holdings with live prices and risk scores
        holdings = await self._enrich_holdings(holdings_raw)

        # Calculate performance — merge backtest metrics if available
        performance = self._calculate_performance(holdings, trades_raw, backtest)

        # Build risk overview
        risk_overview = await self._build_risk_overview(portfolio_id, holdings)

        trade_history = [
            TradeRecord(
                ticker=t["ticker"],
                action=t["action"],
                quantity=t["quantity"],
                price=t["price"],
                value=t["quantity"] * t["price"],
                triggered_by=t.get("triggered_by"),
                reason=t.get("reason"),
                conviction=t.get("conviction"),
                executed_at=t["executed_at"]
            )
            for t in trades_raw
        ]

        ai_summary = self._generate_ai_summary(
            portfolio, holdings, performance, risk_overview
        )

        return {
            "portfolio": portfolio,
            "holdings": [h.dict() for h in holdings],
            "performance": performance.dict(),
            "trade_history": [t.dict() for t in trade_history],
            "ai_summary": ai_summary,
            "risk_overview": risk_overview
        }

    async def update(
        self, portfolio_id: str, user_id: str, body: PortfolioUpdate
    ) -> dict | None:
        db = get_service_supabase()
        updates = {k: v for k, v in body.dict().items() if v is not None}
        updates["updated_at"] = datetime.utcnow().isoformat()
        result = (
            db.table("portfolios")
            .update(updates)
            .eq("id", portfolio_id)
            .eq("user_id", user_id)
            .execute()
        )
        return result.data[0] if result.data else None

    async def delete(self, portfolio_id: str, user_id: str) -> bool:
        db = get_service_supabase()
        db.table("portfolios").delete().eq("id", portfolio_id).eq("user_id", user_id).execute()
        return True

    # ─── Rebalance preview ────────────────────────────────────────────────────

    async def preview_rebalance(
        self, portfolio_id: str, user_id: str, body: RebalancePreviewRequest
    ) -> RebalancePreview:
        db = get_supabase()

        holdings_raw = (
            db.table("holdings")
            .select("*")
            .eq("portfolio_id", portfolio_id)
            .execute()
            .data
        )

        current_weights = {
            h["ticker"]: round(h["weight"], 4) for h in holdings_raw
        }

        holdings = await self._enrich_holdings(holdings_raw)
        total_value = sum(
            h.current_value for h in holdings if h.current_value
        )

        proposed_trades = []
        for ticker, target_weight in body.target_weights.items():
            current_weight = current_weights.get(ticker, 0)
            weight_diff = target_weight - current_weight

            if abs(weight_diff) < 0.01:
                continue

            target_value = total_value * target_weight
            current_holding = next(
                (h for h in holdings if h.ticker == ticker), None
            )
            current_price = current_holding.current_price if current_holding else 0
            current_val = current_holding.current_value if current_holding else 0
            conviction = (
                body.conviction_scores.get(ticker)
                if body.conviction_scores else None
            )

            if current_price and current_price > 0:
                value_diff = target_value - (current_val or 0)
                quantity = abs(value_diff / current_price)

                proposed_trades.append(ProposedTrade(
                    ticker=ticker,
                    action="buy" if weight_diff > 0 else "sell",
                    quantity=round(quantity, 4),
                    estimated_value=round(abs(value_diff), 2),
                    reason=(
                        f"{'Underweight' if weight_diff > 0 else 'Overweight'} "
                        f"by {abs(weight_diff)*100:.1f}%"
                    ),
                    conviction=conviction,
                    risk_score=current_holding.risk_score if current_holding else None
                ))

        drift_score = self._calculate_drift(current_weights, body.target_weights)

        return RebalancePreview(
            portfolio_id=portfolio_id,
            current_weights=current_weights,
            target_weights=body.target_weights,
            proposed_trades=proposed_trades,
            drift_score=round(drift_score, 4),
            ai_reasoning=body.ai_reasoning,
            confidence=body.confidence,
            estimated_total_value=round(total_value, 2)
        )

    # ─── Backtest ─────────────────────────────────────────────────────────────

    async def ingest_backtest(self, body: BacktestIngest) -> dict:
        """Called by AI engine after running bt/vectorbt."""
        db = get_service_supabase()
        result = (
            db.table("backtest_results")
            .insert({
                "portfolio_id": body.portfolio_id,
                "experiment_id": body.experiment_id,
                "strategy_name": body.strategy_name,
                "start_date": body.start_date,
                "end_date": body.end_date,
                "total_return_pct": body.total_return_pct,
                "sharpe_ratio": body.sharpe_ratio,
                "max_drawdown": body.max_drawdown,
                "volatility": body.volatility,
                "win_rate": body.win_rate,
                "weights_used": body.weights_used,
                "kept": body.kept,
                "notes": body.notes,
                "status": "completed"
            })
            .execute()
        )
        return result.data[0]

    async def get_backtest_history(self, portfolio_id: str) -> list:
        db = get_supabase()
        return (
            db.table("backtest_results")
            .select("*")
            .eq("portfolio_id", portfolio_id)
            .order("created_at", desc=True)
            .limit(20)
            .execute()
            .data
        )

    async def get_experiments(self, portfolio_id: str) -> list:
        """For the AutoAllocatorPanel — returns full experiment log."""
        db = get_supabase()
        return (
            db.table("backtest_results")
            .select("*")
            .eq("portfolio_id", portfolio_id)
            .order("created_at", desc=True)
            .execute()
            .data
        )

    # ─── Scheduler helpers ────────────────────────────────────────────────────

    async def get_all_active_tickers(self) -> list[str]:
        db = get_service_supabase()
        result = db.table("holdings").select("ticker").execute()
        return list(set(h["ticker"] for h in result.data))

    async def get_all_active_portfolios(self) -> list[dict]:
        db = get_service_supabase()
        return db.table("portfolios").select("id, user_id").execute().data

    # ─── Private helpers ──────────────────────────────────────────────────────

    async def _enrich_holdings(self, holdings_raw: list) -> list[HoldingDetail]:
        from app.services.market_service import MarketService
        from app.services.risk_service import RiskService

        market = MarketService()
        risk = RiskService()

        tickers = [h["ticker"] for h in holdings_raw]
        prices = await market.get_prices(tickers)
        risk_scores = await risk.get_risk_scores_bulk(tickers)

        enriched = []
        for h in holdings_raw:
            price_data = prices.get(h["ticker"])
            current_price = price_data["price"] if price_data else None
            current_value = (
                current_price * h["quantity"]
            ) if current_price else None
            cost_basis = h["avg_cost"] * h["quantity"]
            gain_loss = (
                current_value - cost_basis
            ) if current_value else None
            gain_loss_pct = (
                round((gain_loss / cost_basis) * 100, 2)
                if gain_loss and cost_basis > 0 else None
            )
            risk_data = risk_scores.get(h["ticker"])

            enriched.append(HoldingDetail(
                ticker=h["ticker"],
                asset_type=h["asset_type"],
                weight=h["weight"],
                quantity=h["quantity"],
                avg_cost=h["avg_cost"],
                current_price=current_price,
                current_value=current_value,
                gain_loss=gain_loss,
                gain_loss_pct=gain_loss_pct,
                risk_score=risk_data.composite_score if risk_data else None,
                sector=h.get("metadata", {}).get("sector")
            ))

        return enriched

    async def _get_latest_backtest(self, portfolio_id: str) -> dict | None:
        db = get_supabase()
        result = (
            db.table("backtest_results")
            .select("*")
            .eq("portfolio_id", portfolio_id)
            .eq("kept", True)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        return result.data[0] if result.data else None

    async def _build_risk_overview(
        self, portfolio_id: str, holdings: list[HoldingDetail]
    ) -> dict:
        risk_scores = [
            h.risk_score for h in holdings if h.risk_score is not None
        ]
        if not risk_scores:
            return None

        overall = round(sum(risk_scores) / len(risk_scores), 3)

        # Top risk factors based on which holdings have highest risk
        top_risk = sorted(
            [h for h in holdings if h.risk_score],
            key=lambda h: abs(h.risk_score),
            reverse=True
        )[:3]

        top_factors = [
            f"{h.ticker} ({'+' if h.risk_score > 0 else ''}{h.risk_score:.2f})"
            for h in top_risk
        ]

        return {
            "portfolio_id": portfolio_id,
            "overall_risk": overall,
            "top_risk_factors": top_factors,
            "computed_at": datetime.utcnow().isoformat()
        }

    def _calculate_performance(
        self,
        holdings: list[HoldingDetail],
        trades: list,
        backtest: dict | None = None
    ) -> PerformanceSummary:
        total_cost = sum(h.avg_cost * h.quantity for h in holdings)
        total_value = sum(
            h.current_value for h in holdings if h.current_value
        )
        total_return_value = total_value - total_cost if total_value else None
        total_return_pct = (
            round((total_return_value / total_cost) * 100, 2)
            if total_return_value and total_cost > 0 else None
        )

        performers = [h for h in holdings if h.gain_loss_pct is not None]
        best = max(performers, key=lambda h: h.gain_loss_pct).ticker if performers else None
        worst = min(performers, key=lambda h: h.gain_loss_pct).ticker if performers else None
        inception_date = (
            min(t["executed_at"] for t in trades)[:10] if trades else None
        )

        # Merge backtest metrics if the AI engine has run one
        sharpe = backtest.get("sharpe_ratio") if backtest else None
        drawdown = backtest.get("max_drawdown") if backtest else None
        volatility = backtest.get("volatility") if backtest else None

        return PerformanceSummary(
            total_return_pct=total_return_pct,
            total_return_value=round(total_return_value, 2) if total_return_value else None,
            inception_date=inception_date,
            trade_count=len(trades),
            best_performer=best,
            worst_performer=worst,
            sharpe_ratio=sharpe,
            max_drawdown=drawdown,
            volatility=volatility
        )

    def _calculate_drift(
        self, current: dict[str, float], target: dict[str, float]
    ) -> float:
        all_tickers = set(current) | set(target)
        if not all_tickers:
            return 0.0
        return sum(
            abs(current.get(t, 0) - target.get(t, 0))
            for t in all_tickers
        ) / len(all_tickers)

    def _generate_ai_summary(
        self,
        portfolio: dict,
        holdings: list[HoldingDetail],
        performance: PerformanceSummary,
        risk_overview: dict | None
    ) -> str:
        name = portfolio.get("name", "Your portfolio")
        ret = performance.total_return_pct
        ret_str = f"{ret:+.1f}%" if ret is not None else "N/A"
        summary = f"{name} is showing a total return of {ret_str}."

        if performance.best_performer:
            summary += f" Top performer: {performance.best_performer}."
        if performance.worst_performer and performance.worst_performer != performance.best_performer:
            summary += f" Lagging: {performance.worst_performer}."
        if performance.sharpe_ratio:
            summary += f" Sharpe ratio: {performance.sharpe_ratio:.2f}."
        if performance.max_drawdown:
            summary += f" Max drawdown: {performance.max_drawdown:.1f}%."
        if risk_overview:
            overall = risk_overview.get("overall_risk", 0)
            risk_label = "elevated" if overall > 0.5 else "moderate" if overall > 0.2 else "low"
            summary += f" Overall portfolio risk is {risk_label} ({overall:+.2f})."
        if performance.trade_count:
            summary += f" {performance.trade_count} AI-driven trades since inception."

        return summary