# CLAUDE.md — Instructions for Claude Code Contributors

## Project Overview

Parallax Intelligence: AI-powered global signal detection + autonomous portfolio construction.
Signal layer (frontend) + custom Python AI engine (backend).

## Architecture

- `frontend/` — Signal layer & visualization (vanilla TypeScript, Vite, globe.gl). Run with `npm run dev:finance`
- `ai-engine/` — Python backend with three modules:
  - `sentiment/` — 3-tier pipeline: Groq (filter) -> FinBERT (score) -> Claude (deep analysis)
  - `autoallocator/` — Autonomous portfolio optimization loop (autoresearch pattern)
  - `data/` — API clients for yfinance, FRED, GDELT, and composite risk scoring
- `supabase/` — Database schema and migrations

## Key Files

- `ai-engine/autoallocator/allocator.py` — THE file the AutoAllocator loop modifies. Contains portfolio weights and strategy logic.
- `ai-engine/autoallocator/policy.md` — Investment constraints. Never violate these.
- `ai-engine/data/yfinance_client.py` — PORTFOLIO_UNIVERSE defines all investable tickers.
- `frontend/src/config/variants/finance.ts` — Finance variant panel/layer config.
- `frontend/src/components/Panel.ts` — Base class all panels extend.

## Commands

```bash
# Frontend
cd frontend && npm install && npm run dev:finance  # Starts at localhost:5173

# AI Engine
cd ai-engine && python -m venv venv && source venv/bin/activate && pip install -r requirements.txt

# Type check frontend
cd frontend && npm run typecheck
```

## Conventions

- Frontend is vanilla TypeScript — no React/Vue/Angular
- New panels: create in `src/components/`, register in `src/config/panels.ts`, export from `src/components/index.ts`
- Python code uses loguru for logging, pydantic for data validation
- All API keys are optional — features degrade gracefully without them
- The `finance` variant curates ~35 relevant panels for the finance use case
