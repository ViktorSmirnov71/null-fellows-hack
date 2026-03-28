# Parallax Intelligence — Signal Layer

The real-time visualization and signal ingestion layer for Parallax Intelligence. Built with vanilla TypeScript, Vite, globe.gl, and MapLibre.

## Quick Start

```bash
npm install
cp .env.example .env.local
npm run dev:finance    # localhost:5173
```

## Architecture

- `src/components/` — Panel components (Portfolio, AutoAllocator, Risk Dashboard, Market, Insights, etc.)
- `src/config/` — Panel registry, feed definitions, finance variant config
- `src/services/` — Data fetching, AI summarization, sentiment analysis integration
- `src/app/` — Application orchestration, data loading, event handling
- `api/` — Vercel Edge Functions (Groq/OpenRouter proxy, data endpoints)
- `server/` — Server-side RPC handlers

## Key Panels

| Panel | Purpose |
|---|---|
| Portfolio | Revolut-style portfolio view with live positions and P&L |
| AutoAllocator | AI experiment loop status, mutation history, Sharpe tracking |
| Risk Dashboard | Composite risk score, geopolitical/macro/volatility breakdown |
| AI Insights | LLM-summarized market intelligence from news signals |
| Markets | Live stock, forex, bond, commodity, crypto data |
| Fear & Greed | Market sentiment gauge |
| Macro Signals | Economic radar with FRED indicators |

## Environment Variables

All optional — features degrade gracefully without them. See `.env.example` for the full list.
