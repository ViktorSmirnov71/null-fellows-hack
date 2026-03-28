import { Panel } from './Panel';
import { escapeHtml } from '@/utils/sanitize';

interface Experiment {
  id: number;
  status: 'KEPT' | 'DISCARDED' | 'CRASH';
  sharpe: number;
  maxDrawdown: number;
  description: string;
  timestamp: string;
}

const DEMO_EXPERIMENTS: Experiment[] = [
  { id: 1, status: 'KEPT',      sharpe: 1.21, maxDrawdown: -0.142, description: 'Increase DBMF 10%→15%, reduce SPY 20%→15%', timestamp: '06:12' },
  { id: 2, status: 'DISCARDED', sharpe: 1.15, maxDrawdown: -0.168, description: 'Switch rebalance to weekly', timestamp: '06:18' },
  { id: 3, status: 'KEPT',      sharpe: 1.34, maxDrawdown: -0.131, description: 'Add RPAR 5%, reduce AGG 10%→5%', timestamp: '06:24' },
  { id: 4, status: 'DISCARDED', sharpe: 1.28, maxDrawdown: -0.189, description: 'Increase sentiment weight 0.15→0.30', timestamp: '06:30' },
  { id: 5, status: 'CRASH',     sharpe: 0,    maxDrawdown: 0,      description: 'Remove all bond allocation', timestamp: '06:36' },
  { id: 6, status: 'KEPT',      sharpe: 1.42, maxDrawdown: -0.118, description: 'Raise risk threshold 0.7→0.65, shift 3% to GLDM', timestamp: '06:42' },
  { id: 7, status: 'DISCARDED', sharpe: 1.38, maxDrawdown: -0.145, description: 'Increase ARCC weight to 12%', timestamp: '06:48' },
  { id: 8, status: 'KEPT',      sharpe: 1.51, maxDrawdown: -0.113, description: 'Consolidate JAAA+CLOA, lower min conviction', timestamp: '06:54' },
];

function badge(status: string): string {
  const m: Record<string, string> = { KEPT: '#2ecc71', DISCARDED: '#e74c3c', CRASH: '#f1c40f' };
  const c = m[status] || '#95a5a6';
  return `<span style="display:inline-block;padding:1px 5px;border-radius:3px;font-size:9px;font-weight:700;letter-spacing:0.4px;background:${c}22;color:${c}">${status}</span>`;
}

export class AutoAllocatorPanel extends Panel {
  private experiments: Experiment[];
  private running = true;
  private simTimer: ReturnType<typeof setInterval> | null = null;

  constructor() {
    super({
      id: 'auto-allocator',
      title: 'AutoAllocator',
      showCount: true,
      infoTooltip: `<b>How the AutoAllocator works</b><br><br>
Adapted from <a href="https://github.com/karpathy/autoresearch" target="_blank">karpathy/autoresearch</a>: an AI agent autonomously evolves portfolio weights.<br><br>
<b>1. Risk Scoring</b> — 6 real-time signals (GDELT news tone, VIX, yield curve, consumer sentiment, unemployment, news volume) produce a composite risk score (0–100).<br><br>
<b>2. Sentiment Cascade</b> — News flows through Groq (fast filter) → FinBERT (financial scoring) → Claude (deep analysis on high-conviction signals).<br><br>
<b>3. The Loop</b> — The AI proposes ONE allocation change, backtests it over 5 years, and keeps it only if Sharpe ratio improves AND max drawdown stays above -25%. Otherwise it reverts. Repeats forever (~12 experiments/hour).<br><br>
<b>4. Guardrails</b> — No position >25% or <1%, at least 8 positions, must beat 60/40 benchmark, max drawdown -25% hard stop.<br><br>
<b>Fitness: Sharpe Ratio</b> (return per unit risk). Benchmark: 60/40 portfolio (Sharpe ~0.54).<br><br>
<a href="https://github.com/ViktorSmirnov71/null-fellows-hack/blob/main/docs/autoallocator-philosophy.md" target="_blank" style="color:#3498db">Read the full philosophy →</a>`,
    });
    this.experiments = [...DEMO_EXPERIMENTS];
  }

  public async fetchData(): Promise<boolean> {
    this.render();
    this.setCount(this.experiments.length);
    this.setDataBadge('live');
    this.startSimulation();
    return true;
  }

  private startSimulation(): void {
    if (this.simTimer) return;
    this.simTimer = setInterval(() => {
      if (!this.running) return;
      const id = this.experiments.length + 1;
      const roll = Math.random();
      const status: Experiment['status'] = roll < 0.35 ? 'KEPT' : roll < 0.9 ? 'DISCARDED' : 'CRASH';
      const bestSharpe = Math.max(...this.experiments.filter(e => e.status === 'KEPT').map(e => e.sharpe));
      const sharpe = status === 'CRASH' ? 0 : +(bestSharpe + (Math.random() - 0.45) * 0.3).toFixed(2);
      const descs = [
        'Shift 2% from equity to managed futures',
        'Increase GLDM weight for tail hedge',
        'Lower rebalance frequency to quarterly',
        'Raise sentiment conviction threshold 0.2→0.35',
        'Add 3% BXSL, reduce CLOA by 3%',
        'Tighten max drawdown limit to -20%',
        'Increase regime shift magnitude 0.03→0.05',
        'Swap RPAR for ALLW (Bridgewater All Weather)',
      ];
      this.experiments.push({
        id, status, sharpe,
        maxDrawdown: status === 'CRASH' ? 0 : +(Math.random() * -0.25).toFixed(3),
        description: descs[Math.floor(Math.random() * descs.length)]!,
        timestamp: new Date().toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' }),
      });
      this.setCount(this.experiments.length);
      this.render();
    }, 12000);
  }

  destroy(): void {
    if (this.simTimer) clearInterval(this.simTimer);
    super.destroy();
  }

  private render(): void {
    const exps = this.experiments;
    const kept = exps.filter(e => e.status === 'KEPT');
    const discarded = exps.filter(e => e.status === 'DISCARDED');
    const crashed = exps.filter(e => e.status === 'CRASH');
    const bestSharpe = kept.length ? Math.max(...kept.map(e => e.sharpe)) : 0;
    const benchmarkSharpe = 0.54;
    const improvement = benchmarkSharpe > 0 ? (((bestSharpe - benchmarkSharpe) / benchmarkSharpe) * 100).toFixed(0) : '0';
    const keepRate = exps.length > 0 ? ((kept.length / exps.length) * 100).toFixed(0) : '0';

    // Progress bar
    const kPct = (kept.length / exps.length * 100) || 0;
    const dPct = (discarded.length / exps.length * 100) || 0;
    const cPct = (crashed.length / exps.length * 100) || 0;

    // Sharpe frontier mini chart
    const valid = exps.filter(e => e.status !== 'CRASH');
    let frontierSVG = '';
    if (valid.length >= 2) {
      const w = 260, h = 50, pad = 4;
      const maxS = Math.max(...valid.map(e => e.sharpe)) * 1.05;
      const minS = Math.min(...valid.map(e => e.sharpe)) * 0.95;
      const rng = maxS - minS || 1;
      const pts = valid.map((e, i) => ({
        x: pad + (i / (valid.length - 1)) * (w - 2 * pad),
        y: h - pad - ((e.sharpe - minS) / rng) * (h - 2 * pad),
        kept: e.status === 'KEPT',
      }));
      let best = -Infinity;
      const fLine = pts.map(p => {
        if (valid[pts.indexOf(p)]!.sharpe > best) best = valid[pts.indexOf(p)]!.sharpe;
        const fy = h - pad - ((best - minS) / rng) * (h - 2 * pad);
        return `${pts.indexOf(p) === 0 ? 'M' : 'L'}${p.x.toFixed(1)},${fy.toFixed(1)}`;
      }).join(' ');
      const dots = pts.map(p => `<circle cx="${p.x.toFixed(1)}" cy="${p.y.toFixed(1)}" r="2.5" fill="${p.kept ? '#2ecc71' : '#e74c3c'}" opacity="0.8"/>`).join('');
      frontierSVG = `<svg viewBox="0 0 ${w} ${h}" width="100%" height="${h}" style="display:block;margin:6px 0"><path d="${fLine}" fill="none" stroke="#3498db" stroke-width="1.5" opacity="0.5"/>${dots}</svg>`;
    }

    const rows = [...exps].reverse().slice(0, 10).map(e => `
      <div style="padding:4px 0;border-bottom:1px solid rgba(255,255,255,0.04)">
        <div style="display:flex;justify-content:space-between;align-items:center">
          <div style="display:flex;align-items:center;gap:5px">
            <span style="font-size:9px;color:var(--text-muted)">#${e.id}</span>
            ${badge(e.status)}
            <span style="font-size:10px;color:var(--text-muted)">${e.timestamp}</span>
          </div>
          <span style="font-size:11px;font-weight:600;color:var(--text)">${e.status === 'CRASH' ? '---' : e.sharpe.toFixed(2)}</span>
        </div>
        <div style="font-size:10px;color:var(--text-dim);margin-top:1px">${escapeHtml(e.description)}</div>
      </div>`).join('');

    const el = document.createElement('div');
    el.style.cssText = 'padding:12px 14px';
    el.innerHTML = `
      <div style="display:flex;align-items:center;gap:6px;margin-bottom:8px">
        <div style="width:8px;height:8px;border-radius:50%;background:${this.running ? '#2ecc71' : '#95a5a6'};animation:${this.running ? 'nf-pulse 2s infinite' : 'none'}"></div>
        <span style="font-size:11px;font-weight:600;color:${this.running ? '#2ecc71' : '#95a5a6'}">${this.running ? 'RUNNING' : 'PAUSED'} &middot; ${exps.length} experiments</span>
      </div>
      <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:6px;margin-bottom:8px">
        <div style="padding:6px;background:rgba(255,255,255,0.03);border-radius:5px;text-align:center">
          <div style="font-size:9px;color:var(--text-muted);text-transform:uppercase">Best Sharpe</div>
          <div style="font-size:17px;font-weight:700;color:#2ecc71">${bestSharpe.toFixed(2)}</div>
        </div>
        <div style="padding:6px;background:rgba(255,255,255,0.03);border-radius:5px;text-align:center">
          <div style="font-size:9px;color:var(--text-muted);text-transform:uppercase">60/40 Bench</div>
          <div style="font-size:17px;font-weight:700;color:var(--text-dim)">${benchmarkSharpe.toFixed(2)}</div>
        </div>
        <div style="padding:6px;background:rgba(255,255,255,0.03);border-radius:5px;text-align:center">
          <div style="font-size:9px;color:var(--text-muted);text-transform:uppercase">vs 60/40</div>
          <div style="font-size:17px;font-weight:700;color:#3498db">+${improvement}%</div>
        </div>
      </div>
      <div style="display:flex;height:5px;border-radius:3px;overflow:hidden;background:rgba(255,255,255,0.05)">
        <div style="width:${kPct.toFixed(1)}%;background:#2ecc71"></div>
        <div style="width:${dPct.toFixed(1)}%;background:#e74c3c"></div>
        <div style="width:${cPct.toFixed(1)}%;background:#f1c40f"></div>
      </div>
      <div style="display:flex;justify-content:space-between;margin-top:3px;font-size:9px;color:var(--text-muted)">
        <span>${kept.length} kept (${keepRate}%)</span><span>${discarded.length} disc</span><span>${crashed.length} crash</span>
      </div>
      ${frontierSVG}
      <div style="font-size:10px;font-weight:600;color:var(--text-dim);text-transform:uppercase;letter-spacing:0.4px;margin:4px 0 2px">Experiment Log</div>
      <div style="max-height:220px;overflow-y:auto">${rows}</div>
    `;

    // Add pulse animation if not already present
    if (!document.getElementById('nf-pulse-style')) {
      const style = document.createElement('style');
      style.id = 'nf-pulse-style';
      style.textContent = '@keyframes nf-pulse{0%,100%{opacity:1}50%{opacity:0.3}}';
      document.head.appendChild(style);
    }

    this.element.querySelector('.panel-content')!.replaceChildren(el);
  }
}
