from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


# ─── Asset & Holdings ─────────────────────────────────────────────────────────

class HoldingInput(BaseModel):
    ticker: str
    asset_type: str = "stock"
    weight: float
    quantity: Optional[float] = 0
    avg_cost: Optional[float] = 0
    metadata: Optional[dict] = {}

class HoldingDetail(BaseModel):
    ticker: str
    asset_type: str
    weight: float
    quantity: float
    avg_cost: float
    current_price: Optional[float] = None
    current_value: Optional[float] = None
    gain_loss: Optional[float] = None
    gain_loss_pct: Optional[float] = None
    drift_from_target: Optional[float] = None
    risk_score: Optional[float] = None       # composite risk from AI engine
    sector: Optional[str] = None


# ─── Portfolio ────────────────────────────────────────────────────────────────

class PortfolioCreate(BaseModel):
    name: str
    risk_profile: str = "moderate"           # conservative | moderate | aggressive
    rebalance_trigger: str = "both"          # schedule | ai | both | manual
    currency: str = "USD"
    holdings: list[HoldingInput] = []

class PortfolioUpdate(BaseModel):
    name: Optional[str] = None
    risk_profile: Optional[str] = None
    rebalance_trigger: Optional[str] = None

class PerformanceSummary(BaseModel):
    total_return_pct: Optional[float] = None
    total_return_value: Optional[float] = None
    inception_date: Optional[str] = None
    trade_count: int = 0
    best_performer: Optional[str] = None
    worst_performer: Optional[str] = None
    sharpe_ratio: Optional[float] = None     # from backtest if available
    max_drawdown: Optional[float] = None     # from backtest if available
    volatility: Optional[float] = None      # from backtest if available

class TradeRecord(BaseModel):
    ticker: str
    action: str
    quantity: float
    price: float
    value: float
    triggered_by: Optional[str] = None      # scheduler | ai | manual | research
    reason: Optional[str] = None
    conviction: Optional[float] = None      # AI conviction score at time of trade
    executed_at: datetime

class PortfolioDetail(BaseModel):
    portfolio: dict
    holdings: list[HoldingDetail]
    performance: PerformanceSummary
    trade_history: list[TradeRecord]
    ai_summary: Optional[str] = None
    risk_overview: Optional[dict] = None    # aggregate risk across holdings


# ─── Rebalancing ──────────────────────────────────────────────────────────────

class RebalancePreviewRequest(BaseModel):
    target_weights: dict[str, float]
    ai_reasoning: Optional[str] = None
    confidence: Optional[float] = None
    conviction_scores: Optional[dict[str, float]] = None  # per ticker

class ProposedTrade(BaseModel):
    ticker: str
    action: str
    quantity: float
    estimated_value: float
    reason: Optional[str] = None
    conviction: Optional[float] = None
    risk_score: Optional[float] = None

class RebalancePreview(BaseModel):
    portfolio_id: str
    current_weights: dict[str, float]
    target_weights: dict[str, float]
    proposed_trades: list[ProposedTrade]
    drift_score: float
    ai_reasoning: Optional[str] = None
    confidence: Optional[float] = None
    estimated_total_value: Optional[float] = None


# ─── Signals (AI engine output) ───────────────────────────────────────────────

class FinBERTScores(BaseModel):
    positive: float
    neutral: float
    negative: float

class SignalIngest(BaseModel):
    ticker: str
    direction: str                           # bullish | bearish | neutral
    conviction: float                        # -1.0 to 1.0
    source: str                              # gdelt | acled | fred | yfinance | news
    groq_filtered: bool = True
    finbert_scores: Optional[FinBERTScores] = None
    claude_analysis: Optional[str] = None   # only on high-magnitude signals
    second_order_effects: Optional[str] = None
    raw_headline: Optional[str] = None
    sector: Optional[str] = None
    timestamp: Optional[datetime] = None

class SignalResponse(BaseModel):
    id: str
    ticker: str
    direction: str
    conviction: float
    source: str
    claude_analysis: Optional[str] = None
    second_order_effects: Optional[str] = None
    sector: Optional[str] = None
    fetched_at: datetime


# ─── Risk scoring ─────────────────────────────────────────────────────────────

class RiskScore(BaseModel):
    ticker: str
    composite_score: float                  # -1.0 to 1.0 aggregate
    macro_component: Optional[float] = None # FRED contribution
    geo_component: Optional[float] = None   # GDELT + ACLED contribution
    sentiment_component: Optional[float] = None  # FinBERT contribution
    conflict_component: Optional[float] = None   # ACLED specific
    supply_chain_component: Optional[float] = None  # AISStream
    confidence: float = 0.0
    signal_count: int = 0                   # how many signals fed this score
    computed_at: datetime

class RiskOverview(BaseModel):
    portfolio_id: str
    overall_risk: float                     # portfolio-level aggregate
    holdings_risk: list[RiskScore]
    top_risk_factors: list[str]             # human readable
    computed_at: datetime


# ─── Backtest ─────────────────────────────────────────────────────────────────

class BacktestResult(BaseModel):
    portfolio_id: str
    experiment_id: Optional[str] = None    # from AI engine experiment_log.tsv
    strategy_name: Optional[str] = None
    start_date: str
    end_date: str
    total_return_pct: float
    sharpe_ratio: Optional[float] = None
    max_drawdown: Optional[float] = None
    volatility: Optional[float] = None
    win_rate: Optional[float] = None
    weights_used: dict[str, float]
    status: str = "completed"              # completed | failed | running
    kept: Optional[bool] = None            # from AutoAllocator keep/discard
    notes: Optional[str] = None
    created_at: datetime

class BacktestIngest(BaseModel):
    """Posted by AI engine after running bt/vectorbt."""
    portfolio_id: str
    experiment_id: str
    strategy_name: str
    start_date: str
    end_date: str
    total_return_pct: float
    sharpe_ratio: Optional[float] = None
    max_drawdown: Optional[float] = None
    volatility: Optional[float] = None
    win_rate: Optional[float] = None
    weights_used: dict[str, float]
    kept: bool
    notes: Optional[str] = None


# ─── Market data ──────────────────────────────────────────────────────────────

class PriceData(BaseModel):
    ticker: str
    price: float
    prev_close: Optional[float] = None
    change_pct: Optional[float] = None
    volume: Optional[float] = None
    source: str = "yfinance"
    fetched_at: datetime

class MacroIndicator(BaseModel):
    indicator: str                          # interest_rate | cpi | gdp | unemployment
    value: float
    previous_value: Optional[float] = None
    change_pct: Optional[float] = None
    source: str = "fred"
    recorded_at: datetime


# ─── Bulk signal ingest ───────────────────────────────────────────────────────

class BulkSignalIngest(BaseModel):
    signals: list[SignalIngest]
    source_run_id: Optional[str] = None    # AI engine can tag a pipeline run
    pipeline_version: Optional[str] = None # track which model version ran

class BulkSignalResult(BaseModel):
    ticker: str
    status: str                            # ok | error
    id: Optional[str] = None
    detail: Optional[str] = None

class BulkSignalResponse(BaseModel):
    processed: int
    success: int
    failed: int
    source_run_id: Optional[str] = None
    results: list[BulkSignalResult]