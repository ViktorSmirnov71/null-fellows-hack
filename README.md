# Parallax Intelligence

**AI-powered global signal detection & autonomous portfolio construction**

Parallax Intelligence is a real-time financial intelligence platform that ingests global event signals — geopolitical, macroeconomic, supply chain, conflict — runs them through a multi-stage AI sentiment cascade, and autonomously constructs and optimizes investment portfolios. The system has full agency: it researches, decides, and executes — no human in the loop.

---

## The Problem

Retail investors are stuck with symmetric, passive portfolios (60/40, target-date funds) while institutional investors access private credit, managed futures, and alternative strategies that deliver better risk-adjusted returns. Meanwhile, world events — conflicts, supply chain disruptions, policy shifts — move markets in ways that passive portfolios can't respond to.

**The gap:** A 60/40 portfolio has a Sharpe ratio of ~0.55. Adding 30% alternatives improves it to ~0.75 while *reducing* volatility from 10.9% to 8.9% (CFA Institute research). But retail investors don't have the tools, access, or time to build these portfolios.

## The Solution

1. **Global Signal Layer** — Real-time ingestion from GDELT (15-min latency on every global news event), USGS seismic data, FRED macroeconomic indicators, commodity futures, and VIX. Every signal classified by sector: energy, metals, conflict, rates, equity, credit, trade.
2. **Three-Tier AI Sentiment Cascade** — Groq + Llama 70B (fast relevance filter) -> FinBERT (domain-specific financial scoring) -> Claude (deep second-order analysis on high-conviction signals)
3. **Autonomous Portfolio Optimizer** — An AI research loop (inspired by autoresearch) that proposes allocation mutations, backtests against 5 years of data, keeps improvements, discards regressions. Six mutation strategies with hard policy constraints.
4. **Alternative Asset Access** — Private credit BDCs, managed futures ETFs, CLO structured credit, real assets — vehicles previously restricted to institutional investors, now accessible in a single portfolio.

---

## Architecture

```
+---------------------------------------------------------+
|                   SIGNAL LAYER                           |
|  Interactive 3D globe + map with real-time event viz     |
|  News aggregation, AI summarization, risk dashboards     |
|  Tech: TypeScript, Vite, globe.gl, MapLibre, deck.gl    |
+---------------------------------------------------------+
|                   AI ENGINE                              |
|  Sentiment: Groq (speed) -> FinBERT (accuracy)          |
|             -> Claude (deep reasoning)                   |
|  AutoAllocator: propose -> backtest -> evaluate ->       |
|                 keep/discard -> repeat                   |
|  Tech: Python, bt, vectorbt, QuantStats, FinBERT        |
+---------------------------------------------------------+
|                   DATA LAYER                             |
|  Market: yfinance (prices, ETFs, fund data)              |
|  Macro:  FRED API (GDP, CPI, yields, unemployment)       |
|  Geopolitical: GDELT (tone/volume every 15min)           |
|  Conflict: ACLED (violence, protests, strategic events)  |
|  Disasters: USGS earthquakes, ReliefWeb crises           |
+---------------------------------------------------------+
|                 INFRASTRUCTURE                           |
|  Supabase (auth, profiles, portfolio storage)            |
|  Vercel (hosting + edge functions)                       |
|  Upstash Redis (multi-tier caching)                      |
+---------------------------------------------------------+
```

### Data Flow

```
GDELT (tone/volume) --+
ACLED (conflict)     --+
USGS (earthquakes)   --+--> Risk Scoring Engine --> AutoAllocator Loop --> Portfolio
FRED (macro)         --+         |                  (AI research loop)     Output
VIX (volatility)     --+         |                       |
Commodity futures    --+    Sentiment Cascade         yfinance
                              (Groq->FinBERT->Claude)  (prices)
```

---

## The AutoAllocator: Autonomous Portfolio Optimization

Inspired by [karpathy/autoresearch](https://github.com/karpathy/autoresearch), which uses an AI agent to autonomously run ML experiments. We apply the same pattern to portfolio allocation.

### The Loop

```python
while True:
    # 1. PROPOSE: AI reads current allocator + experiment history
    proposed_change = llm.propose(
        current_code=read("allocator.py"),
        history=read("experiment_log.md"),
        constraints=read("policy.md"),
        market_context=latest_sentiment_signals()
    )

    # 2. APPLY the change
    apply_patch(proposed_change, "allocator.py")

    # 3. BACKTEST over 5-year historical window
    results = backtest("allocator.py", period="2020-01-01:2024-12-31")

    # 4. DECIDE: keep or revert
    if new_sharpe > best_sharpe and new_max_dd > -0.25:
        git_commit()   # KEPT
    else:
        git_revert()   # DISCARDED
```

### Six Mutation Strategies
- **Pair shifts** — rebalance between two correlated positions
- **Defensive tilts** — rotate into gold, treasuries, managed futures
- **Growth tilts** — rotate into equities, private credit BDCs
- **Random perturbation** — explore the weight space
- **Concentration** — increase conviction on high-signal positions
- **World-signal-driven** — direct response to real-time event signals

### Policy Constraints (Hard Stops)
- No single position > 25% or < 1%
- Portfolio holds >= 8 distinct positions
- Max drawdown: -25% (hard stop)
- Annual turnover capped at 300%

---

## Sentiment Analysis Pipeline

```
[GDELT / RSS / News APIs]
        |
        v
  Groq + Llama 70B (fast pre-filter)
  -> Is this financially material? Y/N
        |
        v
  FinBERT (domain-specific scoring)
  -> P(positive), P(neutral), P(negative)
  -> Sentiment = P(pos) - P(neg)  in [-1, +1]
        |
        v
  Time-weighted aggregation per ticker/sector
        |
        v
  Claude (deep analysis on high-conviction signals only)
  -> "What are the second-order effects on sector X?"
        |
        v
  Portfolio Signal: { ticker, direction, conviction, timestamp }
```

---

## Composite World Risk Score

Multi-signal risk scoring combining geopolitical, macro, and volatility components:

```
Risk Score = w1 * GDELT_tone     (falling tone = rising risk)
           + w2 * GDELT_volume   (rising volume = rising attention)
           + w3 * yield_inversion (T10Y2Y < 0 = recession signal)
           + w4 * VIX             (volatility spike = market stress)
           + w5 * consumer_sent   (falling confidence = demand risk)
           + w6 * unemployment    (rising = economic weakness)
```

When risk rises -> portfolio autonomously shifts toward defensive allocations.
When risk falls -> portfolio leans into growth positions.

---

## Investment Universe

13 positions across 6 asset classes:

| Asset Class | Tickers | Allocation |
|---|---|---|
| Core Equity | SPY, VTI | ~30% |
| Managed Futures | DBMF, KMLM, RPAR | ~20% |
| CLO / Structured Credit | JAAA, CLOA | ~15% |
| Private Credit BDCs | ARCC, BXSL | ~15% |
| Real Assets | GLDM, PDBC | ~10% |
| Fixed Income | AGG, SRLN | ~10% |

---

## Getting Started

### Prerequisites
- **Node.js 22+** (signal layer)
- **Python 3.10+** (AI engine)

### Signal Layer (Frontend)

```bash
cd frontend
npm install
cp .env.example .env.local
# Add API keys to .env.local (all optional)
npm run dev:finance    # localhost:5173
```

### AI Engine (Backend)

```bash
cd ai-engine
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python server.py       # localhost:8001
```

### Optional API Keys

| Key | Source | Enables |
|---|---|---|
| `GROQ_API_KEY` | [console.groq.com](https://console.groq.com) | AI sentiment filtering & summarization |
| `FRED_API_KEY` | [fred.stlouisfed.org](https://fred.stlouisfed.org/docs/api/api_key.html) | Macroeconomic indicators |
| `FINNHUB_API_KEY` | [finnhub.io](https://finnhub.io) | Live stock quotes |

---

## Project Structure

```
parallax-intelligence/
+-- frontend/                    # Signal layer & visualization
|   +-- src/
|   |   +-- components/          # Panel components
|   |   |   +-- PortfolioPanel.ts       # Portfolio dashboard
|   |   |   +-- AutoAllocatorPanel.ts   # AI loop status & experiments
|   |   |   +-- RiskDashboardPanel.ts   # Risk metrics
|   |   |   +-- InsightsPanel.ts        # AI market insights
|   |   |   +-- MarketPanel.ts          # Live market data
|   |   |   +-- FearGreedPanel.ts       # Sentiment gauge
|   |   |   +-- MacroSignalsPanel.ts    # Economic radar
|   |   |   +-- ...
|   |   +-- config/
|   |   |   +-- variants/finance.ts     # Finance variant config
|   |   |   +-- panels.ts              # Panel registry
|   |   |   +-- feeds.ts               # News feed definitions
|   |   +-- services/                   # Data fetching & AI services
|   |   +-- App.ts
|   +-- api/                     # Edge functions (Groq/OpenRouter proxy)
|   +-- server/                  # Server-side RPC handlers
+-- ai-engine/                   # Python AI backend
|   +-- sentiment/
|   |   +-- pipeline.py          # Groq -> FinBERT -> Claude cascade
|   |   +-- groq_filter.py       # Fast relevance filtering
|   |   +-- finbert_scorer.py    # Financial sentiment scoring
|   |   +-- claude_analyst.py    # Deep second-order analysis
|   |   +-- signal_aggregator.py # Time-weighted signal aggregation
|   +-- autoallocator/
|   |   +-- allocator.py         # [AGENT-MODIFIED] Portfolio weights
|   |   +-- loop.py              # Autonomous optimization loop
|   |   +-- backtest_runner.py   # bt/vectorbt backtesting
|   |   +-- policy.md            # Investment constraints
|   +-- data/
|   |   +-- yfinance_client.py   # Market data
|   |   +-- fred_client.py       # FRED macro data
|   |   +-- gdelt_client.py      # GDELT geopolitical signals
|   |   +-- risk_scorer.py       # Composite risk scoring
|   +-- server.py                # FastAPI server
|   +-- requirements.txt
+-- supabase/                    # Database schema & migrations
+-- CLAUDE.md                    # AI contributor instructions
+-- README.md
```

---

## Key References

- [karpathy/autoresearch](https://github.com/karpathy/autoresearch) — Autonomous AI experiment loop (core inspiration)
- [ProsusAI/finBERT](https://github.com/ProsusAI/finBERT) — Financial domain sentiment model
- [QuantStats](https://github.com/ranaroussi/quantstats) — Portfolio risk metrics
- CFA Institute — *The 60/40 Portfolio Needs an Alts Infusion*
- J.P. Morgan — *Alternative Investments Outlook 2026*

---

## Team

Built by the **Null Fellows** team at the hackathon.

## License

MIT
