<p align="center">
  <strong>Parallax Intelligence</strong><br>
  <em>AI-powered global signal detection & autonomous portfolio construction</em>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/TypeScript-3178C6?logo=typescript&logoColor=white" alt="TypeScript" />
  <img src="https://img.shields.io/badge/Python-3776AB?logo=python&logoColor=white" alt="Python" />
  <img src="https://img.shields.io/badge/Vite-646CFF?logo=vite&logoColor=white" alt="Vite" />
  <img src="https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white" alt="FastAPI" />
  <img src="https://img.shields.io/badge/FinBERT-FF6F00?logo=huggingface&logoColor=white" alt="FinBERT" />
  <img src="https://img.shields.io/badge/License-MIT-green" alt="MIT License" />
</p>

---

A real-time financial intelligence platform that ingests global event signals, runs them through a multi-stage AI sentiment cascade, and autonomously constructs and optimizes investment portfolios. The system has full agency: it researches, decides, and executes.

## Problem

Retail investors are locked into symmetric, passive portfolios (60/40, target-date funds) while institutional investors access private credit, managed futures, and alternative strategies with better risk-adjusted returns. World events move markets in ways passive portfolios can't respond to.

> A 60/40 portfolio has a Sharpe ratio of ~0.55. Adding 30% alternatives improves it to ~0.75 while *reducing* volatility from 10.9% to 8.9%.
> -- CFA Institute

## Solution

| Layer | What it does |
|-------|-------------|
| **Signal Layer** | Real-time ingestion from GDELT, USGS, FRED, VIX, commodity futures. Every signal classified by sector. |
| **AI Sentiment Cascade** | Groq/Llama 70B (fast filter) &rarr; FinBERT (financial scoring) &rarr; Claude (deep second-order analysis) |
| **AutoAllocator** | Autonomous research loop: propose mutation &rarr; backtest 5yr &rarr; keep if Sharpe improves & drawdown holds &rarr; discard otherwise |
| **Portfolio** | 13 positions across 6 asset classes including managed futures, CLOs, and private credit BDCs |

## Architecture

```
Signal Layer (TypeScript/Vite)        AI Engine (Python/FastAPI)
+--------------------------+          +--------------------------+
| 3D Globe + Map Viz       |          | Sentiment Pipeline       |
| News Aggregation         |   REST   |   Groq -> FinBERT ->     |
| Risk Dashboards          | <------> |   Claude                 |
| Portfolio UI             |          | AutoAllocator Loop       |
| AI Insights Panels       |          | Composite Risk Scoring   |
+--------------------------+          +--------------------------+
        |                                      |
        v                                      v
  GDELT  USGS  FRED  VIX              yfinance  bt  QuantStats
```

## AutoAllocator

Inspired by [karpathy/autoresearch](https://github.com/karpathy/autoresearch). The AI agent autonomously evolves portfolio allocations through a propose-backtest-evaluate loop.

**Mutation strategies:** pair shifts, defensive tilts, growth tilts, random perturbation, concentration, world-signal-driven moves.

**Hard constraints:** no position >25%, min 8 positions, max drawdown -25%, annual turnover cap 300%.

```python
while True:
    change = llm.propose(allocator, history, policy, signals)
    apply_patch(change, "allocator.py")
    results = backtest(period="2020-01-01:2024-12-31")
    if results.sharpe > best and results.max_dd > -0.25:
        git_commit()     # KEPT
    else:
        git_revert()     # DISCARDED
```

## Sentiment Pipeline

```
News/GDELT --> Groq+Llama 70B --> FinBERT --> Claude (high-conviction only)
                (relevant?)     (sentiment)   (second-order effects)
                                    |
                                    v
                        { ticker, direction, conviction }
```

## Investment Universe

| Asset Class | Tickers | Target |
|---|---|---|
| Core Equity | SPY, VTI | ~30% |
| Managed Futures | DBMF, KMLM, RPAR | ~20% |
| CLO / Structured Credit | JAAA, CLOA | ~15% |
| Private Credit BDCs | ARCC, BXSL | ~15% |
| Real Assets | GLDM, PDBC | ~10% |
| Fixed Income | AGG, SRLN | ~10% |

## Quick Start

```bash
# Signal Layer
cd frontend && npm install && npm run dev:finance   # localhost:5173

# AI Engine
cd ai-engine && python -m venv venv && source venv/bin/activate
pip install -r requirements.txt && python server.py  # localhost:8001
```

**Optional API keys** (features degrade gracefully without them):

| Key | Source | Enables |
|---|---|---|
| `GROQ_API_KEY` | [console.groq.com](https://console.groq.com) | AI sentiment filtering & summarization |
| `FRED_API_KEY` | [fred.stlouisfed.org](https://fred.stlouisfed.org/docs/api/api_key.html) | Macroeconomic indicators |
| `FINNHUB_API_KEY` | [finnhub.io](https://finnhub.io) | Live stock quotes |

## Project Structure

```
parallax-intelligence/
+-- frontend/                   # Signal layer & visualization
|   +-- src/components/         # Portfolio, AutoAllocator, Risk, Insights panels
|   +-- src/services/           # Data fetching, AI summarization
|   +-- api/                    # Edge functions (Groq/OpenRouter proxy)
|   +-- server/                 # Server-side RPC handlers
+-- ai-engine/                  # Python AI backend
|   +-- sentiment/              # Groq -> FinBERT -> Claude cascade
|   +-- autoallocator/          # Autonomous optimization loop
|   +-- data/                   # yfinance, FRED, GDELT clients
+-- backend/                    # FastAPI portfolio service
+-- supabase/                   # Database schema
```

## References

- [karpathy/autoresearch](https://github.com/karpathy/autoresearch) -- Autonomous AI experiment loop
- [ProsusAI/finBERT](https://github.com/ProsusAI/finBERT) -- Financial sentiment model
- [QuantStats](https://github.com/ranaroussi/quantstats) -- Portfolio risk metrics

## License

[MIT](LICENSE)

---

<p align="center">Built by <strong>Null Fellows</strong></p>
