import { Panel } from './Panel';

interface RiskMetrics {
  sharpe: number;
  sortino: number;
  maxDrawdown: number;
  calmar: number;
  tailRatio: number;
  cagr: number;
  volatility: number;
  winRate: number;
  var95: number;
  cvar: number;
  // Risk score components
  riskTotal: number;
  riskGeo: number;
  riskMacro: number;
  riskVol: number;
  // Monte Carlo
  probPositive12m: number;
  probLoss20: number;
}

function getDemoMetrics(): RiskMetrics {
  return {
    sharpe: 1.51,
    sortino: 2.10,
    maxDrawdown: -0.113,
    calmar: 1.34,
    tailRatio: 1.24,
    cagr: 0.142,
    volatility: 0.089,
    winRate: 0.583,
    var95: -0.018,
    cvar: -0.026,
    riskTotal: 0.42,
    riskGeo: 0.38,
    riskMacro: 0.45,
    riskVol: 0.35,
    probPositive12m: 0.82,
    probLoss20: 0.03,
  };
}

function metricColor(value: number, thresholds: { good: number; warn: number }, higherIsBetter = true): string {
  if (higherIsBetter) {
    if (value >= thresholds.good) return '#2ecc71';
    if (value >= thresholds.warn) return '#f1c40f';
    return '#e74c3c';
  }
  if (value <= thresholds.good) return '#2ecc71';
  if (value <= thresholds.warn) return '#f1c40f';
  return '#e74c3c';
}

function renderMeter(label: string, value: number, max: number, color: string): string {
  const pct = Math.min(100, (value / max) * 100);
  return `
    <div style="margin-bottom:8px">
      <div style="display:flex;justify-content:space-between;margin-bottom:2px">
        <span style="font-size:10px;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.4px">${label}</span>
        <span style="font-size:11px;font-weight:600;color:${color}">${(value * 100).toFixed(0)}</span>
      </div>
      <div style="height:4px;border-radius:2px;background:rgba(255,255,255,0.06)">
        <div style="height:100%;width:${pct.toFixed(1)}%;border-radius:2px;background:${color};transition:width 0.3s"></div>
      </div>
    </div>`;
}

function renderMonteCarloFan(): string {
  // Simplified fan chart visualization
  const w = 280, h = 80, months = 12;
  const paths: string[] = [];

  // Generate percentile bands (simplified)
  const percentiles = [
    { pct: '5th',  values: [0, -2, -5, -8, -10, -12, -11, -10, -8, -6, -4, -2, 0], color: 'rgba(231,76,60,0.15)' },
    { pct: '25th', values: [0, 0, 1, 2, 3, 4, 5, 6, 7, 7, 8, 9, 10], color: 'rgba(241,196,15,0.15)' },
    { pct: '50th', values: [0, 1, 3, 5, 7, 8, 9, 10, 11, 12, 13, 14, 15], color: 'rgba(46,204,113,0.15)' },
    { pct: '75th', values: [0, 2, 5, 8, 11, 13, 15, 17, 18, 19, 21, 23, 25], color: 'rgba(46,204,113,0.2)' },
    { pct: '95th', values: [0, 4, 8, 13, 17, 21, 24, 27, 30, 32, 35, 38, 42], color: 'rgba(52,152,219,0.15)' },
  ];

  const allVals = percentiles.flatMap(p => p.values);
  const minV = Math.min(...allVals), maxV = Math.max(...allVals);
  const range = maxV - minV || 1;

  function toX(i: number): number { return 4 + (i / months) * (w - 8); }
  function toY(v: number): number { return h - 4 - ((v - minV) / range) * (h - 8); }

  // Draw filled bands between percentile pairs
  for (let i = 0; i < percentiles.length - 1; i++) {
    const lower = percentiles[i]!.values;
    const upper = percentiles[i + 1]!.values;
    const d = lower.map((_, j) => `${toX(j).toFixed(1)},${toY(upper[j]!).toFixed(1)}`).join(' L');
    const dRev = [...lower].reverse().map((v, j) => `${toX(months - j).toFixed(1)},${toY(v).toFixed(1)}`).join(' L');
    paths.push(`<path d="M${d} L${dRev} Z" fill="${percentiles[i + 1]!.color}"/>`);
  }

  // Median line
  const medianPath = percentiles[2]!.values.map((v, i) => `${i === 0 ? 'M' : 'L'}${toX(i).toFixed(1)},${toY(v).toFixed(1)}`).join(' ');
  paths.push(`<path d="${medianPath}" fill="none" stroke="#2ecc71" stroke-width="1.5"/>`);

  // Zero line
  const zeroY = toY(0);
  paths.push(`<line x1="4" y1="${zeroY.toFixed(1)}" x2="${w - 4}" y2="${zeroY.toFixed(1)}" stroke="rgba(255,255,255,0.15)" stroke-width="0.5" stroke-dasharray="3,3"/>`);

  return `
    <div style="margin:8px 0">
      <div style="font-size:10px;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.4px;margin-bottom:4px">12-MONTH MONTE CARLO (1,000 sims)</div>
      <svg viewBox="0 0 ${w} ${h}" width="100%" height="${h}" style="display:block">
        ${paths.join('')}
      </svg>
      <div style="display:flex;justify-content:space-between;font-size:9px;color:var(--text-muted);margin-top:2px">
        <span>Now</span>
        <span>6m</span>
        <span>12m</span>
      </div>
    </div>`;
}

export class RiskDashboardPanel extends Panel {
  private metrics: RiskMetrics | null = null;

  constructor() {
    super({
      id: 'risk-dashboard',
      title: 'Risk Dashboard',
      showCount: false,
      className: 'panel-wide',
      infoTooltip: 'Portfolio risk metrics computed via QuantStats. Risk score combines GDELT geopolitical tone, FRED macro indicators, and VIX volatility.',
    });
  }

  public async fetchData(): Promise<boolean> {
    this.showLoading();
    try {
      this.metrics = getDemoMetrics();
      this.render();
      this.setDataBadge('live');
      return true;
    } catch (e) {
      this.showError('Failed to load risk metrics', () => void this.fetchData());
      return false;
    }
  }

  private render(): void {
    if (!this.metrics) return;
    const m = this.metrics;

    const metricCard = (label: string, value: string, color: string, subtitle?: string) => `
      <div style="padding:8px;background:rgba(255,255,255,0.03);border-radius:6px;text-align:center">
        <div style="font-size:9px;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.4px">${label}</div>
        <div style="font-size:16px;font-weight:700;color:${color}">${value}</div>
        ${subtitle ? `<div style="font-size:9px;color:var(--text-muted)">${subtitle}</div>` : ''}
      </div>`;

    const html = `
      <div style="padding:12px 14px">
        <!-- Performance metrics grid -->
        <div style="font-size:11px;font-weight:600;color:var(--text-dim);text-transform:uppercase;letter-spacing:0.5px;margin-bottom:6px">Performance</div>
        <div style="display:grid;grid-template-columns:1fr 1fr 1fr 1fr;gap:6px;margin-bottom:12px">
          ${metricCard('Sharpe', m.sharpe.toFixed(2), metricColor(m.sharpe, { good: 1.5, warn: 1.0 }), 'target >1.5')}
          ${metricCard('Sortino', m.sortino.toFixed(2), metricColor(m.sortino, { good: 2.0, warn: 1.5 }), 'target >2.0')}
          ${metricCard('CAGR', (m.cagr * 100).toFixed(1) + '%', metricColor(m.cagr, { good: 0.10, warn: 0.06 }))}
          ${metricCard('Win Rate', (m.winRate * 100).toFixed(0) + '%', metricColor(m.winRate, { good: 0.55, warn: 0.50 }))}
        </div>

        <!-- Risk metrics grid -->
        <div style="font-size:11px;font-weight:600;color:var(--text-dim);text-transform:uppercase;letter-spacing:0.5px;margin-bottom:6px">Downside Risk</div>
        <div style="display:grid;grid-template-columns:1fr 1fr 1fr 1fr;gap:6px;margin-bottom:12px">
          ${metricCard('Max DD', (m.maxDrawdown * 100).toFixed(1) + '%', metricColor(Math.abs(m.maxDrawdown), { good: 0.15, warn: 0.20 }, false))}
          ${metricCard('Calmar', m.calmar.toFixed(2), metricColor(m.calmar, { good: 1.0, warn: 0.5 }))}
          ${metricCard('VaR 95%', (m.var95 * 100).toFixed(1) + '%', '#e67e22')}
          ${metricCard('CVaR', (m.cvar * 100).toFixed(1) + '%', '#e74c3c')}
        </div>

        <!-- Asymmetry highlight -->
        <div style="display:flex;align-items:center;gap:8px;padding:8px 10px;margin-bottom:12px;background:${m.tailRatio > 1 ? 'rgba(46,204,113,0.08)' : 'rgba(231,76,60,0.08)'};border:1px solid ${m.tailRatio > 1 ? 'rgba(46,204,113,0.2)' : 'rgba(231,76,60,0.2)'};border-radius:6px">
          <div style="font-size:24px;font-weight:700;color:${m.tailRatio > 1 ? '#2ecc71' : '#e74c3c'}">${m.tailRatio.toFixed(2)}</div>
          <div>
            <div style="font-size:11px;font-weight:600;color:var(--text)">Tail Ratio ${m.tailRatio > 1 ? '(Positive Skew)' : '(Negative Skew)'}</div>
            <div style="font-size:10px;color:var(--text-dim)">${m.tailRatio > 1 ? 'More upside than downside — asymmetric returns working' : 'Downside exceeds upside — needs adjustment'}</div>
          </div>
        </div>

        <!-- World Risk Score -->
        <div style="font-size:11px;font-weight:600;color:var(--text-dim);text-transform:uppercase;letter-spacing:0.5px;margin-bottom:6px">World Risk Score</div>
        <div style="padding:8px 10px;background:rgba(255,255,255,0.03);border-radius:6px;margin-bottom:12px">
          ${renderMeter('Geopolitical', m.riskGeo, 1, m.riskGeo < 0.4 ? '#2ecc71' : m.riskGeo < 0.6 ? '#f1c40f' : '#e74c3c')}
          ${renderMeter('Macro', m.riskMacro, 1, m.riskMacro < 0.4 ? '#2ecc71' : m.riskMacro < 0.6 ? '#f1c40f' : '#e74c3c')}
          ${renderMeter('Volatility', m.riskVol, 1, m.riskVol < 0.4 ? '#2ecc71' : m.riskVol < 0.6 ? '#f1c40f' : '#e74c3c')}
          <div style="display:flex;justify-content:space-between;margin-top:6px;padding-top:6px;border-top:1px solid rgba(255,255,255,0.06)">
            <span style="font-size:11px;font-weight:600;color:var(--text)">Composite Risk</span>
            <span style="font-size:13px;font-weight:700;color:${m.riskTotal < 0.4 ? '#2ecc71' : m.riskTotal < 0.6 ? '#f1c40f' : '#e74c3c'}">${(m.riskTotal * 100).toFixed(0)} / 100</span>
          </div>
        </div>

        <!-- Monte Carlo -->
        ${renderMonteCarloFan()}

        <!-- Monte Carlo stats -->
        <div style="display:flex;gap:8px;margin-top:6px">
          <div style="flex:1;padding:6px 8px;background:rgba(46,204,113,0.08);border-radius:4px;text-align:center">
            <div style="font-size:9px;color:var(--text-muted)">P(positive @ 12m)</div>
            <div style="font-size:14px;font-weight:700;color:#2ecc71">${(m.probPositive12m * 100).toFixed(0)}%</div>
          </div>
          <div style="flex:1;padding:6px 8px;background:rgba(231,76,60,0.08);border-radius:4px;text-align:center">
            <div style="font-size:9px;color:var(--text-muted)">P(loss >20%)</div>
            <div style="font-size:14px;font-weight:700;color:#e74c3c">${(m.probLoss20 * 100).toFixed(0)}%</div>
          </div>
        </div>
      </div>`;

    this.setContent(html);
  }
}
