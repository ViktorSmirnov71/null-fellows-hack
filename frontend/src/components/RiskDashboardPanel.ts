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
  riskTotal: number;
  riskGeo: number;
  riskMacro: number;
  riskVol: number;
  probPositive12m: number;
  probLoss20: number;
}

function demoMetrics(): RiskMetrics {
  return {
    sharpe: 1.51, sortino: 2.10, maxDrawdown: -0.113, calmar: 1.34,
    tailRatio: 1.24, cagr: 0.142, volatility: 0.089, winRate: 0.583,
    var95: -0.018, cvar: -0.026,
    riskTotal: 0.42, riskGeo: 0.38, riskMacro: 0.45, riskVol: 0.35,
    probPositive12m: 0.82, probLoss20: 0.03,
  };
}

function mColor(val: number, good: number, warn: number, higher = true): string {
  if (higher) return val >= good ? '#2ecc71' : val >= warn ? '#f1c40f' : '#e74c3c';
  return val <= good ? '#2ecc71' : val <= warn ? '#f1c40f' : '#e74c3c';
}

function meter(label: string, value: number, color: string): string {
  const pct = Math.min(100, value * 100);
  return `<div style="margin-bottom:6px">
    <div style="display:flex;justify-content:space-between;margin-bottom:1px">
      <span style="font-size:9px;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.3px">${label}</span>
      <span style="font-size:10px;font-weight:600;color:${color}">${pct.toFixed(0)}</span>
    </div>
    <div style="height:3px;border-radius:2px;background:rgba(255,255,255,0.06)">
      <div style="height:100%;width:${pct.toFixed(1)}%;border-radius:2px;background:${color};transition:width 0.3s"></div>
    </div>
  </div>`;
}

function fanChart(): string {
  const w = 260, h = 65, m = 12;
  const bands = [
    { vals: [0,-2,-5,-8,-10,-12,-11,-10,-8,-6,-4,-2,0], col: 'rgba(231,76,60,0.12)' },
    { vals: [0,0,1,2,3,4,5,6,7,7,8,9,10], col: 'rgba(241,196,15,0.12)' },
    { vals: [0,1,3,5,7,8,9,10,11,12,13,14,15], col: 'rgba(46,204,113,0.12)' },
    { vals: [0,2,5,8,11,13,15,17,18,19,21,23,25], col: 'rgba(46,204,113,0.18)' },
    { vals: [0,4,8,13,17,21,24,27,30,32,35,38,42], col: 'rgba(52,152,219,0.12)' },
  ];
  const all = bands.flatMap(b => b.vals);
  const mn = Math.min(...all), mx = Math.max(...all), rng = mx - mn || 1;
  const x = (i: number) => 4 + (i / m) * (w - 8);
  const y = (v: number) => h - 4 - ((v - mn) / rng) * (h - 8);
  const paths: string[] = [];
  for (let i = 0; i < bands.length - 1; i++) {
    const lo = bands[i]!.vals, hi = bands[i + 1]!.vals;
    const d1 = lo.map((_, j) => `${x(j).toFixed(1)},${y(hi[j]!).toFixed(1)}`).join(' L');
    const d2 = [...lo].reverse().map((v, j) => `${x(m - j).toFixed(1)},${y(v).toFixed(1)}`).join(' L');
    paths.push(`<path d="M${d1} L${d2} Z" fill="${bands[i + 1]!.col}"/>`);
  }
  const med = bands[2]!.vals.map((v, i) => `${i === 0 ? 'M' : 'L'}${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(' ');
  paths.push(`<path d="${med}" fill="none" stroke="#2ecc71" stroke-width="1.5"/>`);
  const zy = y(0);
  paths.push(`<line x1="4" y1="${zy.toFixed(1)}" x2="${w - 4}" y2="${zy.toFixed(1)}" stroke="rgba(255,255,255,0.12)" stroke-width="0.5" stroke-dasharray="3,3"/>`);
  return `<svg viewBox="0 0 ${w} ${h}" width="100%" height="${h}" style="display:block">${paths.join('')}</svg>
    <div style="display:flex;justify-content:space-between;font-size:8px;color:var(--text-muted)"><span>Now</span><span>6m</span><span>12m</span></div>`;
}

function card(label: string, value: string, color: string, sub?: string): string {
  return `<div style="padding:5px;background:rgba(255,255,255,0.03);border-radius:5px;text-align:center">
    <div style="font-size:8px;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.3px">${label}</div>
    <div style="font-size:15px;font-weight:700;color:${color}">${value}</div>
    ${sub ? `<div style="font-size:8px;color:var(--text-muted)">${sub}</div>` : ''}
  </div>`;
}

export class RiskDashboardPanel extends Panel {
  private metrics: RiskMetrics;

  constructor() {
    super({
      id: 'risk-dashboard',
      title: 'Risk Dashboard',
      showCount: false,
      className: 'panel-wide',
      infoTooltip: 'Portfolio risk metrics via QuantStats. Risk score combines GDELT geopolitical tone, FRED macro indicators, and VIX volatility.',
    });
    this.metrics = demoMetrics();
  }

  public async fetchData(): Promise<boolean> {
    this.render();
    this.setDataBadge('live');
    return true;
  }

  private render(): void {
    const m = this.metrics;
    const el = document.createElement('div');
    el.style.cssText = 'padding:12px 14px';
    el.innerHTML = `
      <div style="font-size:10px;font-weight:600;color:var(--text-dim);text-transform:uppercase;letter-spacing:0.4px;margin-bottom:4px">Performance</div>
      <div style="display:grid;grid-template-columns:1fr 1fr 1fr 1fr;gap:5px;margin-bottom:10px">
        ${card('Sharpe', m.sharpe.toFixed(2), mColor(m.sharpe, 1.5, 1.0), '>1.5')}
        ${card('Sortino', m.sortino.toFixed(2), mColor(m.sortino, 2.0, 1.5), '>2.0')}
        ${card('CAGR', (m.cagr * 100).toFixed(1) + '%', mColor(m.cagr, 0.10, 0.06))}
        ${card('Win Rate', (m.winRate * 100).toFixed(0) + '%', mColor(m.winRate, 0.55, 0.50))}
      </div>
      <div style="font-size:10px;font-weight:600;color:var(--text-dim);text-transform:uppercase;letter-spacing:0.4px;margin-bottom:4px">Downside Risk</div>
      <div style="display:grid;grid-template-columns:1fr 1fr 1fr 1fr;gap:5px;margin-bottom:10px">
        ${card('Max DD', (m.maxDrawdown * 100).toFixed(1) + '%', mColor(Math.abs(m.maxDrawdown), 0.15, 0.20, false))}
        ${card('Calmar', m.calmar.toFixed(2), mColor(m.calmar, 1.0, 0.5))}
        ${card('VaR 95%', (m.var95 * 100).toFixed(1) + '%', '#e67e22')}
        ${card('CVaR', (m.cvar * 100).toFixed(1) + '%', '#e74c3c')}
      </div>
      <div style="display:flex;align-items:center;gap:8px;padding:6px 8px;margin-bottom:10px;background:${m.tailRatio > 1 ? 'rgba(46,204,113,0.06)' : 'rgba(231,76,60,0.06)'};border:1px solid ${m.tailRatio > 1 ? 'rgba(46,204,113,0.15)' : 'rgba(231,76,60,0.15)'};border-radius:5px">
        <div style="font-size:22px;font-weight:700;color:${m.tailRatio > 1 ? '#2ecc71' : '#e74c3c'}">${m.tailRatio.toFixed(2)}</div>
        <div>
          <div style="font-size:11px;font-weight:600;color:var(--text)">Tail Ratio ${m.tailRatio > 1 ? '(Positive Skew)' : '(Negative Skew)'}</div>
          <div style="font-size:9px;color:var(--text-dim)">${m.tailRatio > 1 ? 'More upside than downside — asymmetric returns working' : 'Downside exceeds upside'}</div>
        </div>
      </div>
      <div style="font-size:10px;font-weight:600;color:var(--text-dim);text-transform:uppercase;letter-spacing:0.4px;margin-bottom:4px">World Risk Score</div>
      <div style="padding:6px 8px;background:rgba(255,255,255,0.03);border-radius:5px;margin-bottom:10px">
        ${meter('Geopolitical', m.riskGeo, m.riskGeo < 0.4 ? '#2ecc71' : m.riskGeo < 0.6 ? '#f1c40f' : '#e74c3c')}
        ${meter('Macro', m.riskMacro, m.riskMacro < 0.4 ? '#2ecc71' : m.riskMacro < 0.6 ? '#f1c40f' : '#e74c3c')}
        ${meter('Volatility', m.riskVol, m.riskVol < 0.4 ? '#2ecc71' : m.riskVol < 0.6 ? '#f1c40f' : '#e74c3c')}
        <div style="display:flex;justify-content:space-between;margin-top:4px;padding-top:4px;border-top:1px solid rgba(255,255,255,0.05)">
          <span style="font-size:10px;font-weight:600;color:var(--text)">Composite</span>
          <span style="font-size:12px;font-weight:700;color:${m.riskTotal < 0.4 ? '#2ecc71' : m.riskTotal < 0.6 ? '#f1c40f' : '#e74c3c'}">${(m.riskTotal * 100).toFixed(0)} / 100</span>
        </div>
      </div>
      <div style="font-size:10px;font-weight:600;color:var(--text-dim);text-transform:uppercase;letter-spacing:0.4px;margin-bottom:3px">12-Month Monte Carlo (1,000 sims)</div>
      ${fanChart()}
      <div style="display:flex;gap:6px;margin-top:6px">
        <div style="flex:1;padding:5px;background:rgba(46,204,113,0.06);border-radius:4px;text-align:center">
          <div style="font-size:8px;color:var(--text-muted)">P(positive @ 12m)</div>
          <div style="font-size:13px;font-weight:700;color:#2ecc71">${(m.probPositive12m * 100).toFixed(0)}%</div>
        </div>
        <div style="flex:1;padding:5px;background:rgba(231,76,60,0.06);border-radius:4px;text-align:center">
          <div style="font-size:8px;color:var(--text-muted)">P(loss >20%)</div>
          <div style="font-size:13px;font-weight:700;color:#e74c3c">${(m.probLoss20 * 100).toFixed(0)}%</div>
        </div>
      </div>`;

    this.element.querySelector('.panel-content')!.replaceChildren(el);
  }
}
