import { Panel } from './Panel';
import { escapeHtml } from '@/utils/sanitize';

interface Experiment {
  id: number;
  status: 'KEPT' | 'DISCARDED' | 'CRASH';
  sharpe: number;
  sortino: number;
  maxDrawdown: number;
  calmar: number;
  tailRatio: number;
  description: string;
  timestamp: string;
  benchmarkSharpe: number;
}

interface AllocatorState {
  isRunning: boolean;
  totalExperiments: number;
  keptCount: number;
  discardedCount: number;
  crashCount: number;
  bestSharpe: number;
  benchmarkSharpe: number;
  currentIteration: number;
  experiments: Experiment[];
}

function getDemoState(): AllocatorState {
  const experiments: Experiment[] = [
    { id: 1,  status: 'KEPT',      sharpe: 1.21, sortino: 1.65, maxDrawdown: -0.142, calmar: 0.85, tailRatio: 1.08, description: 'Increase DBMF weight 10%→15%, reduce SPY 20%→15%', timestamp: '2026-03-28T06:12:00Z', benchmarkSharpe: 0.54 },
    { id: 2,  status: 'DISCARDED', sharpe: 1.15, sortino: 1.52, maxDrawdown: -0.168, calmar: 0.72, tailRatio: 0.98, description: 'Switch rebalance to weekly', timestamp: '2026-03-28T06:18:00Z', benchmarkSharpe: 0.54 },
    { id: 3,  status: 'KEPT',      sharpe: 1.34, sortino: 1.82, maxDrawdown: -0.131, calmar: 1.02, tailRatio: 1.15, description: 'Add RPAR 5%, reduce AGG 10%→5%', timestamp: '2026-03-28T06:24:00Z', benchmarkSharpe: 0.54 },
    { id: 4,  status: 'DISCARDED', sharpe: 1.28, sortino: 1.71, maxDrawdown: -0.189, calmar: 0.73, tailRatio: 1.10, description: 'Increase sentiment weight 0.15→0.30', timestamp: '2026-03-28T06:30:00Z', benchmarkSharpe: 0.54 },
    { id: 5,  status: 'CRASH',     sharpe: 0,    sortino: 0,    maxDrawdown: 0,      calmar: 0,    tailRatio: 0,    description: 'Remove all bond allocation', timestamp: '2026-03-28T06:36:00Z', benchmarkSharpe: 0.54 },
    { id: 6,  status: 'KEPT',      sharpe: 1.42, sortino: 1.95, maxDrawdown: -0.118, calmar: 1.20, tailRatio: 1.21, description: 'Raise risk threshold 0.7→0.65, shift 3% more to GLDM in high-risk regime', timestamp: '2026-03-28T06:42:00Z', benchmarkSharpe: 0.54 },
    { id: 7,  status: 'DISCARDED', sharpe: 1.38, sortino: 1.88, maxDrawdown: -0.145, calmar: 0.98, tailRatio: 1.18, description: 'Increase ARCC weight to 12%', timestamp: '2026-03-28T06:48:00Z', benchmarkSharpe: 0.54 },
    { id: 8,  status: 'KEPT',      sharpe: 1.51, sortino: 2.10, maxDrawdown: -0.113, calmar: 1.34, tailRatio: 1.24, description: 'Add JAAA 5% from CLOA, lower min conviction 0.3→0.2', timestamp: '2026-03-28T06:54:00Z', benchmarkSharpe: 0.54 },
  ];

  return {
    isRunning: true,
    totalExperiments: experiments.length,
    keptCount: experiments.filter(e => e.status === 'KEPT').length,
    discardedCount: experiments.filter(e => e.status === 'DISCARDED').length,
    crashCount: experiments.filter(e => e.status === 'CRASH').length,
    bestSharpe: 1.51,
    benchmarkSharpe: 0.54,
    currentIteration: 9,
    experiments: experiments.reverse(),
  };
}

function statusBadge(status: string): string {
  const colors: Record<string, { bg: string; fg: string }> = {
    KEPT:      { bg: 'rgba(46,204,113,0.15)', fg: '#2ecc71' },
    DISCARDED: { bg: 'rgba(231,76,60,0.15)',  fg: '#e74c3c' },
    CRASH:     { bg: 'rgba(241,196,15,0.15)', fg: '#f1c40f' },
  };
  const c = colors[status] ?? colors.DISCARDED!;
  return `<span style="display:inline-block;padding:1px 6px;border-radius:3px;font-size:9px;font-weight:700;letter-spacing:0.5px;background:${c!.bg};color:${c!.fg}">${status}</span>`;
}

function renderProgressBar(kept: number, discarded: number, crashed: number, total: number): string {
  const kPct = (kept / total * 100).toFixed(1);
  const dPct = (discarded / total * 100).toFixed(1);
  const cPct = (crashed / total * 100).toFixed(1);
  return `
    <div style="display:flex;height:6px;border-radius:3px;overflow:hidden;background:rgba(255,255,255,0.05)">
      <div style="width:${kPct}%;background:#2ecc71" title="${kept} kept"></div>
      <div style="width:${dPct}%;background:#e74c3c" title="${discarded} discarded"></div>
      <div style="width:${cPct}%;background:#f1c40f" title="${crashed} crashed"></div>
    </div>`;
}

function renderSharpeFrontier(experiments: Experiment[]): string {
  // Mini SVG chart showing Sharpe progression
  const w = 280, h = 60, pad = 4;
  const valid = experiments.filter(e => e.status !== 'CRASH').reverse();
  if (valid.length < 2) return '';

  const maxS = Math.max(...valid.map(e => e.sharpe)) * 1.1;
  const minS = Math.min(...valid.map(e => e.sharpe)) * 0.9;
  const range = maxS - minS || 1;

  const points = valid.map((e, i) => {
    const x = pad + (i / (valid.length - 1)) * (w - 2 * pad);
    const y = h - pad - ((e.sharpe - minS) / range) * (h - 2 * pad);
    return { x, y, status: e.status, sharpe: e.sharpe };
  });

  // Running maximum (frontier)
  let best = -Infinity;
  const frontier: { x: number; y: number }[] = [];
  for (const p of points) {
    if (p.sharpe > best) best = p.sharpe;
    const y = h - pad - ((best - minS) / range) * (h - 2 * pad);
    frontier.push({ x: p.x, y });
  }

  const frontierLine = frontier.map((p, i) => `${i === 0 ? 'M' : 'L'}${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(' ');

  const dots = points.map(p => {
    const fill = p.status === 'KEPT' ? '#2ecc71' : '#e74c3c';
    return `<circle cx="${p.x.toFixed(1)}" cy="${p.y.toFixed(1)}" r="3" fill="${fill}" opacity="0.8"/>`;
  }).join('');

  return `
    <div style="margin:8px 0">
      <div style="font-size:10px;color:var(--text-muted);margin-bottom:4px">SHARPE FRONTIER</div>
      <svg viewBox="0 0 ${w} ${h}" width="100%" height="${h}" style="display:block">
        <path d="${frontierLine}" fill="none" stroke="#3498db" stroke-width="1.5" opacity="0.6"/>
        ${dots}
      </svg>
    </div>`;
}

export class AutoAllocatorPanel extends Panel {
  private state: AllocatorState | null = null;

  constructor() {
    super({
      id: 'auto-allocator',
      title: 'AutoAllocator',
      showCount: true,
      infoTooltip: 'Autonomous portfolio optimization loop inspired by karpathy/autoresearch. The AI proposes allocation changes, backtests them, and keeps improvements.',
    });
  }

  public async fetchData(): Promise<boolean> {
    this.showLoading();
    try {
      this.state = getDemoState();
      this.setCount(this.state.totalExperiments);
      this.render();
      this.setDataBadge('live');
      return true;
    } catch (e) {
      this.showError('Failed to load allocator state', () => void this.fetchData());
      return false;
    }
  }

  private render(): void {
    if (!this.state) return;
    const s = this.state;
    const keepRate = s.totalExperiments > 0 ? ((s.keptCount / s.totalExperiments) * 100).toFixed(0) : '0';
    const improvement = s.benchmarkSharpe > 0 ? (((s.bestSharpe - s.benchmarkSharpe) / s.benchmarkSharpe) * 100).toFixed(0) : 'N/A';

    const experimentRows = s.experiments.slice(0, 8).map(e => `
      <div style="padding:6px 0;border-bottom:1px solid rgba(255,255,255,0.04)">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:2px">
          <div style="display:flex;align-items:center;gap:6px">
            <span style="font-size:10px;color:var(--text-muted)">#${e.id}</span>
            ${statusBadge(e.status)}
          </div>
          <span style="font-size:11px;font-weight:600;color:var(--text)">${e.status === 'CRASH' ? '—' : e.sharpe.toFixed(2)}</span>
        </div>
        <div style="font-size:10px;color:var(--text-dim);line-height:1.3">${escapeHtml(e.description)}</div>
      </div>
    `).join('');

    const html = `
      <div style="padding:12px 14px">
        <!-- Status indicator -->
        <div style="display:flex;align-items:center;gap:6px;margin-bottom:10px">
          <div style="width:8px;height:8px;border-radius:50%;background:${s.isRunning ? '#2ecc71' : '#95a5a6'};${s.isRunning ? 'animation:pulse 2s infinite' : ''}"></div>
          <span style="font-size:11px;font-weight:600;color:${s.isRunning ? '#2ecc71' : '#95a5a6'}">${s.isRunning ? 'RUNNING' : 'STOPPED'} &middot; Iteration #${s.currentIteration}</span>
        </div>

        <!-- Key metrics -->
        <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px;margin-bottom:10px">
          <div style="padding:8px;background:rgba(255,255,255,0.03);border-radius:6px;text-align:center">
            <div style="font-size:10px;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.4px">Best Sharpe</div>
            <div style="font-size:18px;font-weight:700;color:#2ecc71">${s.bestSharpe.toFixed(2)}</div>
          </div>
          <div style="padding:8px;background:rgba(255,255,255,0.03);border-radius:6px;text-align:center">
            <div style="font-size:10px;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.4px">Benchmark</div>
            <div style="font-size:18px;font-weight:700;color:var(--text-dim)">${s.benchmarkSharpe.toFixed(2)}</div>
          </div>
          <div style="padding:8px;background:rgba(255,255,255,0.03);border-radius:6px;text-align:center">
            <div style="font-size:10px;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.4px">vs 60/40</div>
            <div style="font-size:18px;font-weight:700;color:#3498db">+${improvement}%</div>
          </div>
        </div>

        <!-- Progress bar -->
        ${renderProgressBar(s.keptCount, s.discardedCount, s.crashCount, s.totalExperiments)}
        <div style="display:flex;justify-content:space-between;margin-top:4px;font-size:10px;color:var(--text-muted)">
          <span>${s.keptCount} kept (${keepRate}%)</span>
          <span>${s.discardedCount} discarded</span>
          <span>${s.crashCount} crashed</span>
        </div>

        <!-- Sharpe frontier chart -->
        ${renderSharpeFrontier(s.experiments)}

        <!-- Experiment log -->
        <div style="font-size:11px;font-weight:600;color:var(--text-dim);text-transform:uppercase;letter-spacing:0.5px;margin:8px 0 4px">Experiment Log</div>
        <div style="max-height:240px;overflow-y:auto">
          ${experimentRows}
        </div>
      </div>
      <style>
        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.4; } }
      </style>`;

    this.setContent(html);
  }
}
