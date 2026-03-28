import { Panel } from './Panel';
import { escapeHtml } from '@/utils/sanitize';

interface Position {
  ticker: string;
  name: string;
  weight: number;
  value: number;
  price: number;
  shares: number;
  assetClass: string;
  color: string;
  dailyChange: number;
  changePct: number;
}

interface PortfolioState {
  totalValue: number;
  dataSource: string;
  positions: Position[];
  riskScore: number;
  lastRebalance: string;
}

const ASSET_CLASS_COLORS: Record<string, string> = {
  'Equity': '#3498db',
  'Managed Futures': '#9b59b6',
  'Structured Credit': '#1abc9c',
  'Private Credit': '#e67e22',
  'Real Assets': '#f1c40f',
  'Fixed Income': '#95a5a6',
};

function defaultPositions(): Position[] {
  return [
    { ticker: 'SPY',  name: 'S&P 500 ETF',           weight: 0.20, value: 2000, price: 0, shares: 0, assetClass: 'Equity',           color: '#3498db', dailyChange: 0, changePct: 0 },
    { ticker: 'VTI',  name: 'Total Stock Market',     weight: 0.10, value: 1000, price: 0, shares: 0, assetClass: 'Equity',           color: '#2980b9', dailyChange: 0, changePct: 0 },
    { ticker: 'DBMF', name: 'Managed Futures',        weight: 0.10, value: 1000, price: 0, shares: 0, assetClass: 'Managed Futures',  color: '#9b59b6', dailyChange: 0, changePct: 0 },
    { ticker: 'KMLM', name: 'Mount Lucas Futures',    weight: 0.05, value: 500,  price: 0, shares: 0, assetClass: 'Managed Futures',  color: '#8e44ad', dailyChange: 0, changePct: 0 },
    { ticker: 'RPAR', name: 'Risk Parity',            weight: 0.05, value: 500,  price: 0, shares: 0, assetClass: 'Managed Futures',  color: '#7d3c98', dailyChange: 0, changePct: 0 },
    { ticker: 'JAAA', name: 'AAA CLO ETF',            weight: 0.10, value: 1000, price: 0, shares: 0, assetClass: 'Structured Credit',color: '#1abc9c', dailyChange: 0, changePct: 0 },
    { ticker: 'CLOA', name: 'iShares AAA CLO',        weight: 0.05, value: 500,  price: 0, shares: 0, assetClass: 'Structured Credit',color: '#16a085', dailyChange: 0, changePct: 0 },
    { ticker: 'ARCC', name: 'Ares Capital',           weight: 0.08, value: 800,  price: 0, shares: 0, assetClass: 'Private Credit',   color: '#e67e22', dailyChange: 0, changePct: 0 },
    { ticker: 'BXSL', name: 'Blackstone Lending',     weight: 0.07, value: 700,  price: 0, shares: 0, assetClass: 'Private Credit',   color: '#d35400', dailyChange: 0, changePct: 0 },
    { ticker: 'GLDM', name: 'Gold MiniShares',        weight: 0.05, value: 500,  price: 0, shares: 0, assetClass: 'Real Assets',      color: '#f1c40f', dailyChange: 0, changePct: 0 },
    { ticker: 'PDBC', name: 'Diversified Commodity',  weight: 0.05, value: 500,  price: 0, shares: 0, assetClass: 'Real Assets',      color: '#f39c12', dailyChange: 0, changePct: 0 },
    { ticker: 'AGG',  name: 'US Aggregate Bond',      weight: 0.05, value: 500,  price: 0, shares: 0, assetClass: 'Fixed Income',     color: '#95a5a6', dailyChange: 0, changePct: 0 },
    { ticker: 'SRLN', name: 'Senior Loan ETF',        weight: 0.05, value: 500,  price: 0, shares: 0, assetClass: 'Fixed Income',     color: '#7f8c8d', dailyChange: 0, changePct: 0 },
  ];
}

function chgColor(v: number): string { return v >= 0 ? '#2ecc71' : '#e74c3c'; }
function chgSign(v: number): string { return v >= 0 ? '+' : ''; }

function donutSVG(positions: Position[], size: number): string {
  const cx = size / 2, cy = size / 2, R = size / 2 - 4, r = R * 0.58;
  let cum = -90;
  const segs: string[] = [];
  for (const p of positions) {
    const a = p.weight * 360;
    if (a < 0.5) { cum += a; continue; }
    const s = (cum * Math.PI) / 180, e = ((cum + a) * Math.PI) / 180;
    const la = a > 180 ? 1 : 0;
    segs.push(`<path d="M${(cx+R*Math.cos(s)).toFixed(1)},${(cy+R*Math.sin(s)).toFixed(1)} A${R},${R} 0 ${la},1 ${(cx+R*Math.cos(e)).toFixed(1)},${(cy+R*Math.sin(e)).toFixed(1)} L${(cx+r*Math.cos(e)).toFixed(1)},${(cy+r*Math.sin(e)).toFixed(1)} A${r},${r} 0 ${la},0 ${(cx+r*Math.cos(s)).toFixed(1)},${(cy+r*Math.sin(s)).toFixed(1)} Z" fill="${p.color}" opacity="0.9"><title>${p.ticker} ${(p.weight*100).toFixed(1)}%</title></path>`);
    cum += a;
  }
  return `<svg viewBox="0 0 ${size} ${size}" width="${size}" height="${size}">${segs.join('')}</svg>`;
}

export class PortfolioPanel extends Panel {
  private state: PortfolioState;

  constructor() {
    super({
      id: 'portfolio',
      title: 'Portfolio',
      showCount: false,
      className: 'panel-wide',
      infoTooltip: 'AI-optimized portfolio with alternative investments. Drag sliders to adjust allocation weights. Totals auto-normalize to 100%.',
    });
    this.state = {
      totalValue: 10000,
      dataSource: 'demo',
      positions: defaultPositions(),
      riskScore: 0.42,
      lastRebalance: '2026-03-25',
    };
  }

  public async fetchData(): Promise<boolean> {
    this.showLoading('Fetching live prices...');
    let isLive = false;
    try {
      const resp = await fetch('http://localhost:8000/api/portfolio');
      if (resp.ok) {
        const data = await resp.json();
        if (data.positions?.length > 0) {
          this.state.totalValue = data.totalValue;
          this.state.lastRebalance = data.lastRebalance;
          this.state.dataSource = data.dataSource || 'demo';
          this.state.positions = data.positions.map((p: any) => ({
            ticker: p.ticker,
            name: p.name,
            weight: p.weight,
            value: p.value,
            price: p.price || 0,
            shares: p.shares || 0,
            assetClass: p.assetClass,
            color: p.color,
            dailyChange: p.dailyChange,
            changePct: p.changePct || 0,
          }));
          isLive = true;
          console.log('[Portfolio] Live data loaded:', data.positions.length, 'positions');
        }
      }
    } catch (e) {
      console.warn('[Portfolio] API unavailable, using demo data:', e);
    }
    this.render();
    this.setDataBadge(isLive ? 'live' : 'cached');
    return true;
  }

  private recalcValues(): void {
    const total = this.state.positions.reduce((s, p) => s + p.weight, 0);
    if (total > 0) {
      for (const p of this.state.positions) {
        p.weight = p.weight / total;
        p.value = Math.round(this.state.totalValue * p.weight);
      }
    }
  }

  private handleSlider(ticker: string, newPct: number): void {
    const pos = this.state.positions.find(p => p.ticker === ticker);
    if (!pos) return;
    pos.weight = newPct / 100;
    this.recalcValues();
    this.render();
  }

  private render(): void {
    const d = this.state;
    const dailyTotal = d.positions.reduce((s, p) => s + p.dailyChange, 0);
    // Weighted average daily change %
    const dailyPct = d.positions.reduce((s, p) => s + p.changePct * p.weight, 0);

    // Group by asset class
    const classMap = new Map<string, { color: string; weight: number; value: number }>();
    for (const p of d.positions) {
      const ex = classMap.get(p.assetClass);
      if (ex) { ex.weight += p.weight; ex.value += p.value; }
      else classMap.set(p.assetClass, { color: ASSET_CLASS_COLORS[p.assetClass] || p.color, weight: p.weight, value: p.value });
    }

    const legend = Array.from(classMap.entries()).map(([cls, info]) => `
      <div style="display:flex;align-items:center;justify-content:space-between;padding:2px 0">
        <div style="display:flex;align-items:center;gap:6px">
          <div style="width:8px;height:8px;border-radius:50%;background:${info.color};flex-shrink:0"></div>
          <span style="font-size:11px;color:var(--text-dim)">${escapeHtml(cls)}</span>
        </div>
        <span style="font-size:11px;color:var(--text);font-weight:500">${(info.weight * 100).toFixed(0)}% &middot; $${info.value.toLocaleString()}</span>
      </div>`).join('');

    const posRows = d.positions.map(p => `
      <div class="nf-pos-row" style="display:flex;align-items:center;gap:8px;padding:5px 0;border-bottom:1px solid rgba(255,255,255,0.04)">
        <div style="width:6px;height:6px;border-radius:50%;background:${p.color};flex-shrink:0"></div>
        <div style="min-width:70px">
          <div style="font-size:12px;font-weight:600;color:var(--text)">${escapeHtml(p.ticker)}</div>
          <div style="font-size:9px;color:var(--text-muted)">${p.price > 0 ? `$${p.price.toFixed(2)}` : escapeHtml(p.name)}</div>
        </div>
        <input type="range" min="1" max="40" step="1" value="${Math.round(p.weight * 100)}"
          data-ticker="${p.ticker}"
          style="flex:1;height:4px;accent-color:${p.color};cursor:pointer" />
        <div style="text-align:right;min-width:80px">
          <div style="font-size:11px;font-weight:600;color:var(--text)">${(p.weight * 100).toFixed(0)}% &middot; $${p.value.toLocaleString()}</div>
          <div style="font-size:10px;color:${chgColor(p.changePct)}">
            ${chgSign(p.changePct)}${Math.abs(p.changePct).toFixed(2)}%${p.shares > 0 ? ` &middot; ${p.shares.toFixed(1)} shr` : ''}
          </div>
        </div>
      </div>`).join('');

    const riskLabel = d.riskScore < 0.3 ? 'Low' : d.riskScore < 0.6 ? 'Moderate' : 'High';
    const riskColor = d.riskScore < 0.3 ? '#2ecc71' : d.riskScore < 0.6 ? '#f1c40f' : '#e74c3c';

    const el = document.createElement('div');
    el.style.cssText = 'padding:12px 14px';
    el.innerHTML = `
      <div style="display:flex;align-items:flex-start;gap:16px;margin-bottom:10px">
        <div style="flex-shrink:0">${donutSVG(d.positions, 130)}</div>
        <div style="flex:1;min-width:0">
          <div style="font-size:26px;font-weight:700;color:var(--text);letter-spacing:-0.5px">$${d.totalValue.toLocaleString()}</div>
          <div style="font-size:12px;color:${chgColor(dailyTotal)};font-weight:500;margin-bottom:8px">${chgSign(dailyTotal)}$${Math.abs(dailyTotal).toFixed(2)} (${chgSign(dailyPct)}${Math.abs(dailyPct).toFixed(2)}%) today</div>
          ${legend}
        </div>
      </div>
      <div style="display:flex;justify-content:space-between;margin-bottom:8px;padding:5px 8px;background:rgba(255,255,255,0.03);border-radius:5px">
        <div><div style="font-size:9px;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.4px">Risk</div><div style="font-size:12px;font-weight:600;color:${riskColor}">${riskLabel}</div></div>
        <div style="text-align:center"><div style="font-size:9px;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.4px">Positions</div><div style="font-size:12px;font-weight:600;color:var(--text)">${d.positions.length}</div></div>
        <div style="text-align:right"><div style="font-size:9px;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.4px">Rebalanced</div><div style="font-size:12px;color:var(--text)">${escapeHtml(d.lastRebalance)}</div></div>
      </div>
      <div style="font-size:10px;font-weight:600;color:var(--text-dim);text-transform:uppercase;letter-spacing:0.5px;margin-bottom:2px">Allocations — drag to adjust</div>
      <div style="max-height:300px;overflow-y:auto" id="nf-pos-list">${posRows}</div>
      <div style="margin-top:8px;padding:5px;text-align:center;background:rgba(52,152,219,0.08);border:1px solid rgba(52,152,219,0.15);border-radius:4px">
        <span style="font-size:10px;color:#3498db;font-weight:500">${d.dataSource === 'demo' ? 'DEMO DATA' : 'LIVE'} &middot; $10K invested &middot; ${d.dataSource !== 'demo' ? 'Yahoo Finance' : 'API offline'}</span>
      </div>`;

    // Wire up sliders
    el.querySelectorAll('input[type="range"]').forEach(slider => {
      slider.addEventListener('input', (e) => {
        const t = e.target as HTMLInputElement;
        this.handleSlider(t.dataset.ticker!, parseInt(t.value, 10));
      });
    });

    this.element.querySelector('.panel-content')!.replaceChildren(el);
  }
}
