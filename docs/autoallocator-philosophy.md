# AutoAllocator: Philosophy & Model

## The Core Idea

Most retail portfolios are static — set once, rebalanced quarterly, blind to the world. Institutional investors have teams of analysts monitoring geopolitics, macro data, and sentiment to dynamically adjust allocations. We automate that entire process.

The AutoAllocator is an AI agent that **continuously evolves portfolio weights** by proposing changes, backtesting them against historical data, and keeping only improvements. It's adapted from [karpathy/autoresearch](https://github.com/karpathy/autoresearch), which uses the same pattern to improve machine learning models.

## How It Picks Funds

### The Investment Universe

We selected 20 instruments across 6 asset classes, specifically chosen to give retail investors access to strategies typically reserved for institutional allocators:

| Asset Class | Allocation | Tickers | Why These |
|---|---|---|---|
| **Core Equity** | 30% | SPY, VTI | Broad US market exposure. SPY (S&P 500) is the baseline; VTI adds small/mid-cap. |
| **Managed Futures** | 20% | DBMF, KMLM, RPAR | **Crisis alpha.** These replicate CTA hedge fund strategies at ETF fees. In 2022, when stocks AND bonds fell, managed futures posted large positive returns. DBMF replicates the top 20 managed futures hedge funds. RPAR is Bridgewater-style risk parity. |
| **Structured Credit** | 15% | JAAA, CLOA | AAA-rated CLO tranches. 5.5% yield, 0.20% fee, floating rate. These were institutional-only until 2020. JAAA alone has $25B AUM — proof the market validates this access. |
| **Private Credit BDCs** | 15% | ARCC, BXSL | Publicly traded Business Development Companies backed by Ares ($400B+) and Blackstone. 9-13% dividend yields from middle-market lending. Buy/sell like any stock — no lockup, no accreditation. |
| **Real Assets** | 10% | GLDM, PDBC | GLDM (gold) is the tail-risk hedge — lowest cost at 0.10%. PDBC is broad commodity exposure without the K-1 tax headache. |
| **Fixed Income** | 10% | AGG, SRLN | AGG is the core bond position. SRLN is floating-rate senior loans (7.1% yield) — natural hedge against rising rates. |

### Why These Specific Funds

The selection criteria:
1. **Retail-accessible** — all are ETFs or public equities, no minimums beyond 1 share ($15-55)
2. **Liquid** — daily trading volume > $1M for every position
3. **Low correlation** — managed futures and gold have historically negative correlation to equities
4. **Asymmetric payoff** — the portfolio is designed to have a Tail Ratio > 1.0 (more upside than downside)

## The Decision Engine

### Layer 1: World Risk Score

Six real-time signals are combined into a composite risk score (0 to 100):

```
Risk Score = 20% × GDELT_tone         (falling global news tone = rising risk)
           + 15% × GDELT_volume        (rising news volume = rising attention)
           + 20% × yield_inversion     (10Y-2Y spread < 0 = recession signal)
           + 20% × VIX                 (>30 = crisis, <15 = calm)
           + 10% × consumer_sentiment  (UMich survey, lower = worse)
           + 15% × unemployment_trend  (higher = worse)
```

**Data sources:**
- [GDELT Project](https://www.gdeltproject.org/) — monitors print, broadcast, and web news in 100+ languages, updated every 15 minutes. We use the DOC 2.0 API for tone (average sentiment) and volume (% of global coverage).
- [FRED API](https://fred.stlouisfed.org/) — 816,000+ economic time series from the Federal Reserve. We pull yield curves (DGS10, DGS2, T10Y2Y), VIX (VIXCLS), consumer sentiment (UMCSENT), and unemployment (UNRATE).

**Risk regimes:**
- Score > 70: **Defensive** — shift 3% per asset toward GLDM, AGG, JAAA, DBMF
- Score < 30: **Growth** — shift 3% per asset toward SPY, VTI, ARCC, BXSL
- Score 30-70: **Neutral** — use base weights

### Layer 2: Sentiment Analysis Pipeline

A three-tier cascade processes news articles into portfolio signals:

```
[500+ news sources / RSS / GDELT articles]
        |
        v
  Groq + Llama 3 (fast pre-filter)
  "Is this headline financially relevant?" (~500 tokens/sec)
  Keeps ~30-40% of articles
        |
        v
  FinBERT (ProsusAI/finBERT)
  Financial-domain sentiment scoring
  Output: P(positive) - P(negative) → score in [-1, +1]
  Also extracts: ticker, sector
        |
        v
  Time-weighted aggregation per ticker
  Exponential decay with 6-hour half-life
  More recent articles get higher weight
        |
        v
  Claude (deep analysis — HIGH conviction signals only)
  Triggered when |score| > 0.7
  "What are the second-order effects on sector X?"
        |
        v
  Portfolio Signal: { ticker, direction, conviction }
```

**How signals affect allocation:**
- Only signals with conviction > 0.3 are acted on
- Each signal tilts allocation by: `signal × 0.15 (SENTIMENT_WEIGHT) × 0.03 (REGIME_SHIFT_MAGNITUDE)`
- Maximum tilt per asset: ~0.45% per signal
- Signals are intentionally weak — sentiment is a nudge, not a driver

### Layer 3: The Autonomous Optimization Loop

This is the core innovation, adapted from [karpathy/autoresearch](https://github.com/karpathy/autoresearch):

```
┌─────────────────────────────────────────────────┐
│                FOREVER LOOP                      │
│                                                  │
│  1. LLM reads:                                   │
│     - allocator.py (current strategy)            │
│     - experiment_log.tsv (all past experiments)  │
│     - policy.md (immutable constraints)          │
│     - Latest risk score + sentiment signals      │
│                                                  │
│  2. LLM proposes ONE change:                     │
│     "Increase DBMF from 10% to 15%,             │
│      reduce SPY from 20% to 15%"                 │
│                                                  │
│  3. Change is written to allocator.py            │
│                                                  │
│  4. Backtest runs over 5 years of data (~5 min)  │
│     using bt (backtesting framework)             │
│                                                  │
│  5. Metrics computed via QuantStats:             │
│     Sharpe, Sortino, Max Drawdown, Calmar,       │
│     Tail Ratio, CAGR, VaR, CVaR                  │
│                                                  │
│  6. DECISION GATE:                               │
│     IF Sharpe improved                           │
│        AND max drawdown > -25%                   │
│     THEN: git commit (KEEP)                      │
│     ELSE: git checkout (REVERT)                  │
│                                                  │
│  7. Result logged to experiment_log.tsv          │
│                                                  │
│  8. Go to step 1                                 │
│     (~12 experiments/hour, ~100 overnight)        │
└─────────────────────────────────────────────────┘
```

**What the LLM can change** (only in `allocator.py`):
- `BASE_WEIGHTS` — allocation percentages
- `RISK_THRESHOLD_HIGH/LOW` — regime trigger points
- `DEFENSIVE_OVERWEIGHT/GROWTH_OVERWEIGHT` — which assets shift in each regime
- `REGIME_SHIFT_MAGNITUDE` — how aggressively to shift
- `REBALANCE_FREQUENCY` — weekly, monthly, quarterly
- `SENTIMENT_WEIGHT` — how much news sentiment influences allocation
- `MIN_CONVICTION` — minimum signal strength to act on
- The `get_weights()` function logic itself

**What the LLM cannot change:**
- The ticker universe (fixed in `yfinance_client.py`)
- The policy constraints (fixed in `policy.md`)
- Any file other than `allocator.py`

## The Fitness Function

**Primary metric: Sharpe Ratio** — excess return per unit of risk.

```
Sharpe = (Portfolio Return - Risk-Free Rate) / Portfolio Standard Deviation
```

The agent maximizes Sharpe while keeping max drawdown above -25%. This is a deliberate choice:
- Raw returns would incentivize concentrated, volatile positions
- Sharpe rewards *consistent* returns relative to risk taken
- The drawdown constraint prevents catastrophic scenarios

**Benchmark: 60/40 portfolio** (60% SPY, 40% AGG)
- Historical Sharpe: ~0.54
- Any strategy that can't beat this doesn't justify its complexity
- Current best: 1.51 (180% improvement)

## Policy Constraints (Immutable Guardrails)

These cannot be overridden by the AI agent:

| Constraint | Value | Rationale |
|---|---|---|
| Max single position | 25% | Prevent over-concentration |
| Min single position | 1% | No dust positions |
| Min positions | 8 | Enforce diversification |
| Max drawdown | -25% | Hard stop for catastrophic loss |
| Max monthly loss | -12% | Prevent single-month blowups |
| Max annual turnover | 300% | Avoid excessive trading costs |
| Must beat 60/40 | On Sharpe | Justify complexity |
| Equity range | 15-40% | Prevent all-in or all-out |
| Alternatives range | 10-30% | Maintain diversification benefit |

## The Asymmetric Growth Thesis

The portfolio is designed for **positive skew** — more upside than downside:

- **Tail Ratio > 1.0** means the right tail (gains) is fatter than the left tail (losses)
- Managed futures provide **crisis alpha** — they tend to profit in market crashes via trend-following
- CLO ETFs provide **steady income** with minimal drawdowns
- Gold provides **tail-risk insurance** — negatively correlated to equities in crises
- The AutoAllocator continuously optimizes for Tail Ratio improvement as a secondary effect of Sharpe maximization

Evidence (from CFA Institute research):
- A 60/40 portfolio has a Sharpe of 0.55
- Adding 30% alternatives (40/30/30 split) improves Sharpe to 0.75 while reducing volatility from 10.9% to 8.9%
- Private credit market grew 10x from $250B to $2.5T (2007-2025)
- SEC's August 2025 policy change removed minimum investment requirements for alternative funds

## Technology Stack

| Component | Technology | Role |
|---|---|---|
| Backtesting | bt (Python) | Portfolio-native backtesting framework |
| Fast backtesting | vectorbt | Vectorized engine for parameter sweeps |
| Risk metrics | QuantStats | 60+ metrics, Monte Carlo, tearsheets |
| Sentiment | FinBERT (ProsusAI) | Financial-domain sentiment model |
| Fast filter | Groq + Llama 3 | Sub-millisecond classification |
| Deep analysis | Claude | Second-order market effect reasoning |
| Market data | yfinance | Live prices, historical OHLCV |
| Macro data | FRED API | 816K+ economic time series |
| Geopolitical | GDELT | News tone/volume every 15 minutes |
| Database | Supabase | User profiles, portfolios, experiments |

## References

- Karpathy, A. (2026). [autoresearch](https://github.com/karpathy/autoresearch). Autonomous AI experiment loop.
- CFA Institute (2023). [The 60/40 Portfolio Needs an Alts Infusion](https://blogs.cfainstitute.org/investor/2023/12/21/the-60-40-portfolio-needs-an-alts-infusion/).
- J.P. Morgan (2026). [Alternative Investments Outlook](https://am.jpmorgan.com/us/en/asset-management/adv/insights/portfolio-insights/alternatives/alternatives-outlook/).
- Kaminski, K. (AlphaSimplex). Crisis Alpha of Managed Futures.
- Ineichen, A. (2006). *Asymmetric Returns: The Future of Active Asset Management*. Wiley.
- ProsusAI. [finBERT](https://github.com/ProsusAI/finBERT). Financial domain sentiment analysis.
