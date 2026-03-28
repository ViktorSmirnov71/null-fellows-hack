# Live Data Integration Guide

**For the team member wiring up real data to the frontend panels.**

This guide walks you through connecting the AI engine to live APIs and serving the results to the frontend. By the end, the Portfolio, AutoAllocator, and Risk Dashboard panels will show real data instead of demo values.

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [API Keys — What We Need](#api-keys--what-we-need)
3. [Security — Never Expose Keys](#security--never-expose-keys)
4. [Step 1: Set Up the Python Environment](#step-1-set-up-the-python-environment)
5. [Step 2: Get Your API Keys](#step-2-get-your-api-keys)
6. [Step 3: Test Each Data Client](#step-3-test-each-data-client)
7. [Step 4: Build the API Server](#step-4-build-the-api-server)
8. [Step 5: Connect Frontend to Backend](#step-5-connect-frontend-to-backend)
9. [Step 6: Run the AutoAllocator Loop](#step-6-run-the-autoallocator-loop)
10. [What We're Skipping (No Groq Key)](#what-were-skipping-no-groq-key)
11. [Git Workflow — How to Push Safely](#git-workflow--how-to-push-safely)

---

## Architecture Overview

```
┌─────────────────┐     HTTP/JSON      ┌──────────────────────┐
│    Frontend      │ ◄────────────────► │   Python API Server  │
│  (localhost:3003)│                    │   (localhost:8000)    │
└─────────────────┘                    └──────────┬───────────┘
                                                  │
                                    ┌─────────────┼─────────────┐
                                    │             │             │
                              ┌─────▼───┐   ┌────▼────┐  ┌─────▼─────┐
                              │ yfinance │   │  FRED   │  │   GDELT   │
                              │ (no key) │   │(free key)│  │ (no key)  │
                              └─────────┘   └─────────┘  └───────────┘
```

The frontend panels currently use hardcoded demo data. We need to:
1. Run a Python API server that fetches real data
2. Update the frontend panels to call that API instead of using demo data

---

## API Keys — What We Need

| API | Key Required? | Cost | How to Get | Priority |
|-----|--------------|------|------------|----------|
| **yfinance** | No key needed | Free | Just `pip install yfinance` | Must have |
| **FRED** | Yes (free) | Free | Register at fred.stlouisfed.org | Must have |
| **GDELT** | No key needed | Free | Just make HTTP requests | Must have |
| **Groq** | Yes (free tier) | Free | console.groq.com | **We don't have this — skip for now** |
| **Anthropic (Claude)** | Yes (paid) | $$$ | console.anthropic.com | Skip for hackathon |
| **Finnhub** | Yes (free) | Free | finnhub.io | Nice to have |

**Bottom line: We only need ONE API key — FRED. Everything else either needs no key or we're skipping.**

---

## Security — Never Expose Keys

### The Rules

1. **NEVER put API keys in code files.** Not in `.ts`, `.py`, `.js`, or any committed file.
2. **NEVER commit `.env` files.** They're already in `.gitignore` but double-check.
3. **Keys go ONLY in `.env.local`** (which is gitignored).
4. **Before every commit**, run `git diff --staged` and visually scan for anything that looks like a key.

### How to Check You Haven't Leaked a Key

```bash
# Before pushing, search staged files for common key patterns
git diff --staged | grep -iE "(api_key|secret|token|password)\s*=\s*\S+"

# If this returns anything with an actual key value, STOP and unstage that file
```

### If You Accidentally Commit a Key

```bash
# DON'T just delete it in a new commit — it's still in git history
# Instead:
# 1. Immediately revoke/rotate the key on the provider's website
# 2. Remove it from the file
# 3. Tell Viktor so we can clean git history if needed
```

---

## Step 1: Set Up the Python Environment

```bash
cd ~/Desktop/NullFellows-FinanceWorldMonitor/ai-engine

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Also install FastAPI for the API server
pip install fastapi uvicorn
```

---

## Step 2: Get Your API Keys

### FRED API Key (required, 2 minutes)

1. Go to https://fred.stlouisfed.org/docs/api/api_key.html
2. Click "Request or view your API keys"
3. Create a free account if needed
4. Copy the 32-character key

### Create Your Local Environment File

```bash
cd ~/Desktop/NullFellows-FinanceWorldMonitor/ai-engine

# Create .env.local (this file is gitignored — safe)
cat > .env.local << 'EOF'
FRED_API_KEY=your_32_char_key_here
EOF
```

**Verify it's gitignored:**
```bash
git status
# .env.local should NOT appear in the output
# If it does, STOP — check .gitignore
```

---

## Step 3: Test Each Data Client

Run these one at a time to verify each data source works.

### Test yfinance (no key needed)

```python
# test_yfinance.py
from data.yfinance_client import YFinanceClient

client = YFinanceClient()
prices = client.get_universe_prices(period="1mo")
print(f"Got {len(prices.columns)} tickers, {len(prices)} days of data")
print(prices.tail())
```

```bash
cd ~/Desktop/NullFellows-FinanceWorldMonitor/ai-engine
python -c "
from data.yfinance_client import YFinanceClient
client = YFinanceClient()
quotes = client.get_live_quotes(['SPY', 'GLDM', 'JAAA'])
print(quotes)
"
```

**Expected output:** `{'SPY': 580.12, 'GLDM': 55.43, 'JAAA': 47.89}` (prices will vary)

### Test FRED

```bash
python -c "
from dotenv import load_dotenv
load_dotenv('.env.local')
from data.fred_client import FREDClient
client = FREDClient()
snapshot = client.get_macro_snapshot()
print(f'Fed Funds Rate: {snapshot.fed_funds_rate}')
print(f'10Y Yield: {snapshot.yield_10y}')
print(f'VIX: {snapshot.vix}')
print(f'Yield Spread: {snapshot.yield_spread}')
print(f'Inverted: {client.is_yield_curve_inverted()}')
"
```

**Expected output:** Real macro numbers. If you see `None` for everything, your FRED key is wrong.

### Test GDELT (no key needed)

```bash
python -c "
from data.gdelt_client import GDELTClient
client = GDELTClient()
signal = client.get_country_risk_signal('US', timespan='7d')
print(f'US risk signal: {signal}')
articles = client.get_articles('economy', timespan='24h', max_records=5)
for a in articles:
    print(f'  {a.tone:+.1f} | {a.title[:80]}')
"
```

**Expected output:** A risk signal dict and a few article headlines with tone scores.

### Test Composite Risk Scorer

```bash
python -c "
from dotenv import load_dotenv
load_dotenv('.env.local')
from data.fred_client import FREDClient
from data.gdelt_client import GDELTClient
from data.risk_scorer import RiskScorer
scorer = RiskScorer(FREDClient(), GDELTClient())
score = scorer.compute()
print(f'Risk Total: {score.total:.2f}')
print(f'  Geopolitical: {score.geopolitical:.2f}')
print(f'  Macro: {score.macro:.2f}')
print(f'  Volatility: {score.volatility:.2f}')
print(f'  Components: {score.components}')
"
```

---

## Step 4: Build the API Server

Create this file at `ai-engine/server.py`:

```python
"""
API server that serves live data to the frontend panels.
Run with: uvicorn server:app --port 8000 --reload
"""

import os
from dotenv import load_dotenv
load_dotenv('.env.local')

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from data.yfinance_client import YFinanceClient, PORTFOLIO_UNIVERSE
from data.fred_client import FREDClient
from data.gdelt_client import GDELTClient
from data.risk_scorer import RiskScorer

app = FastAPI(title="Null Fellows API")

# Allow frontend to call us
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3003", "http://localhost:5173"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

# Initialize clients once
yf_client = YFinanceClient()
fred_client = FREDClient()
gdelt_client = GDELTClient()
risk_scorer = RiskScorer(fred_client, gdelt_client)


@app.get("/api/portfolio")
def get_portfolio():
    """Live portfolio data with current prices."""
    quotes = yf_client.get_live_quotes()

    # Base weights from allocator
    from autoallocator.allocator import BASE_WEIGHTS

    total_value = 10000  # Demo amount
    positions = []
    for ticker, weight in BASE_WEIGHTS.items():
        price = quotes.get(ticker, 0)
        value = round(total_value * weight)
        positions.append({
            "ticker": ticker,
            "name": PORTFOLIO_UNIVERSE.get(ticker, ticker),
            "weight": weight,
            "value": value,
            "price": price,
            "assetClass": _get_asset_class(ticker),
        })

    return {"totalValue": total_value, "positions": positions}


@app.get("/api/risk")
def get_risk():
    """Live composite risk score."""
    score = risk_scorer.compute()
    return {
        "total": round(score.total, 3),
        "geopolitical": round(score.geopolitical, 3),
        "macro": round(score.macro, 3),
        "volatility": round(score.volatility, 3),
        "components": {k: round(v, 3) for k, v in score.components.items()},
    }


@app.get("/api/macro")
def get_macro():
    """Live macro snapshot from FRED."""
    snapshot = fred_client.get_macro_snapshot()
    return {
        "gdpGrowth": snapshot.gdp_growth,
        "cpiYoy": snapshot.cpi_yoy,
        "unemployment": snapshot.unemployment,
        "fedFundsRate": snapshot.fed_funds_rate,
        "yield10y": snapshot.yield_10y,
        "yield2y": snapshot.yield_2y,
        "yieldSpread": snapshot.yield_spread,
        "vix": snapshot.vix,
        "consumerSentiment": snapshot.consumer_sentiment,
    }


@app.get("/api/gdelt/{country_code}")
def get_gdelt_risk(country_code: str):
    """GDELT risk signal for a country."""
    signal = gdelt_client.get_country_risk_signal(country_code, timespan="7d")
    return signal


@app.get("/api/gdelt/articles/{query}")
def get_gdelt_articles(query: str, max_records: int = 20):
    """Recent articles matching a query."""
    articles = gdelt_client.get_articles(query, timespan="24h", max_records=max_records)
    return [{"title": a.title, "url": a.url, "source": a.source, "tone": a.tone} for a in articles]


def _get_asset_class(ticker: str) -> str:
    classes = {
        "SPY": "Equity", "VTI": "Equity",
        "DBMF": "Managed Futures", "KMLM": "Managed Futures", "RPAR": "Managed Futures",
        "JAAA": "Structured Credit", "CLOA": "Structured Credit",
        "ARCC": "Private Credit", "BXSL": "Private Credit",
        "GLDM": "Real Assets", "PDBC": "Real Assets",
        "AGG": "Fixed Income", "SRLN": "Fixed Income",
    }
    return classes.get(ticker, "Other")
```

### Run it:

```bash
cd ~/Desktop/NullFellows-FinanceWorldMonitor/ai-engine
source venv/bin/activate
uvicorn server:app --port 8000 --reload
```

### Test it:

```bash
# In another terminal
curl http://localhost:8000/api/risk
curl http://localhost:8000/api/macro
curl http://localhost:8000/api/portfolio
curl http://localhost:8000/api/gdelt/US
```

---

## Step 5: Connect Frontend to Backend

Once the API server is working, update the frontend panels to fetch from it.

In each panel's `fetchData()` method, replace the demo data with a fetch call:

```typescript
// Example for RiskDashboardPanel
public async fetchData(): Promise<boolean> {
  this.showLoading();
  try {
    const resp = await fetch('http://localhost:8000/api/risk');
    if (!resp.ok) throw new Error('API error');
    const data = await resp.json();
    this.metrics = {
      // ... map API response to panel's data structure
      riskTotal: data.total,
      riskGeo: data.geopolitical,
      riskMacro: data.macro,
      riskVol: data.volatility,
      // ... other fields keep demo values for now
    };
    this.render();
    this.setDataBadge('live');
    return true;
  } catch (e) {
    // Fall back to demo data if API is down
    this.metrics = demoMetrics();
    this.render();
    this.setDataBadge('cached');
    return false;
  }
}
```

**Key pattern: always fall back to demo data if the API is down.** This way the demo always works even without the backend running.

The panel files to update are:
- `frontend/src/components/PortfolioPanel.ts` → fetch from `/api/portfolio`
- `frontend/src/components/RiskDashboardPanel.ts` → fetch from `/api/risk`
- `frontend/src/components/AutoAllocatorPanel.ts` → can stay as demo/simulation for now

---

## Step 6: Run the AutoAllocator Loop

This is the autonomous optimization loop. It requires historical price data (via yfinance, no key) and runs backtests locally.

```bash
cd ~/Desktop/NullFellows-FinanceWorldMonitor/ai-engine
source venv/bin/activate

# First, test that backtesting works
python -c "
from autoallocator.backtest_runner import BacktestRunner
runner = BacktestRunner()
result = runner.run()
print(f'Sharpe: {result.sharpe_ratio:.4f}')
print(f'Sortino: {result.sortino_ratio:.4f}')
print(f'Max DD: {result.max_drawdown:.4f}')
print(f'Benchmark Sharpe: {result.benchmark_sharpe:.4f}')
"
```

**Note:** The full autonomous loop (where an LLM proposes changes) requires either Groq or Claude API keys to work. For the hackathon demo, the backtest runner + manual weight tweaks are enough to show the concept.

---

## What We're Skipping (No Groq Key)

Without a Groq API key, the sentiment pipeline's fast-filter stage won't work. Here's how to handle it:

### Option A: Skip Sentiment Entirely (simplest)

The risk scorer and portfolio allocator work fine without sentiment. The sentiment overlay is only a ±0.45% tilt — the risk regime system is the main driver.

### Option B: Use FinBERT Only (no API key needed)

FinBERT runs locally — no API key required. Skip the Groq pre-filter and Claude deep analysis:

```python
from sentiment.finbert_scorer import FinBERTScorer

scorer = FinBERTScorer()  # Downloads model on first run (~400MB)
result = scorer.score("Fed raises interest rates by 25 basis points")
print(f"Sentiment: {result.sentiment:+.3f}")
print(f"Sector: {result.sector}")
```

This gives us sentiment scoring without any API keys. The first run downloads the FinBERT model which takes a minute.

### Option C: Get a Groq Key (free, 2 minutes)

If someone on the team wants to set this up:
1. Go to https://console.groq.com
2. Sign up with GitHub/Google
3. Create an API key (free tier: 14,400 requests/day)
4. Add to `ai-engine/.env.local`: `GROQ_API_KEY=gsk_...`

---

## Git Workflow — How to Push Safely

### Before You Start Working

```bash
cd ~/Desktop/NullFellows-FinanceWorldMonitor
git pull origin main                 # Get latest changes
git checkout -b feature/live-data    # Work on a branch
```

### While Working

```bash
# Check what you've changed
git status
git diff

# Stage specific files (NEVER use git add -A blindly)
git add ai-engine/server.py
git add frontend/src/components/RiskDashboardPanel.ts

# Double-check no keys are staged
git diff --staged | grep -iE "api_key|secret|token|gsk_|sk-"

# Commit
git commit -m "Wire up RiskDashboard to live FRED data"
```

### Before Pushing

```bash
# Final safety check
git log --oneline -3        # Review your commits
git diff origin/main..HEAD  # Review all changes vs main

# Push your branch
git push -u origin feature/live-data
```

### Merging to Main

Create a PR on GitHub or merge locally:
```bash
git checkout main
git pull origin main
git merge feature/live-data
git push origin main
```

### Files You Should NEVER Commit

- `.env.local` or `.env` (API keys)
- `venv/` (Python virtual environment)
- `node_modules/` (npm packages)
- `__pycache__/` (Python bytecode)
- Any file containing an actual API key string

These are all in `.gitignore` already, but always double-check with `git status` before committing.

---

## Quick Reference: What to Run

```bash
# Terminal 1: Frontend (production build served via npx serve)
cd ~/Desktop/NullFellows-FinanceWorldMonitor/frontend
VITE_VARIANT=finance npx vite build
npx serve dist -p 3003 -s

# Terminal 2: Python API server
cd ~/Desktop/NullFellows-FinanceWorldMonitor/ai-engine
source venv/bin/activate
uvicorn server:app --port 8000 --reload

# Terminal 3: ngrok (if sharing externally)
ngrok http 3003
```

---

## Priority Order for the Hackathon

1. **Get FRED key and test `api/risk` + `api/macro` endpoints** (30 min)
2. **Wire RiskDashboardPanel to live risk data** (30 min)
3. **Wire PortfolioPanel to live prices from yfinance** (30 min)
4. **Run a backtest and show real Sharpe numbers** (15 min)
5. **Optional: Set up FinBERT for local sentiment scoring** (20 min)
6. **Optional: Get Groq key for full sentiment pipeline** (10 min)

Total estimated time: **~2 hours for the must-haves.**
