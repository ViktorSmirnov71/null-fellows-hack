/**
 * LiveResearcherPage — full-page component for the "Auto Researcher" tab.
 * Visualises the Karpathy-style autoresearch loop in real time: a pipeline
 * column, scrolling terminal, and D3 metrics sidebar.
 */

import * as d3 from 'd3';
import { escapeHtml } from '@/utils/sanitize';
import {
  getResearchSimulator,
  type ResearchSimulator,
  type ResearchEvent,
  type PipelineStage,
  type ExperimentRecord,
} from '@/services/research-simulator';

/* ── Stage definitions ── */

const STAGES: { key: PipelineStage; num: string; title: string }[] = [
  { key: 'data_ingest', num: '01', title: 'Data Ingest' },
  { key: 'sentiment',   num: '02', title: 'Sentiment Analysis' },
  { key: 'hypothesis',  num: '03', title: 'LLM Hypothesis' },
  { key: 'backtest',    num: '04', title: 'Backtest (5yr)' },
  { key: 'decision',    num: '05', title: 'Decision Gate' },
];

const MAX_LOG_ENTRIES = 500;

/* ── Component ── */

export class LiveResearcherPage {
  public readonly element: HTMLDivElement;

  private sim: ResearchSimulator;
  private terminalScroll!: HTMLDivElement;
  private logCount = 0;
  private stageEls = new Map<PipelineStage, HTMLDivElement>();
  private connectorEls: HTMLDivElement[] = [];
  private progressFill: HTMLDivElement | null = null;
  private decisionBadgeEl: HTMLDivElement | null = null;
  private hypothesisDetailEl: HTMLDivElement | null = null;
  private typingEl: HTMLSpanElement | null = null;
  private chartContainer: HTMLDivElement | null = null;
  private tileEls: Record<string, HTMLDivElement> = {};
  private expListEl: HTMLDivElement | null = null;
  private headerStatsEl: HTMLDivElement | null = null;
  private pulseEl: HTMLDivElement | null = null;
  private pauseBtn: HTMLButtonElement | null = null;
  private speedBtns: HTMLButtonElement[] = [];

  constructor() {
    this.element = document.createElement('div');
    this.element.className = 'lr-root';

    // Use singleton simulator — survives DOM rebuilds and HMR
    this.sim = getResearchSimulator(this.handleEvent.bind(this));

    // Try to get Groq key
    this.loadGroqKey();

    this.buildDOM();

    // Replay existing state into the fresh DOM
    this.replayState();
  }

  /** Restore metrics/chart/list from existing simulator state (e.g. after HMR rebuild) */
  private replayState(): void {
    const st = this.sim.getState();
    if (st.experimentCount === 0) return; // nothing to replay

    this.log('system', `[RECONNECTED] Restored ${st.experimentCount} experiments (${st.kept} kept)`, 'lr-log-kept');
    this.updateMetrics();
    this.updateExperimentList();
    this.renderSharpeChart();
  }

  /* ── Lifecycle ── */

  activate(): void {
    // forceStart kills any stale loop and starts fresh — never gets stuck
    this.sim.forceStart();
    if (this.pulseEl) this.pulseEl.classList.remove('paused');
    if (this.pauseBtn) this.pauseBtn.textContent = 'PAUSE';
  }

  deactivate(): void {
    this.sim.pause();
    if (this.pulseEl) this.pulseEl.classList.add('paused');
    if (this.pauseBtn) this.pauseBtn.textContent = 'RESUME';
  }

  /* ── Groq key ── */

  private async loadGroqKey(): Promise<void> {
    try {
      const { getRuntimeConfigSnapshot } = await import('@/services/runtime-config');
      const key = getRuntimeConfigSnapshot().secrets['GROQ_API_KEY']?.value;
      if (key) {
        this.sim.setGroqApiKey(key);
        this.log('system', '[INIT] Groq API key detected — live LLM reasoning enabled', 'lr-log-kept');
      } else {
        this.log('system', '[INIT] No Groq key — using template-based hypotheses', 'lr-log-dim');
      }
    } catch {
      this.log('system', '[INIT] Runtime config unavailable — using templates', 'lr-log-dim');
    }
  }

  /* ── DOM construction ── */

  private buildDOM(): void {
    // ── Header ──
    const header = document.createElement('div');
    header.className = 'lr-header';
    header.innerHTML = `
      <div class="lr-pulse" id="lrPulse"></div>
      <div class="lr-header-title">Autonomous Research Loop</div>
      <div class="lr-header-stats" id="lrHeaderStats">
        <span class="lr-stat">EXP <b>0</b></span>
        <span class="lr-stat lr-stat-kept">KEPT <b>0</b></span>
        <span class="lr-stat lr-stat-disc">DISC <b>0</b></span>
        <span class="lr-stat lr-stat-crash">ERR <b>0</b></span>
      </div>
      <div class="lr-speed-controls" id="lrSpeedControls">
        <button class="lr-speed-btn active" data-speed="1">1x</button>
        <button class="lr-speed-btn" data-speed="2">2x</button>
        <button class="lr-speed-btn" data-speed="5">5x</button>
      </div>
      <button class="lr-pause-btn" id="lrPauseBtn">PAUSE</button>`;
    this.element.appendChild(header);

    this.pulseEl = header.querySelector('#lrPulse');
    this.headerStatsEl = header.querySelector('#lrHeaderStats');
    this.pauseBtn = header.querySelector('#lrPauseBtn');

    // Speed buttons
    const speedContainer = header.querySelector('#lrSpeedControls')!;
    this.speedBtns = Array.from(speedContainer.querySelectorAll('.lr-speed-btn'));
    speedContainer.addEventListener('click', (e) => {
      const btn = (e.target as HTMLElement).closest('.lr-speed-btn') as HTMLButtonElement | null;
      if (!btn) return;
      const spd = parseInt(btn.dataset.speed!, 10);
      this.sim.setSpeed(spd);
      this.speedBtns.forEach(b => b.classList.toggle('active', b === btn));
    });

    // Pause button
    this.pauseBtn!.addEventListener('click', () => {
      const st = this.sim.getState();
      if (st.running) {
        this.deactivate();
      } else {
        this.activate();
      }
    });

    // ── Body (3-column grid) ──
    const body = document.createElement('div');
    body.className = 'lr-body';
    this.element.appendChild(body);

    body.appendChild(this.buildPipeline());
    body.appendChild(this.buildTerminal());
    body.appendChild(this.buildMetrics());
  }

  /* ── Pipeline column ── */

  private buildPipeline(): HTMLDivElement {
    const col = document.createElement('div');
    col.className = 'lr-pipeline';

    STAGES.forEach((s, i) => {
      const card = document.createElement('div');
      card.className = 'lr-stage';
      card.dataset.stage = s.key;
      card.innerHTML = `
        <div class="lr-stage-num">STAGE ${s.num}</div>
        <div class="lr-stage-title">${s.title}</div>
        <div class="lr-stage-detail" id="lrStageDetail_${s.key}"></div>
        ${s.key === 'backtest' ? '<div class="lr-progress-bar"><div class="lr-progress-fill" id="lrProgressFill" style="width:0%"></div></div>' : ''}
        ${s.key === 'decision' ? '<div id="lrDecisionBadge"></div>' : ''}
        ${s.key === 'hypothesis' ? '<div class="lr-stage-detail" id="lrHypothesisDetail" style="margin-top:4px;color:var(--text-dim);max-height:60px;overflow:hidden;font-size:9px"></div>' : ''}`;
      this.stageEls.set(s.key, card);
      col.appendChild(card);

      // Connector between stages
      if (i < STAGES.length - 1) {
        const conn = document.createElement('div');
        conn.className = 'lr-connector';
        this.connectorEls.push(conn);
        col.appendChild(conn);
      }
    });

    this.progressFill = col.querySelector('#lrProgressFill');
    this.decisionBadgeEl = col.querySelector('#lrDecisionBadge');
    this.hypothesisDetailEl = col.querySelector('#lrHypothesisDetail');

    return col;
  }

  /* ── Terminal ── */

  private buildTerminal(): HTMLDivElement {
    const wrap = document.createElement('div');
    wrap.className = 'lr-terminal';
    wrap.innerHTML = `<div class="lr-terminal-header">Research Log &mdash; Live Stream</div>`;

    this.terminalScroll = document.createElement('div');
    this.terminalScroll.className = 'lr-terminal-scroll';
    wrap.appendChild(this.terminalScroll);

    // Initial messages
    this.log('system', '══════════════════════════════════════════════════', 'lr-log-dim');
    this.log('system', '  AUTORESEARCH ENGINE v1.0 — Null Fellows', 'lr-log-kept');
    this.log('system', '  Adapted from karpathy/autoresearch', 'lr-log-dim');
    this.log('system', '  Loop: Ingest → Sentiment → Hypothesize → Backtest → Decide', 'lr-log-dim');
    this.log('system', '══════════════════════════════════════════════════', 'lr-log-dim');
    this.log('system', '', 'lr-log-dim');

    return wrap;
  }

  /* ── Metrics sidebar ── */

  private buildMetrics(): HTMLDivElement {
    const col = document.createElement('div');
    col.className = 'lr-metrics';

    // Summary tiles
    const tilesSection = document.createElement('div');
    tilesSection.className = 'lr-metrics-section';
    tilesSection.innerHTML = `<div class="lr-section-label">Performance</div><div class="lr-tiles" id="lrTiles">
      <div class="lr-tile"><div class="lr-tile-label">Best Sharpe</div><div class="lr-tile-value" id="lrTileSharpe">1.240</div><div class="lr-tile-sub" id="lrTileSharpeSub">vs 0.54 benchmark</div></div>
      <div class="lr-tile"><div class="lr-tile-label">Keep Rate</div><div class="lr-tile-value" id="lrTileKeepRate">—</div><div class="lr-tile-sub" id="lrTileKeepSub">0 experiments</div></div>
      <div class="lr-tile"><div class="lr-tile-label">Improvement</div><div class="lr-tile-value" id="lrTileImprove">+130%</div><div class="lr-tile-sub">vs 60/40 portfolio</div></div>
      <div class="lr-tile"><div class="lr-tile-label">Status</div><div class="lr-tile-value" id="lrTileStatus" style="color:#00e676;font-size:11px">RUNNING</div><div class="lr-tile-sub" id="lrTileStatusSub">experiment #0</div></div>
    </div>`;
    col.appendChild(tilesSection);

    this.tileEls = {
      sharpe: tilesSection.querySelector('#lrTileSharpe')!,
      sharpeSub: tilesSection.querySelector('#lrTileSharpeSub')!,
      keepRate: tilesSection.querySelector('#lrTileKeepRate')!,
      keepSub: tilesSection.querySelector('#lrTileKeepSub')!,
      improve: tilesSection.querySelector('#lrTileImprove')!,
      status: tilesSection.querySelector('#lrTileStatus')!,
      statusSub: tilesSection.querySelector('#lrTileStatusSub')!,
    };

    // Sharpe frontier chart
    const chartSection = document.createElement('div');
    chartSection.className = 'lr-metrics-section';
    chartSection.innerHTML = `<div class="lr-section-label">Sharpe Frontier</div>`;
    this.chartContainer = document.createElement('div');
    this.chartContainer.className = 'lr-chart-container';
    chartSection.appendChild(this.chartContainer);
    col.appendChild(chartSection);

    // Experiment history
    const histSection = document.createElement('div');
    histSection.className = 'lr-metrics-section';
    histSection.innerHTML = `<div class="lr-section-label">Experiment Log</div>`;
    this.expListEl = document.createElement('div');
    this.expListEl.className = 'lr-exp-list';
    histSection.appendChild(this.expListEl);
    col.appendChild(histSection);

    return col;
  }

  /* ── Event handler ── */

  private handleEvent(event: ResearchEvent): void {
    switch (event.type) {
      case 'stage_change':
        this.updatePipelineStage(event.stage);
        break;

      case 'data_ingest':
        this.updateStageDetail('data_ingest', `${event.source}: ${event.tickersUpdated.join(', ')}`);
        this.log('data', `[DATA] ${event.source} — ${event.detail}`, 'lr-log-data');
        break;

      case 'sentiment':
        this.updateStageDetail('sentiment', event.detail.slice(0, 80));
        if (event.tier === 'groq_filter') {
          this.log('groq', `[GROQ] ${event.detail}`, 'lr-log-groq');
        } else if (event.tier === 'finbert') {
          this.log('finbert', `[FINBERT] ${event.detail}`, 'lr-log-finbert');
        } else {
          this.log('claude', `[CLAUDE] ${event.detail}`, 'lr-log-groq');
        }
        break;

      case 'hypothesis_start':
        this.updateStageDetail('hypothesis', `Experiment #${event.experimentId} — generating...`);
        if (this.hypothesisDetailEl) this.hypothesisDetailEl.textContent = '';
        this.typingEl = document.createElement('span');
        this.typingEl.className = 'lr-typing-cursor';
        this.log('llm', `[LLM] Experiment #${event.experimentId} — reasoning:`, 'lr-log-llm');
        this.startTypingLine();
        break;

      case 'hypothesis_chunk':
        if (this.typingEl) {
          this.typingEl.textContent += event.text;
          this.autoScrollTerminal();
        }
        if (this.hypothesisDetailEl) {
          this.hypothesisDetailEl.textContent += event.text;
        }
        break;

      case 'hypothesis_end':
        if (this.typingEl) {
          this.typingEl.classList.remove('lr-typing-cursor');
          this.typingEl = null;
        }
        this.updateStageDetail('hypothesis', 'Done');
        break;

      case 'backtest_progress':
        if (this.progressFill) {
          this.progressFill.style.width = `${event.pct}%`;
        }
        this.updateStageDetail('backtest', `${event.pct}% — ${event.elapsed}${event.currentMetric ? ` — computing ${event.currentMetric}` : ''}`);
        if (event.currentMetric) {
          this.log('bt', `[BACKTEST] Computing ${event.currentMetric}... (${event.pct}%)`, 'lr-log-backtest');
        }
        break;

      case 'backtest_result': {
        const m = event.metrics;
        if (isNaN(m.sharpe)) {
          this.log('bt', `[BACKTEST] ✗ CRASH — NaN encountered`, 'lr-log-crash');
        } else {
          this.log('bt', `[BACKTEST] Sharpe=${m.sharpe.toFixed(3)} Sortino=${m.sortino.toFixed(3)} MaxDD=${(m.maxDrawdown * 100).toFixed(1)}% Calmar=${m.calmar.toFixed(2)} CAGR=${(m.cagr * 100).toFixed(1)}%`, 'lr-log-backtest');
        }
        break;
      }

      case 'decision': {
        if (this.progressFill) this.progressFill.style.width = '0%';

        const statusClass = event.status === 'KEPT' ? 'lr-badge-kept' : event.status === 'DISCARDED' ? 'lr-badge-discarded' : 'lr-badge-crash';
        const logClass = event.status === 'KEPT' ? 'lr-log-kept' : event.status === 'DISCARDED' ? 'lr-log-discarded' : 'lr-log-crash';

        if (this.decisionBadgeEl) {
          this.decisionBadgeEl.innerHTML = `<div class="lr-decision-badge ${statusClass}">${event.status}</div>`;
        }
        this.updateStageDetail('decision', event.status === 'KEPT'
          ? `Sharpe improved: ${event.prevBestSharpe.toFixed(3)} → ${event.metrics.sharpe.toFixed(3)}`
          : event.status === 'CRASH' ? 'Experiment crashed' : `No improvement (${isNaN(event.metrics.sharpe) ? 'NaN' : event.metrics.sharpe.toFixed(3)} ≤ ${event.prevBestSharpe.toFixed(3)})`);

        this.log('decision', '', 'lr-log-decision-line');
        if (event.status === 'KEPT') {
          this.log('decision', `[✓ KEPT] #${event.experimentId} — Sharpe ${event.prevBestSharpe.toFixed(3)} → ${event.metrics.sharpe.toFixed(3)} (+${((event.metrics.sharpe - event.prevBestSharpe) * 1000).toFixed(0)} bps)`, logClass);
        } else if (event.status === 'CRASH') {
          this.log('decision', `[✗ CRASH] #${event.experimentId} — experiment failed`, logClass);
        } else {
          this.log('decision', `[— DISCARDED] #${event.experimentId} — Sharpe ${isNaN(event.metrics.sharpe) ? 'NaN' : event.metrics.sharpe.toFixed(3)} did not beat ${event.prevBestSharpe.toFixed(3)}`, logClass);
        }
        this.log('decision', '', 'lr-log-dim');

        // Update metrics
        this.updateMetrics();
        this.updateExperimentList();
        this.renderSharpeChart();
        break;
      }

      case 'error':
        this.log('error', `[ERROR] ${event.message}`, 'lr-log-error');
        break;
    }
  }

  /* ── Pipeline stage highlighting ── */

  private updatePipelineStage(active: PipelineStage): void {
    const stageIdx = STAGES.findIndex(s => s.key === active);

    STAGES.forEach((s, i) => {
      const el = this.stageEls.get(s.key);
      if (!el) return;
      el.classList.remove('lr-stage-active', 'lr-stage-done');
      if (s.key === active) {
        el.classList.add('lr-stage-active');
      } else if (active !== 'idle' && i < stageIdx) {
        el.classList.add('lr-stage-done');
      }
    });

    // Connector animation
    this.connectorEls.forEach((c, i) => {
      c.classList.toggle('lr-connector-active', active !== 'idle' && i < stageIdx);
    });
  }

  private updateStageDetail(stage: PipelineStage, text: string): void {
    const el = this.element.querySelector(`#lrStageDetail_${stage}`) as HTMLDivElement | null;
    if (el) el.textContent = text;
  }

  /* ── Terminal logging ── */

  private log(_category: string, text: string, cssClass: string): void {
    const entry = document.createElement('div');
    entry.className = `lr-log-entry ${cssClass}`;
    if (text) {
      const ts = new Date().toLocaleTimeString('en-GB', { hour12: false });
      entry.innerHTML = `<span class="lr-log-dim">${ts}</span> ${escapeHtml(text)}`;
    }
    this.terminalScroll.appendChild(entry);
    this.logCount++;

    // Cap entries
    while (this.logCount > MAX_LOG_ENTRIES) {
      this.terminalScroll.removeChild(this.terminalScroll.firstChild!);
      this.logCount--;
    }

    this.autoScrollTerminal();
  }

  private startTypingLine(): void {
    if (!this.typingEl) return;
    const entry = document.createElement('div');
    entry.className = 'lr-log-entry lr-log-llm';
    const ts = new Date().toLocaleTimeString('en-GB', { hour12: false });
    const tsSpan = document.createElement('span');
    tsSpan.className = 'lr-log-dim';
    tsSpan.textContent = ts + ' ';
    entry.appendChild(tsSpan);
    entry.appendChild(this.typingEl);
    this.terminalScroll.appendChild(entry);
    this.logCount++;
  }

  private autoScrollTerminal(): void {
    const el = this.terminalScroll;
    // Only auto-scroll if user is near bottom
    if (el.scrollHeight - el.scrollTop - el.clientHeight < 80) {
      el.scrollTop = el.scrollHeight;
    }
  }

  /* ── Metrics updates ── */

  private updateMetrics(): void {
    const st = this.sim.getState();

    // Header stats
    if (this.headerStatsEl) {
      this.headerStatsEl.innerHTML = `
        <span class="lr-stat">EXP <b>${st.experimentCount}</b></span>
        <span class="lr-stat lr-stat-kept">KEPT <b>${st.kept}</b></span>
        <span class="lr-stat lr-stat-disc">DISC <b>${st.discarded}</b></span>
        <span class="lr-stat lr-stat-crash">ERR <b>${st.crashed}</b></span>`;
    }

    // Tiles
    if (this.tileEls.sharpe) {
      this.tileEls.sharpe.textContent = st.bestSharpe.toFixed(3);
      if (this.tileEls.sharpeSub) this.tileEls.sharpeSub.textContent = `vs ${st.benchmarkSharpe} benchmark`;
    }
    if (this.tileEls.keepRate) {
      const rate = st.experimentCount > 0 ? ((st.kept / st.experimentCount) * 100).toFixed(0) : '—';
      this.tileEls.keepRate.textContent = `${rate}%`;
      if (this.tileEls.keepSub) this.tileEls.keepSub.textContent = `${st.experimentCount} experiments`;
    }
    if (this.tileEls.improve) {
      const pct = ((st.bestSharpe / st.benchmarkSharpe - 1) * 100).toFixed(0);
      this.tileEls.improve.textContent = `+${pct}%`;
      this.tileEls.improve.style.color = '#00e676';
    }
    if (this.tileEls.status && this.tileEls.statusSub) {
      this.tileEls.statusSub.textContent = `experiment #${st.experimentCount}`;
    }
  }

  /* ── Experiment list ── */

  private updateExperimentList(): void {
    if (!this.expListEl) return;
    const exps = this.sim.getState().experiments;
    // Show last 15, newest first
    const recent = exps.slice(-15).reverse();

    this.expListEl.innerHTML = recent.map((e: ExperimentRecord) => {
      const statusClass = e.status.toLowerCase();
      const sharpeStr = isNaN(e.metrics.sharpe) ? 'CRASH' : e.metrics.sharpe.toFixed(3);
      const sharpeColor = e.status === 'KEPT' ? '#00e676' : e.status === 'CRASH' ? '#ff9800' : 'var(--text-dim)';
      return `<div class="lr-exp-card ${statusClass}">
        <div class="lr-exp-card-header">
          <span class="lr-exp-card-id">#${e.id}</span>
          <span class="lr-exp-card-sharpe" style="color:${sharpeColor}">${sharpeStr}</span>
        </div>
        <div class="lr-exp-card-desc">${escapeHtml(e.description.slice(0, 100))}</div>
      </div>`;
    }).join('');
  }

  /* ── D3 Sharpe Frontier Chart ── */

  private renderSharpeChart(): void {
    if (!this.chartContainer) return;
    this.chartContainer.innerHTML = '';

    const exps = this.sim.getState().experiments;
    if (exps.length === 0) return;

    const width = this.chartContainer.clientWidth || 230;
    const height = 130;
    const margin = { top: 8, right: 8, bottom: 22, left: 38 };
    const iW = width - margin.left - margin.right;
    const iH = height - margin.top - margin.bottom;

    const svg = d3.select(this.chartContainer)
      .append('svg')
      .attr('width', width)
      .attr('height', height)
      .style('display', 'block');

    const g = svg.append('g')
      .attr('transform', `translate(${margin.left},${margin.top})`);

    // Scales
    const x = d3.scaleLinear()
      .domain([1, Math.max(exps.length, 5)])
      .range([0, iW]);

    const allSharpe = exps.filter((e: ExperimentRecord) => !isNaN(e.metrics.sharpe)).map((e: ExperimentRecord) => e.metrics.sharpe);
    const yMin = Math.min(0.5, ...allSharpe) - 0.05;
    const yMax = Math.max(1.5, ...allSharpe) + 0.05;
    const y = d3.scaleLinear().domain([yMin, yMax]).range([iH, 0]);

    // Gridlines
    g.selectAll('.lr-grid')
      .data(y.ticks(4))
      .join('line')
      .attr('x1', 0).attr('x2', iW)
      .attr('y1', d => y(d)).attr('y2', d => y(d))
      .attr('stroke', 'rgba(255,255,255,0.04)')
      .attr('stroke-dasharray', '2,4');

    // Benchmark line
    const benchY = y(0.54);
    g.append('line')
      .attr('x1', 0).attr('x2', iW)
      .attr('y1', benchY).attr('y2', benchY)
      .attr('stroke', 'rgba(255,23,68,0.3)')
      .attr('stroke-dasharray', '4,4');
    g.append('text')
      .attr('x', iW - 2).attr('y', benchY - 4)
      .attr('text-anchor', 'end')
      .attr('fill', 'rgba(255,23,68,0.5)')
      .attr('font-size', '8px')
      .attr('font-family', 'var(--font-mono)')
      .text('60/40');

    // Running best step line
    let runBest = 0;
    const stepData: { x: number; y: number }[] = [];
    for (const e of exps) {
      if (e.status === 'KEPT' && !isNaN(e.metrics.sharpe)) runBest = e.metrics.sharpe;
      if (runBest > 0) stepData.push({ x: e.id, y: runBest });
    }

    if (stepData.length > 0) {
      const stepLine = d3.line<{ x: number; y: number }>()
        .x(d => x(d.x))
        .y(d => y(d.y))
        .curve(d3.curveStepAfter);

      g.append('path')
        .datum(stepData)
        .attr('d', stepLine)
        .attr('fill', 'none')
        .attr('stroke', '#00e676')
        .attr('stroke-width', 1.5)
        .attr('opacity', 0.6);
    }

    // Scatter dots
    for (const e of exps) {
      if (isNaN(e.metrics.sharpe)) continue;
      const dotColor = e.status === 'KEPT' ? '#00e676' : e.status === 'CRASH' ? '#ff9800' : 'rgba(255,255,255,0.2)';
      const r = e.status === 'KEPT' ? 4 : 2.5;
      g.append('circle')
        .attr('cx', x(e.id))
        .attr('cy', y(e.metrics.sharpe))
        .attr('r', r)
        .attr('fill', dotColor)
        .attr('opacity', e.status === 'KEPT' ? 0.9 : 0.5);
    }

    // Axes
    g.append('g')
      .attr('transform', `translate(0,${iH})`)
      .call(d3.axisBottom(x).ticks(Math.min(exps.length, 6)).tickFormat(d => `#${d}`).tickSize(0))
      .attr('class', 'pf-axis')
      .select('.domain').attr('stroke', 'rgba(255,255,255,0.06)');

    g.append('g')
      .call(d3.axisLeft(y).ticks(4).tickFormat(d => (d as number).toFixed(2)).tickSize(0))
      .attr('class', 'pf-axis')
      .select('.domain').attr('stroke', 'rgba(255,255,255,0.06)');
  }
}
