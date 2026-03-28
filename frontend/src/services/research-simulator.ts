/**
 * ResearchSimulator — client-side engine that simulates the Karpathy autoresearch
 * loop adapted for portfolio optimization. Drives the Live Auto Researcher tab.
 *
 * Emits typed events through a callback as each experiment progresses through
 * 5 pipeline stages: Data Ingest → Sentiment → Hypothesis → Backtest → Decision.
 *
 * Optionally calls the Groq API for real LLM reasoning in the hypothesis phase.
 * Falls back to pre-scripted templates when no API key is available.
 */

/* ── Event types ── */

export interface DataIngestEvent {
  type: 'data_ingest';
  source: string;
  detail: string;
  tickersUpdated: string[];
}

export interface SentimentEvent {
  type: 'sentiment';
  tier: 'groq_filter' | 'finbert' | 'claude_deep';
  detail: string;
  score?: number;
  ticker?: string;
}

export interface HypothesisStartEvent {
  type: 'hypothesis_start';
  experimentId: number;
}

export interface HypothesisChunkEvent {
  type: 'hypothesis_chunk';
  text: string;
}

export interface HypothesisEndEvent {
  type: 'hypothesis_end';
  fullText: string;
}

export interface BacktestProgressEvent {
  type: 'backtest_progress';
  pct: number;
  elapsed: string;
  currentMetric?: string;
}

export interface BacktestResultEvent {
  type: 'backtest_result';
  metrics: ExperimentMetrics;
}

export interface DecisionEvent {
  type: 'decision';
  status: 'KEPT' | 'DISCARDED' | 'CRASH';
  experimentId: number;
  description: string;
  metrics: ExperimentMetrics;
  prevBestSharpe: number;
}

export interface ErrorEvent {
  type: 'error';
  message: string;
}

export interface StageChangeEvent {
  type: 'stage_change';
  stage: PipelineStage;
}

export type ResearchEvent =
  | DataIngestEvent
  | SentimentEvent
  | HypothesisStartEvent
  | HypothesisChunkEvent
  | HypothesisEndEvent
  | BacktestProgressEvent
  | BacktestResultEvent
  | DecisionEvent
  | ErrorEvent
  | StageChangeEvent;

export type PipelineStage = 'idle' | 'data_ingest' | 'sentiment' | 'hypothesis' | 'backtest' | 'decision';

export interface ExperimentMetrics {
  sharpe: number;
  sortino: number;
  maxDrawdown: number;
  calmar: number;
  cagr: number;
  volatility: number;
  winRate: number;
  var95: number;
}

export interface ExperimentRecord {
  id: number;
  status: 'KEPT' | 'DISCARDED' | 'CRASH';
  description: string;
  metrics: ExperimentMetrics;
  timestamp: number;
}

export interface SimulatorState {
  experimentCount: number;
  kept: number;
  discarded: number;
  crashed: number;
  bestSharpe: number;
  benchmarkSharpe: number;
  experiments: ExperimentRecord[];
  allocations: Record<string, number>;
  currentStage: PipelineStage;
  running: boolean;
}

/* ── Constants ── */

const BENCHMARK_SHARPE = 0.54;

const INITIAL_ALLOCATIONS: Record<string, number> = {
  SPY: 0.20, VTI: 0.10, DBMF: 0.10, KMLM: 0.05, RPAR: 0.05,
  JAAA: 0.10, CLOA: 0.05, ARCC: 0.08, BXSL: 0.07,
  GLDM: 0.05, PDBC: 0.05, AGG: 0.05, SRLN: 0.05,
};

const DATA_SOURCES = [
  { name: 'GDELT', detail: 'Scanning 15-min global event tone feed' },
  { name: 'Yahoo Finance', detail: 'Pulling latest EOD prices for 13 assets' },
  { name: 'FRED', detail: 'Checking yield curve spread (10Y-2Y), VIX, UMich sentiment' },
  { name: 'GDELT Volume', detail: 'Aggregating article volume by region' },
  { name: 'FRED Unemployment', detail: 'Latest BLS unemployment rate' },
];

const HEADLINES = [
  'Fed signals potential rate pause amid cooling inflation data',
  'China PMI contracts for third consecutive month, copper drops 2%',
  'Oil surges 4% on Middle East supply disruption fears',
  'Tech earnings beat expectations, NASDAQ hits new high',
  'European Central Bank holds rates, warns of stagflation risks',
  'Gold rallies to record high on safe-haven demand',
  'US jobs report surprises to upside: 280K added',
  'Japan yen weakens past 160 as BoJ maintains ultra-loose policy',
  'Credit spreads widen on regional banking concerns',
  'Commodity indices fall as dollar strengthens sharply',
  'India GDP growth accelerates to 7.8% year-over-year',
  'VIX spikes above 25 as geopolitical tensions escalate',
  'Treasury yield curve un-inverts for first time in 18 months',
  'OPEC+ agrees deeper production cuts starting Q2',
  'Bitcoin surges past $100K as institutional inflows accelerate',
  'CLO issuance hits record levels amid strong credit appetite',
  'Private credit AUM surpasses $1.7T globally',
  'Consumer confidence drops to 6-month low',
  'Real estate REITs rally on rate cut expectations',
  'Emerging market currencies strengthen on dollar weakness',
];

const HYPOTHESIS_TEMPLATES = [
  'Increase GLDM allocation from {from}% to {to}% — gold momentum is strong with VIX elevated and real rates declining. Reduce SPY exposure by {delta}% to fund the shift.',
  'Rotate 3% from AGG into JAAA — AAA CLO spreads offer 150bps pickup over treasuries with minimal credit risk. Current credit environment remains benign.',
  'Add 2% to DBMF from VTI — managed futures should benefit from trend persistence in rates and commodities. Cross-asset momentum signals are strong.',
  'Reduce BXSL by 2%, add to ARCC — Ares Capital has better sector diversification and lower floating rate exposure heading into a potential rate cut cycle.',
  'Shift 3% from equity (SPY) to PDBC — commodity supply constraints and geopolitical risk premium justify higher real asset exposure. Correlation benefits improve portfolio Sharpe.',
  'Increase KMLM allocation by 2% funded from SRLN — Mount Lucas has shown superior crisis alpha in recent volatility. Senior loans underperforming as defaults tick up.',
  'Overweight structured credit: +3% JAAA, -2% AGG, -1% VTI. CLO AAA tranches trading at historically wide spreads with negligible default risk.',
  'Defensive tilt: +2% GLDM, +1% AGG, -2% SPY, -1% ARCC. Risk signals elevated — GDELT tone negative, VIX above 20, yield curve flattening.',
  'Growth tilt: +3% SPY, +1% VTI, -2% AGG, -2% GLDM. Economic data improving, sentiment turning positive, risk regime score dropped below 0.3.',
  'Increase RPAR weight by 2% from PDBC — risk parity strategy should outperform in current cross-asset volatility regime. PDBC dragged by agricultural sector weakness.',
  'Reduce total equity to 25% (-5% SPY) and allocate to managed futures (+3% DBMF, +2% KMLM). Equity momentum weakening while trend signals remain strong across rates and FX.',
  'Add 2% to CLOA from SRLN — iShares AAA CLO offers better liquidity and tighter tracking than senior loan ETFs in current spread environment.',
  'Increase private credit to 18%: +2% ARCC, +1% BXSL. Direct lending yields at 11%+ with robust coverage ratios. Fund from -2% VTI, -1% AGG.',
  'Full defensive rotation: +3% GLDM, +2% AGG, +1% DBMF, -3% SPY, -2% VTI, -1% ARCC. Multiple risk signals flashing: inverted curve, VIX spike, negative GDELT tone.',
  'Tactical rebalance back to base weights — recent experiments have over-concentrated in alternatives. Return to policy-neutral positioning and let next cycle find new alpha.',
  'Replace SRLN position entirely: move 5% into split of JAAA (3%) and CLOA (2%). Senior loans face headwinds from rising defaults; AAA CLOs offer better risk-adjusted carry.',
  'Trim GLDM by 2%, add to PDBC — gold overbought on RSI-14, while broader commodities (energy, metals, agriculture) offer diversified exposure at lower valuation.',
  'Increase RPAR from 5% to 8%, reduce KMLM by 3% — Risk Parity ETF provides similar managed futures exposure plus bonds and commodities in a single allocation.',
  'Add momentum overlay: increase SPY +2% and DBMF +1%, reduce AGG -2% and PDBC -1%. 6-month price momentum favors equities and trend-following over fixed income.',
  'Maximum Sharpe tilt: concentrate in top-3 performers from last quarter — JAAA (15%), ARCC (12%), DBMF (12%). Reduce laggards proportionally while respecting 25% position cap.',
];

const GROQ_SYSTEM_PROMPT = `You are an autonomous portfolio researcher running experiments on a 13-asset alternative investment portfolio. You speak concisely in 2-3 sentences.

Assets: SPY, VTI (equity), DBMF, KMLM, RPAR (managed futures), JAAA, CLOA (structured credit), ARCC, BXSL (private credit), GLDM, PDBC (real assets), AGG, SRLN (fixed income).

Constraints: min 1%, max 25% per position. Min 8 positions. Max drawdown -25%.

Given the current allocation and recent results, propose ONE specific weight change with a clear rationale tied to current market conditions. Be specific with numbers.`;

/* ── Utility functions ── */

function gaussRandom(mean: number, std: number): number {
  const u1 = Math.random();
  const u2 = Math.random();
  return mean + std * Math.sqrt(-2 * Math.log(u1)) * Math.cos(2 * Math.PI * u2);
}

function clamp(v: number, lo: number, hi: number): number {
  return Math.max(lo, Math.min(hi, v));
}

function sleep(ms: number): Promise<void> {
  return new Promise(r => setTimeout(r, ms));
}

function pickRandom<T>(arr: T[]): T {
  return arr[Math.floor(Math.random() * arr.length)]!;
}

function generateMetrics(bestSharpe: number): ExperimentMetrics {
  // Most experiments cluster near the current best, with occasional outliers
  const sharpe = clamp(gaussRandom(bestSharpe - 0.02, 0.12), 0.4, 2.0);
  const sortino = clamp(sharpe * (1.3 + Math.random() * 0.4), 0.5, 3.5);
  const maxDrawdown = clamp(gaussRandom(-0.14, 0.04), -0.30, -0.03);
  const calmar = clamp(sharpe / Math.abs(maxDrawdown) * 0.3, 0.3, 5.0);
  const cagr = clamp(gaussRandom(0.08, 0.04), -0.05, 0.25);
  const volatility = clamp(gaussRandom(0.12, 0.03), 0.04, 0.30);
  const winRate = clamp(gaussRandom(0.55, 0.05), 0.35, 0.72);
  const var95 = clamp(gaussRandom(-0.02, 0.008), -0.06, -0.005);
  return { sharpe, sortino, maxDrawdown, calmar, cagr, volatility, winRate, var95 };
}

/* ── Simulator class ── */

export class ResearchSimulator {
  private state: SimulatorState;
  private onEvent: (event: ResearchEvent) => void;
  private speed = 1;
  private aborted = false;
  private groqApiKey: string | null = null;
  /** Generation counter — incremented on every start() to kill stale loops */
  private generation = 0;

  constructor(onEvent: (event: ResearchEvent) => void) {
    this.onEvent = onEvent;
    this.state = {
      experimentCount: 0,
      kept: 0,
      discarded: 0,
      crashed: 0,
      bestSharpe: 1.24,
      benchmarkSharpe: BENCHMARK_SHARPE,
      experiments: [],
      allocations: { ...INITIAL_ALLOCATIONS },
      currentStage: 'idle',
      running: false,
    };
  }

  getState(): SimulatorState { return this.state; }

  /** Swap the event callback (used when DOM rebuilds but state persists) */
  setOnEvent(cb: (event: ResearchEvent) => void): void { this.onEvent = cb; }

  setGroqApiKey(key: string | null): void { this.groqApiKey = key; }

  setSpeed(x: number): void { this.speed = clamp(x, 1, 10); }

  start(): void {
    if (this.state.running) return;
    this.state.running = true;
    this.aborted = false;
    this.generation++;
    void this.runLoop(this.generation);
  }

  pause(): void {
    this.state.running = false;
    this.aborted = true;
  }

  resume(): void {
    if (this.state.running) return;
    this.start();
  }

  /** Returns true if the current loop generation is still valid */
  private alive(gen: number): boolean {
    return !this.aborted && gen === this.generation;
  }

  private delay(ms: number): Promise<void> {
    return sleep(ms / this.speed);
  }

  private emit(event: ResearchEvent): void {
    this.onEvent(event);
  }

  private setStage(stage: PipelineStage): void {
    this.state.currentStage = stage;
    this.emit({ type: 'stage_change', stage });
  }

  /* ── Main loop ── */

  private async runLoop(gen: number): Promise<void> {
    while (this.alive(gen)) {
      try {
        await this.runExperiment(gen);
        if (!this.alive(gen)) return;
        await this.delay(2000); // Brief pause between experiments
      } catch (e) {
        if (!this.alive(gen)) return;
        this.emit({ type: 'error', message: `Loop error: ${e}` });
        await this.delay(3000);
      }
    }
  }

  private async runExperiment(gen: number): Promise<void> {
    this.state.experimentCount++;
    const expId = this.state.experimentCount;

    // ── Phase 1: Data Ingest ──
    this.setStage('data_ingest');
    for (const src of DATA_SOURCES) {
      if (!this.alive(gen)) return;
      const tickers = Object.keys(this.state.allocations)
        .sort(() => Math.random() - 0.5)
        .slice(0, 3 + Math.floor(Math.random() * 4));
      this.emit({ type: 'data_ingest', source: src.name, detail: src.detail, tickersUpdated: tickers });
      await this.delay(600 + Math.random() * 400);
    }

    // ── Phase 2: Sentiment Analysis ──
    if (!this.alive(gen)) return;
    this.setStage('sentiment');

    const articleCount = 5 + Math.floor(Math.random() * 8);
    const passCount = Math.floor(articleCount * (0.3 + Math.random() * 0.15));
    this.emit({
      type: 'sentiment', tier: 'groq_filter',
      detail: `Scanned ${articleCount} articles — ${passCount} passed financial relevance filter`,
    });
    await this.delay(800);

    // FinBERT scoring
    for (let i = 0; i < Math.min(passCount, 4); i++) {
      if (!this.alive(gen)) return;
      const headline = pickRandom(HEADLINES);
      const score = clamp(gaussRandom(0, 0.5), -1, 1);
      const ticker = pickRandom(Object.keys(this.state.allocations));
      this.emit({
        type: 'sentiment', tier: 'finbert',
        detail: `"${headline}" → ${score >= 0 ? '+' : ''}${score.toFixed(2)} [${ticker}]`,
        score, ticker,
      });
      await this.delay(500 + Math.random() * 300);
    }

    // Occasionally trigger Claude deep analysis
    if (Math.random() < 0.35) {
      if (!this.alive(gen)) return;
      const headline = pickRandom(HEADLINES);
      this.emit({
        type: 'sentiment', tier: 'claude_deep',
        detail: `High conviction signal: "${headline}" — analyzing second-order portfolio effects`,
      });
      await this.delay(1200);
    }

    // ── Phase 3: Hypothesis ──
    if (!this.alive(gen)) return;
    this.setStage('hypothesis');
    this.emit({ type: 'hypothesis_start', experimentId: expId });
    await this.delay(400);

    let hypothesis: string;
    if (this.groqApiKey) {
      hypothesis = await this.generateGroqHypothesis(expId, gen);
    } else {
      hypothesis = await this.generateTemplateHypothesis(gen);
    }

    this.emit({ type: 'hypothesis_end', fullText: hypothesis });
    await this.delay(600);

    // ── Phase 4: Backtest ──
    if (!this.alive(gen)) return;
    this.setStage('backtest');

    const isCrash = Math.random() < 0.05;
    const steps = 8 + Math.floor(Math.random() * 5);
    const metricNames = ['Sharpe', 'Sortino', 'Max Drawdown', 'Calmar', 'CAGR', 'Volatility', 'Win Rate', 'VaR 95%'];

    for (let i = 0; i <= steps; i++) {
      if (!this.alive(gen)) return;
      const pct = Math.round((i / steps) * 100);
      const elapsed = `${Math.floor(i * 5 / steps)}:${String(Math.floor((i * 300 / steps) % 60)).padStart(2, '0')}`;
      const metricLabel = i > 2 && i <= 2 + metricNames.length ? metricNames[i - 3] : undefined;
      this.emit({ type: 'backtest_progress', pct, elapsed, currentMetric: metricLabel });
      await this.delay(300 + Math.random() * 200);
    }

    // Generate result
    const metrics = generateMetrics(this.state.bestSharpe);
    if (isCrash) {
      metrics.sharpe = NaN;
    }

    this.emit({ type: 'backtest_result', metrics });
    await this.delay(500);

    // ── Phase 5: Decision ──
    if (!this.alive(gen)) return;
    this.setStage('decision');

    let status: 'KEPT' | 'DISCARDED' | 'CRASH';
    const prevBest = this.state.bestSharpe;

    if (isCrash || isNaN(metrics.sharpe)) {
      status = 'CRASH';
      this.state.crashed++;
    } else if (metrics.sharpe > this.state.bestSharpe && metrics.maxDrawdown > -0.25) {
      status = 'KEPT';
      this.state.kept++;
      this.state.bestSharpe = metrics.sharpe;
      // Tweak allocations slightly to reflect the change
      this.nudgeAllocations();
    } else {
      status = 'DISCARDED';
      this.state.discarded++;
    }

    const record: ExperimentRecord = {
      id: expId,
      status,
      description: hypothesis,
      metrics,
      timestamp: Date.now(),
    };
    this.state.experiments.push(record);

    this.emit({ type: 'decision', status, experimentId: expId, description: hypothesis, metrics, prevBestSharpe: prevBest });
    this.setStage('idle');
    await this.delay(1500);
  }

  /* ── Hypothesis generation ── */

  private async generateTemplateHypothesis(gen: number): Promise<string> {
    const template = pickRandom(HYPOTHESIS_TEMPLATES);
    const from = 3 + Math.floor(Math.random() * 12);
    const delta = 1 + Math.floor(Math.random() * 4);
    const to = from + delta;
    const text = template
      .replace('{from}', String(from))
      .replace('{to}', String(to))
      .replace('{delta}', String(delta));

    // Simulate typewriter streaming
    const words = text.split(' ');
    for (let i = 0; i < words.length; i++) {
      if (!this.alive(gen)) return text;
      this.emit({ type: 'hypothesis_chunk', text: (i > 0 ? ' ' : '') + words[i] });
      await this.delay(40 + Math.random() * 30);
    }
    return text;
  }

  private async generateGroqHypothesis(expId: number, gen: number): Promise<string> {
    const allocStr = Object.entries(this.state.allocations)
      .map(([t, w]) => `${t}: ${(w * 100).toFixed(1)}%`)
      .join(', ');

    const recentStr = this.state.experiments.slice(-3).map(e =>
      `#${e.id} ${e.status} Sharpe=${isNaN(e.metrics.sharpe) ? 'CRASH' : e.metrics.sharpe.toFixed(3)}: ${e.description.slice(0, 80)}`
    ).join('\n');

    const prompt = `Current allocation: ${allocStr}
Best Sharpe so far: ${this.state.bestSharpe.toFixed(3)} (benchmark 60/40: ${BENCHMARK_SHARPE})
Experiment #${expId}.
Recent results:\n${recentStr || 'No previous experiments.'}

Propose ONE specific weight change:`;

    try {
      const resp = await fetch('https://api.groq.com/openai/v1/chat/completions', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${this.groqApiKey}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          model: 'llama-3.3-70b-versatile',
          messages: [
            { role: 'system', content: GROQ_SYSTEM_PROMPT },
            { role: 'user', content: prompt },
          ],
          temperature: 0.8,
          max_tokens: 200,
          stream: true,
        }),
      });

      if (!resp.ok || !resp.body) {
        return this.generateTemplateHypothesis(gen);
      }

      // Stream SSE response
      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let full = '';
      let buffer = '';

      while (true) {
        if (!this.alive(gen)) break;
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          const data = line.slice(6).trim();
          if (data === '[DONE]') break;
          try {
            const parsed = JSON.parse(data);
            const token = parsed.choices?.[0]?.delta?.content;
            if (token) {
              full += token;
              this.emit({ type: 'hypothesis_chunk', text: token });
              await this.delay(15);
            }
          } catch { /* skip malformed chunk */ }
        }
      }
      return full || await this.generateTemplateHypothesis(gen);
    } catch {
      return this.generateTemplateHypothesis(gen);
    }
  }

  /* ── Allocation nudge (cosmetic) ── */

  private nudgeAllocations(): void {
    const keys = Object.keys(this.state.allocations);
    const up = pickRandom(keys);
    const down = pickRandom(keys.filter(k => k !== up));
    const delta = 0.01 + Math.random() * 0.03;
    this.state.allocations[up] = clamp(this.state.allocations[up]! + delta, 0.01, 0.25);
    this.state.allocations[down] = clamp(this.state.allocations[down]! - delta, 0.01, 0.25);
    // Renormalize
    const total = Object.values(this.state.allocations).reduce((s, v) => s + v, 0);
    for (const k of keys) {
      this.state.allocations[k] = this.state.allocations[k]! / total;
    }
  }
}

/* ── Module-level singleton ──
   Survives component rebuilds, HMR, and DOM destruction.
   The LiveResearcherPage reconnects to it on mount. */

// eslint-disable-next-line no-var
let _singleton: ResearchSimulator | null = null;

/** Get or create the singleton simulator. */
export function getResearchSimulator(onEvent: (event: ResearchEvent) => void): ResearchSimulator {
  if (!_singleton) {
    _singleton = new ResearchSimulator(onEvent);
  } else {
    // Reconnect the event callback to the new DOM
    _singleton.setOnEvent(onEvent);
  }
  return _singleton;
}
