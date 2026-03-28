# Null Fellows Hack

**AI-powered world monitoring & autonomous portfolio builder**

A real-time global intelligence dashboard that monitors geopolitical events, economic signals, and market data — then automatically constructs and optimizes investment portfolios using an AI-driven autonomous research loop. Built for the hackathon by the Null Fellows team.

---

## The Problem

Retail investors are stuck with symmetric, passive portfolios (60/40, target-date funds) while institutional investors access private credit, managed futures, and alternative strategies that deliver better risk-adjusted returns. Meanwhile, world events — conflicts, supply chain disruptions, policy shifts — move markets in ways that passive portfolios can't respond to.

**The gap:** A 60/40 portfolio has a Sharpe ratio of ~0.55. Adding 30% alternatives improves it to ~0.75 while *reducing* volatility from 10.9% to 8.9% (CFA Institute research). But retail investors don't have the tools, access, or time to build these portfolios.

## The Solution

A system that:

1. **Monitors the world in real-time** — geopolitical events, economic data, market sentiment, natural disasters, supply chain disruptions — visualized on an interactive 3D globe
2. **Runs sentiment analysis** on global news to generate market signals using a FinBERT + Groq + Claude cascade
3. **Autonomously optimizes portfolios** using an AI research loop (inspired by [karpathy/autoresearch](https://github.com/karpathy/autoresearch)) that proposes allocation changes, backtests them, keeps improvements, and discards regressions
4. **Democratizes access to alternative investments** — private credit, managed futures, CLO ETFs, real assets — vehicles that were previously restricted to institutional investors
5. **Presents everything in a clean, Revolut-style UI** showing exactly where your money is, why, and how world events affected it

---

## Architecture

```
┌──────────────────────────────────────────────────────────┐
│                      FRONTEND                             │
│  WorldMonitor fork (3D globe + interactive map + news)    │
│  + Revolut-style portfolio dashboard                      │
│  + Risk metrics & performance visualization               │
│  Tech: TypeScript, Vite, globe.gl, MapLibre, deck.gl, d3 │
├──────────────────────────────────────────────────────────┤
│                    AI ENGINE                               │
│  Sentiment Pipeline: Groq (speed) → FinBERT (accuracy)    │
│                      → Claude (deep reasoning)            │
│  AutoAllocator Loop: propose → backtest → evaluate →      │
│                      keep/discard → repeat                │
│  Tech: Python, bt, vectorbt, QuantStats, FinBERT          │
├──────────────────────────────────────────────────────────┤
│                   DATA LAYER                               │
│  Market: yfinance (prices, ETFs, fund data)               │
│  Macro:  FRED API (GDP, CPI, yields, unemployment)        │
│  Geopolitical: GDELT (tone/volume every 15min)            │
│  Conflict: ACLED (violence, protests, strategic events)   │
│  Disasters: USGS earthquakes, ReliefWeb crises            │
│  Supply Chain: AISStream (vessel tracking)                │
│  Cyber: ThreatFox (IOC feeds)                             │
│  Displacement: UNHCR refugee data                         │
├──────────────────────────────────────────────────────────┤
│                 INFRASTRUCTURE                             │
│  Supabase (auth, user profiles, portfolio storage)        │
│  Vercel (frontend hosting + edge functions)               │
│  Upstash Redis (multi-tier caching)                       │
└──────────────────────────────────────────────────────────┘
```

### Data Flow

```
GDELT (tone/volume) ─┐
ACLED (conflict)     ─┤
USGS (earthquakes)   ─┼──▶ Risk Scoring Engine ──▶ AutoAllocator Loop ──▶ Portfolio
ReliefWeb (crises)   ─┤         ▲                    (AI research loop)     Output
AISStream (shipping) ─┤         │                         │
ThreatFox (cyber)    ─┘    FRED (macro)              yfinance
                         (rates, GDP, CPI)         (prices, execute)
```

---

## The AutoAllocator: Autonomous Portfolio Optimization

Adapted from [karpathy/autoresearch](https://github.com/karpathy/autoresearch), which uses an AI agent to autonomously run ML experiments — proposing changes, evaluating results, keeping improvements, discarding regressions. We apply the same pattern to portfolio allocation.

### How It Maps

| Autoresearch Element | Our Portfolio Equivalent |
|---|---|
| `prepare.py` (immutable data) | Market data pipeline, historical prices, risk-free rate |
| `train.py` (agent-modified) | `allocator.py` — portfolio weights, rebalancing logic, signal thresholds |
| `program.md` (constraints) | Investment policy: max position size, sector limits, turnover caps |
| `val_bpb` metric | Rolling Sharpe ratio + max drawdown constraint |
| 5-min training run | 5-min backtest over historical window |
| Keep/discard gate | If Sharpe improves AND max drawdown < 25%, keep. Otherwise revert. |

### The Loop

```python
while True:
    # 1. PROPOSE: LLM reads current allocator + experiment history
    #    and proposes a modification (signal weight, sector tilt, rebalance freq)
    proposed_change = llm.propose(
        current_code=read("allocator.py"),
        history=read("experiment_log.md"),
        constraints=read("policy.md"),
        market_context=latest_sentiment_signals()
    )

    # 2. APPLY the change
    apply_patch(proposed_change, "allocator.py")

    # 3. BACKTEST over fixed historical window
    results = backtest("allocator.py", period="2020-01-01:2024-12-31")

    # 4. EVALUATE fitness
    new_sharpe = results.sharpe_ratio
    new_max_dd = results.max_drawdown

    # 5. DECIDE: keep or revert
    if new_sharpe > best_sharpe and new_max_dd > -0.25:
        best_sharpe = new_sharpe
        git_commit()
        log_experiment(status="KEPT", sharpe=new_sharpe, dd=new_max_dd)
    else:
        git_revert()
        log_experiment(status="DISCARDED", sharpe=new_sharpe, dd=new_max_dd)
```

### Benchmarks & Risk Metrics

We use [QuantStats](https://github.com/ranaroussi/quantstats) to generate a full tearsheet. Key metrics:

| Metric | What It Shows | Target |
|---|---|---|
| **Sharpe Ratio** | Return per unit risk | > 1.5 |
| **Sortino Ratio** | Return per unit downside risk | > 2.0 |
| **Max Drawdown** | Worst peak-to-trough decline | < -15% |
| **Calmar Ratio** | CAGR / Max Drawdown | > 1.0 |
| **Tail Ratio** | Right tail / left tail (asymmetry) | > 1.0 (positive skew) |
| **VaR (95%)** | Worst expected daily loss at 95% confidence | Report |
| **CVaR** | Average loss beyond VaR | Report |

**Primary benchmark:** 60/40 portfolio (60% S&P 500 / 40% Bloomberg US Agg). Our portfolio must beat this on a risk-adjusted basis to justify its complexity.

---

## Sentiment Analysis Pipeline

Three-tier cascade optimized for speed and accuracy:

```
[News Feeds / RSS / GDELT / APIs]
        │
        ▼
  Groq + Llama 3 (fast pre-filter)
  → classify: financial relevance? Y/N
        │
        ▼
  FinBERT (domain-specific scoring)
  → softmax: P(positive), P(neutral), P(negative)
  → Sentiment Score = P(positive) - P(negative)  ∈ [-1, +1]
        │
        ▼
  Time-weighted aggregation per ticker/sector
        │
        ▼
  Claude (deep analysis — high-magnitude signals only)
  → "What are the second-order effects on sector X?"
        │
        ▼
  Portfolio Signal: { ticker, direction, conviction, timestamp }
```

---

## Data Sources

### Market & Financial Data

| Source | Auth | Rate Limit | Update Freq | What It Gives Us |
|---|---|---|---|---|
| **yfinance** | None | ~2K req/hr | 15-min delay | Live prices, historical OHLCV, ETF holdings, options, analyst targets, financials |
| **FRED API** | Free API key | 120 req/min | Varies | 816K+ economic series: GDP, CPI, unemployment, yield curves, Fed funds rate, VIX |
| **Finnhub** | Free API key | 60 req/min | Real-time | Stock quotes, earnings, IPOs, forex |

#### Key FRED Series

| Series ID | Indicator | Frequency |
|---|---|---|
| `GDP` | Gross Domestic Product | Quarterly |
| `CPIAUCSL` | Consumer Price Index | Monthly |
| `UNRATE` | Unemployment Rate | Monthly |
| `FEDFUNDS` | Federal Funds Rate | Daily |
| `DGS10` | 10-Year Treasury Yield | Daily |
| `T10Y2Y` | 10Y-2Y Spread (yield curve inversion) | Daily |
| `VIXCLS` | VIX Volatility Index | Daily |
| `UMCSENT` | Consumer Sentiment | Monthly |

### Geopolitical & Event Data

| Source | Auth | Rate Limit | Update Freq | What It Gives Us |
|---|---|---|---|---|
| **GDELT** | None | ~1 req/sec | Every 15 min | News volume, tone scoring, themes, geographic tagging across 100+ languages |
| **ACLED** | Free OAuth | 5K events/call | Weekly | Political violence, protests, riots, battles — with coordinates and fatalities |
| **USGS** | None | Reasonable | Real-time | Earthquake catalog with magnitude, depth, coordinates, tsunami flags |
| **ReliefWeb** | None | Reasonable | As published | UN humanitarian reports, disaster declarations, crisis data |
| **UNHCR** | None | Reasonable | Annual + updates | Refugee and displacement statistics by origin/asylum country |

### Infrastructure & Supply Chain

| Source | Auth | Rate Limit | Update Freq | What It Gives Us |
|---|---|---|---|---|
| **AISStream** | Free API key | Streaming | Real-time | Global vessel tracking (800K+ ships) — monitor chokepoint transits |
| **ThreatFox** | Free API key | Reasonable | Real-time | Cyber threat IOCs — spikes correlate with sector-specific market impact |

### Composite Risk Signal

Combine across sources to build a per-region risk score:

```
Risk Score = w1 * GDELT_tone_change     (falling tone = rising risk)
           + w2 * GDELT_volume_change    (rising volume = rising attention)
           + w3 * ACLED_event_count      (more conflict = more risk)
           + w4 * FRED_yield_inversion   (T10Y2Y < 0 = recession signal)
           + w5 * AIS_transit_drop       (fewer ships = supply disruption)
```

When risk rises → shift portfolio toward defensive allocations (treasuries, gold, managed futures).

---

## Investment Vehicles: Democratizing Access

The core differentiator: we allocate across asset classes retail investors typically can't reach.

### Private Credit (Interval Funds)

| Fund | Ticker | Min Investment | What It Is |
|---|---|---|---|
| Apollo Diversified Credit | CRDTX | **$2,500** | Multi-strategy private credit via Apollo's $600B+ platform |
| Carlyle Tactical Private Credit | TAKNX | $10,000 | Direct lending from Carlyle's $400B+ deal pipeline |
| Cliffwater Corporate Lending | CCLFX | $10M (platforms waive) | The category-defining fund, $32B+ AUM, 4000+ positions |

### Managed Futures / Trend-Following ETFs

| Fund | Ticker | Min Investment | Why It Matters |
|---|---|---|---|
| iMGP DBi Managed Futures | DBMF | ~$25 (1 share) | Replicates top 20 CTA hedge funds for 0.85% fee |
| KraneShares Mount Lucas | KMLM | ~$27 (1 share) | Systematic trend-following across commodities, currencies, bonds |
| SPDR Bridgewater All Weather | ALLW | 1 share | Ray Dalio's All Weather strategy in a retail ETF |
| RPAR Risk Parity | RPAR | ~$18 (1 share) | Lowest-cost risk parity ETF (0.54%) |
| Fidelity Managed Futures | FFUT | 1 share | Won Best New Alternatives ETF 2026 |

### CLO / Structured Credit ETFs

| Fund | Ticker | Min Investment | Why It Matters |
|---|---|---|---|
| Janus Henderson AAA CLO | JAAA | 1 share | $25B AUM, AAA credit, 5.5% yield, 0.20% fee |
| iShares AAA CLO Active | CLOA | 1 share | BlackRock's CLO entry, 5.6% yield |
| Janus Henderson B-BBB CLO | JBBB | 1 share | Higher-yield (7.5%) CLO exposure |

### Publicly Traded BDCs (Private Credit via Stock Market)

| Fund | Ticker | Dividend Yield | What It Is |
|---|---|---|---|
| Ares Capital Corp | ARCC | ~9-10% | Largest public BDC, backed by Ares ($400B+ AUM) |
| Blackstone Secured Lending | BXSL | ~12.9% | Blackstone's public BDC, senior secured lending |
| Blue Owl Capital Corp | OBDC | ~11-12% | One of the fastest-growing alt asset managers |

### Real Assets & Commodities

| Fund | Ticker | Why It Matters |
|---|---|---|
| Invesco Optimum Yield Commodity | PDBC | Broad commodity exposure, no K-1 tax form |
| SPDR Gold MiniShares | GLDM | Lowest-cost gold ETF (0.10%) |
| State Street Blackstone Senior Loan | SRLN | 7.1% yield, floating-rate hedge against rising rates |

### The Asymmetric Growth Thesis

> *"Traditional portfolios are symmetric — they go up and down equally with the market. Our system constructs asymmetric portfolios by dynamically tilting into assets with convex payoff profiles when sentiment signals detect regime shifts."*

Key evidence:
- A portfolio of 40% PE, 30% private credit, 20% RE, 10% hedge funds achieved a **Calmar ratio of 1.83** over 20 years vs. the S&P 500's **0.18** (Future Standard research)
- In 2022, when both stocks AND bonds fell (worst 60/40 year in decades), managed futures posted large positive gains
- Private credit market grew from $250B (2007) to **$2.5T** (2025) — J.P. Morgan now calls it "essential, not optional"
- SEC's August 2025 policy change eliminated minimum investment requirements for registered alternative funds, opening the door for retail access

---

## Demo Scenario

**Persona:** Working-class user, $50K annual income, $10K to invest.

**The experience:**

1. **Globe View:** The 3D globe lights up with real-time events — a trade policy shift in China, rising conflict in the Middle East, a supply chain disruption in the Strait of Hormuz
2. **Signal Detection:** The sentiment pipeline processes 500+ news sources. FinBERT scores turn negative on energy sector, positive on treasury-linked instruments. GDELT tone for Middle East drops sharply while volume spikes.
3. **AutoAllocator runs:** The AI loop proposes shifting 5% from emerging market equity into managed futures (DBMF) and AAA CLOs (JAAA). It backtests the change — Sharpe improves from 1.42 to 1.51, max drawdown stays within bounds. Change is kept.
4. **Portfolio View:** Clean Revolut-style cards show:
   - **$3,000** in index ETFs (SPY, VTI)
   - **$2,000** in managed futures (DBMF, KMLM)
   - **$2,000** in AAA CLOs (JAAA) + senior loans (SRLN)
   - **$1,500** in private credit BDCs (ARCC, BXSL)
   - **$1,000** in gold (GLDM) + commodities (PDBC)
   - **$500** in real estate (Fundrise interval fund)
5. **Risk Dashboard:** Sharpe 1.51, Sortino 2.1, Max Drawdown -11.3%, Tail Ratio 1.24. Monte Carlo simulation shows 82% probability of positive returns over 12 months.

---

## Tech Stack

### Frontend (WorldMonitor fork)
- **TypeScript** (vanilla — no React/Vue/Angular)
- **Vite** for dev/build + PWA support
- **globe.gl + Three.js** for 3D globe visualization
- **MapLibre GL + Protomaps PMTiles** for 2D interactive map
- **deck.gl** for data visualization layers
- **d3** for charts and graphs

### AI Engine (Python)
- **FinBERT** (ProsusAI/finBERT) — financial domain sentiment
- **Groq API** — fast LLM inference for pre-filtering
- **Claude API** — deep reasoning on high-magnitude signals
- **bt** — portfolio backtesting framework (native portfolio support)
- **vectorbt** — high-speed vectorized backtesting for the AutoAllocator loop
- **QuantStats** — risk metrics and tearsheet generation

### Infrastructure
- **Supabase** — auth, PostgreSQL database, user profiles, portfolio storage
- **Vercel** — frontend hosting + edge functions (auto-preview on every PR)
- **Upstash Redis** — multi-tier caching (60s to 24hr)

---

## Project Structure

```
null-fellows-hack/
├── frontend/                    # WorldMonitor fork (finance variant)
│   ├── src/
│   │   ├── components/          # Panel components
│   │   │   ├── Panel.ts         # Base panel class
│   │   │   ├── MarketPanel.ts   # Live market data
│   │   │   ├── PortfolioPanel.ts       # [NEW] Revolut-style portfolio view
│   │   │   ├── AutoAllocatorPanel.ts   # [NEW] AI loop status & experiments
│   │   │   ├── RiskDashboardPanel.ts   # [NEW] QuantStats metrics
│   │   │   └── ...
│   │   ├── config/
│   │   │   ├── panels.ts       # Panel registry
│   │   │   ├── variants/
│   │   │   │   └── finance.ts  # Finance variant config
│   │   │   ├── markets.ts      # Market symbols & sectors
│   │   │   └── feeds.ts        # RSS feed definitions
│   │   ├── services/           # Data fetching services
│   │   └── App.ts              # Main application
│   ├── api/                    # Vercel Edge Functions
│   ├── .env.local              # API keys (gitignored)
│   └── package.json
├── ai-engine/                  # Python AI backend
│   ├── sentiment/
│   │   ├── pipeline.py         # Groq → FinBERT → Claude cascade
│   │   ├── finbert_scorer.py   # FinBERT wrapper
│   │   └── signal_aggregator.py
│   ├── autoallocator/
│   │   ├── allocator.py        # [AGENT-MODIFIED] Portfolio weights & logic
│   │   ├── policy.md           # Investment constraints
│   │   ├── program.md          # Agent instructions (autoresearch pattern)
│   │   ├── backtest_runner.py  # bt/vectorbt backtest harness
│   │   ├── experiment_log.tsv  # All experiments (kept/discarded/crashed)
│   │   └── analysis.ipynb      # Progress visualization
│   ├── data/
│   │   ├── yfinance_client.py  # Market data fetcher
│   │   ├── fred_client.py      # FRED API wrapper
│   │   ├── gdelt_client.py     # GDELT tone/volume queries
│   │   ├── acled_client.py     # Conflict event data
│   │   └── risk_scorer.py      # Composite risk signal
│   └── requirements.txt
├── supabase/                   # Database schema & migrations
│   ├── migrations/
│   └── seed.sql
├── .github/
│   └── workflows/
│       └── ci.yml              # Typecheck, lint, test
├── CLAUDE.md                   # Claude Code instructions for all contributors
└── README.md                   # This file
```

---

## Getting Started

### Prerequisites

- **Node.js 22+** (for frontend)
- **Python 3.10+** (for AI engine)
- **Git**

### 1. Clone the repo

```bash
git clone https://github.com/ViktorSmirnov71/null-fellows-hack.git
cd null-fellows-hack
```

### 2. Set up the frontend (WorldMonitor fork)

```bash
cd frontend
npm install
cp .env.example .env.local
# Add your API keys to .env.local (all optional — runs without them)
npm run dev:finance    # Opens at localhost:5173
```

**Optional API keys** (add to `.env.local` for richer data):

| Key | Where to Get | What It Enables |
|---|---|---|
| `GROQ_API_KEY` | [console.groq.com](https://console.groq.com) | AI market summaries |
| `FINNHUB_API_KEY` | [finnhub.io](https://finnhub.io) | Live stock quotes |
| `FRED_API_KEY` | [fred.stlouisfed.org](https://fred.stlouisfed.org/docs/api/api_key.html) | Economic indicators |

### 3. Set up the AI engine

```bash
cd ai-engine
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 4. Set up Supabase

```bash
# Install Supabase CLI
brew install supabase/tap/supabase

# Start local Supabase
supabase init
supabase start
```

---

## Team Collaboration

### Work Split

| Person | Role | Branch | Focus Areas |
|---|---|---|---|
| **Person 1** | Frontend | `feature/frontend` | WorldMonitor fork setup, portfolio dashboard UI (Revolut-style cards, allocation pie chart, performance graph), risk dashboard panel |
| **Person 2** | AI / Backend | `feature/ai-engine` | Sentiment pipeline (FinBERT + Groq + Claude), AutoAllocator loop, backtesting harness, Supabase schema |
| **Person 3** | Data / Integration | `feature/data-layer` | yfinance + FRED + GDELT + ACLED API wiring, data ingestion, composite risk scoring, demo scenario data, fund mapping |

### Workflow

```bash
# Each person works on their branch
git checkout -b feature/your-area

# Push regularly
git push -u origin feature/your-area

# Merge to main via PR (Vercel auto-deploys previews for each PR)
```

### Vercel Preview Deployments

Every push to any branch gets an automatic preview URL. No ngrok needed — everyone sees everyone's work live. Connect the repo to Vercel:

1. Go to [vercel.com/new](https://vercel.com/new)
2. Import `ViktorSmirnov71/null-fellows-hack`
3. Set root directory to `frontend/`
4. Framework: Vite
5. Every PR now gets a unique preview URL

---

## Adding a New Panel to WorldMonitor

The panel system is straightforward — 3 steps:

**Step 1:** Create `src/components/YourPanel.ts`:
```typescript
import { Panel } from './Panel';

export class YourPanel extends Panel {
  constructor() {
    super({ panelId: 'yourPanel', title: 'Your Panel Title' });
    this.init();
  }

  private async init() {
    this.showLoading();
    const el = document.createElement('div');
    // Build your UI here
    this.setContent(el);
    this.setDataBadge('live');
  }
}
```

**Step 2:** Register in `src/config/panels.ts`:
```typescript
yourPanel: { name: 'Your Panel Title', enabled: true, priority: 1 },
```

**Step 3:** Export from `src/components/index.ts`:
```typescript
export { YourPanel } from './YourPanel';
```

---

## Key References

### Inspiration
- [karpathy/autoresearch](https://github.com/karpathy/autoresearch) — Autonomous AI experiment loop
- [koala73/worldmonitor](https://github.com/koala73/worldmonitor) — Real-time global intelligence dashboard

### AI & Finance
- [ProsusAI/finBERT](https://github.com/ProsusAI/finBERT) — Financial domain sentiment model
- [bt (backtesting)](https://pmorissette.github.io/bt/) — Portfolio-native backtesting framework
- [QuantStats](https://github.com/ranaroussi/quantstats) — Portfolio risk metrics & tearsheets
- [Open-Finance-Lab/AgenticTrading](https://github.com/Open-Finance-Lab/AgenticTrading) — Agentic trading with adaptive research loops

### Research
- CFA Institute — [The 60/40 Portfolio Needs an Alts Infusion](https://blogs.cfainstitute.org/investor/2023/12/21/the-60-40-portfolio-needs-an-alts-infusion/)
- J.P. Morgan — [Alternative Investments Outlook 2026](https://am.jpmorgan.com/us/en/asset-management/adv/insights/portfolio-insights/alternatives/alternatives-outlook/)
- Kathryn Kaminski (AlphaSimplex) — Crisis Alpha of Managed Futures
- Alexander Ineichen — *Asymmetric Returns: The Future of Active Asset Management* (Wiley, 2006)

---

## License

MIT

---

*Built at the hackathon by the Null Fellows team.*
