import { Panel } from './Panel';
import { escapeHtml } from '@/utils/sanitize';

/** Demo portfolio data — in production this comes from Supabase + the AutoAllocator */
interface Position {
  ticker: string;
  name: string;
  weight: number;
  value: number;
  assetClass: string;
  color: string;
  dailyChange: number;
}

interface PortfolioData {
  totalValue: number;
  dailyChange: number;
  dailyChangePct: number;
  positions: Position[];
  riskScore: number;
  lastRebalance: string;
}

function getDemoPortfolio(): PortfolioData {
  const positions: Position[] = [
    { ticker: 'SPY',  name: 'S&P 500 ETF',             weight: 0.20, value: 2000, assetClass: 'Equity',           color: '#3498db', dailyChange: 12.40 },
    { ticker: 'VTI',  name: 'Total Stock Market',       weight: 0.10, value: 1000, assetClass: 'Equity',           color: '#2980b9', dailyChange: 5.80 },
    { ticker: 'DBMF', name: 'Managed Futures',          weight: 0.10, value: 1000, assetClass: 'Managed Futures',  color: '#9b59b6', dailyChange: -3.20 },
    { ticker: 'KMLM', name: 'Mount Lucas Futures',      weight: 0.05, value: 500,  assetClass: 'Managed Futures',  color: '#8e44ad', dailyChange: 1.10 },
    { ticker: 'RPAR', name: 'Risk Parity',              weight: 0.05, value: 500,  assetClass: 'Managed Futures',  color: '#7d3c98', dailyChange: -0.50 },
    { ticker: 'JAAA', name: 'AAA CLO ETF',              weight: 0.10, value: 1000, assetClass: 'Structured Credit',color: '#1abc9c', dailyChange: 0.80 },
    { ticker: 'CLOA', name: 'iShares AAA CLO',          weight: 0.05, value: 500,  assetClass: 'Structured Credit',color: '#16a085', dailyChange: 0.40 },
    { ticker: 'ARCC', name: 'Ares Capital',             weight: 0.08, value: 800,  assetClass: 'Private Credit',   color: '#e67e22', dailyChange: 2.30 },
    { ticker: 'BXSL', name: 'Blackstone Lending',       weight: 0.07, value: 700,  assetClass: 'Private Credit',   color: '#d35400', dailyChange: 1.90 },
    { ticker: 'GLDM', name: 'Gold MiniShares',          weight: 0.05, value: 500,  assetClass: 'Real Assets',      color: '#f1c40f', dailyChange: 4.20 },
    { ticker: 'PDBC', name: 'Diversified Commodity',    weight: 0.05, value: 500,  assetClass: 'Real Assets',      color: '#f39c12', dailyChange: -1.80 },
    { ticker: 'AGG',  name: 'US Aggregate Bond',        weight: 0.05, value: 500,  assetClass: 'Fixed Income',     color: '#95a5a6', dailyChange: 0.30 },
    { ticker: 'SRLN', name: 'Senior Loan ETF',          weight: 0.05, value: 500,  assetClass: 'Fixed Income',     color: '#7f8c8d', dailyChange: 0.60 },
  ];
  const totalChange = positions.reduce((s, p) => s + p.dailyChange, 0);
  return {
    totalValue: 10000,
    dailyChange: totalChange,
    dailyChangePct: (totalChange / 10000) * 100,
    positions,
    riskScore: 0.42,
    lastRebalance: '2026-03-25',
  };
}

function changeColor(v: number): string {
  return v >= 0 ? '#2ecc71' : '#e74c3c';
}

function changeSign(v: number): string {
  return v >= 0 ? '+' : '';
}

function renderDonut(positions: Position[], size: number): string {
  const cx = size / 2, cy = size / 2, R = size / 2 - 4, r = R * 0.6;
  let cumAngle = -90;
  const paths: string[] = [];

  for (const pos of positions) {
    const angle = pos.weight * 360;
    const startRad = (cumAngle * Math.PI) / 180;
    const endRad = ((cumAngle + angle) * Math.PI) / 180;
    const largeArc = angle > 180 ? 1 : 0;

    const x1o = cx + R * Math.cos(startRad), y1o = cy + R * Math.sin(startRad);
    const x2o = cx + R * Math.cos(endRad),   y2o = cy + R * Math.sin(endRad);
    const x1i = cx + r * Math.cos(endRad),   y1i = cy + r * Math.sin(endRad);
    const x2i = cx + r * Math.cos(startRad), y2i = cy + r * Math.sin(startRad);

    paths.push(
      `<path d="M${x1o.toFixed(1)},${y1o.toFixed(1)} A${R},${R} 0 ${largeArc},1 ${x2o.toFixed(1)},${y2o.toFixed(1)} L${x1i.toFixed(1)},${y1i.toFixed(1)} A${r},${r} 0 ${largeArc},0 ${x2i.toFixed(1)},${y2i.toFixed(1)} Z" fill="${pos.color}" opacity="0.9"/>`
    );
    cumAngle += angle;
  }

  return `<svg viewBox="0 0 ${size} ${size}" width="${size}" height="${size}" style="display:block;margin:0 auto">${paths.join('')}</svg>`;
}

export class PortfolioPanel extends Panel {
  private data: PortfolioData | null = null;

  constructor() {
    super({
      id: 'portfolio',
      title: 'Portfolio',
      showCount: false,
      className: 'panel-wide',
      infoTooltip: 'AI-optimized portfolio with alternative investments. Allocations are dynamically adjusted based on world events and sentiment signals.',
    });
  }

  public async fetchData(): Promise<boolean> {
    this.showLoading();
    try {
      // In production: fetch from Supabase / AI engine API
      this.data = getDemoPortfolio();
      this.render();
      this.setDataBadge('live');
      return true;
    } catch (e) {
      this.showError('Failed to load portfolio', () => void this.fetchData());
      return false;
    }
  }

  private render(): void {
    if (!this.data) return;
    const d = this.data;
    const chg = changeColor(d.dailyChange);
    const sign = changeSign(d.dailyChange);

    // Group by asset class for the legend
    const classMap = new Map<string, { color: string; weight: number; value: number }>();
    for (const p of d.positions) {
      const existing = classMap.get(p.assetClass);
      if (existing) {
        existing.weight += p.weight;
        existing.value += p.value;
      } else {
        classMap.set(p.assetClass, { color: p.color, weight: p.weight, value: p.value });
      }
    }

    const legend = Array.from(classMap.entries()).map(([cls, info]) => `
      <div style="display:flex;align-items:center;justify-content:space-between;padding:3px 0">
        <div style="display:flex;align-items:center;gap:6px">
          <div style="width:8px;height:8px;border-radius:50%;background:${info.color}"></div>
          <span style="font-size:11px;color:var(--text-dim)">${escapeHtml(cls)}</span>
        </div>
        <span style="font-size:11px;color:var(--text)">${(info.weight * 100).toFixed(0)}% &middot; $${info.value.toLocaleString()}</span>
      </div>
    `).join('');

    const positionRows = d.positions.map(p => `
      <div style="display:flex;align-items:center;justify-content:space-between;padding:6px 0;border-bottom:1px solid rgba(255,255,255,0.04)">
        <div style="display:flex;align-items:center;gap:8px">
          <div style="width:6px;height:6px;border-radius:50%;background:${p.color}"></div>
          <div>
            <div style="font-size:12px;font-weight:600;color:var(--text)">${escapeHtml(p.ticker)}</div>
            <div style="font-size:10px;color:var(--text-muted)">${escapeHtml(p.name)}</div>
          </div>
        </div>
        <div style="text-align:right">
          <div style="font-size:12px;color:var(--text)">$${p.value.toLocaleString()}</div>
          <div style="font-size:10px;color:${changeColor(p.dailyChange)}">${changeSign(p.dailyChange)}$${Math.abs(p.dailyChange).toFixed(2)}</div>
        </div>
      </div>
    `).join('');

    const riskLabel = d.riskScore < 0.3 ? 'Low' : d.riskScore < 0.6 ? 'Moderate' : 'High';
    const riskColor = d.riskScore < 0.3 ? '#2ecc71' : d.riskScore < 0.6 ? '#f1c40f' : '#e74c3c';

    const html = `
      <div style="padding:12px 14px">
        <!-- Header: total value + daily change -->
        <div style="text-align:center;margin-bottom:12px">
          <div style="font-size:28px;font-weight:700;color:var(--text);letter-spacing:-0.5px">$${d.totalValue.toLocaleString()}</div>
          <div style="font-size:13px;color:${chg};font-weight:500">${sign}$${Math.abs(d.dailyChange).toFixed(2)} (${sign}${Math.abs(d.dailyChangePct).toFixed(2)}%) today</div>
        </div>

        <!-- Donut chart -->
        ${renderDonut(d.positions, 140)}

        <!-- Asset class legend -->
        <div style="margin:12px 0;padding:8px 10px;background:rgba(255,255,255,0.03);border-radius:6px">
          ${legend}
        </div>

        <!-- Risk + rebalance info -->
        <div style="display:flex;justify-content:space-between;margin-bottom:10px;padding:6px 10px;background:rgba(255,255,255,0.03);border-radius:6px">
          <div>
            <div style="font-size:10px;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.5px">Risk Level</div>
            <div style="font-size:13px;font-weight:600;color:${riskColor}">${riskLabel} (${(d.riskScore * 100).toFixed(0)})</div>
          </div>
          <div style="text-align:right">
            <div style="font-size:10px;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.5px">Last Rebalance</div>
            <div style="font-size:13px;color:var(--text)">${escapeHtml(d.lastRebalance)}</div>
          </div>
        </div>

        <!-- Positions list -->
        <div style="font-size:11px;font-weight:600;color:var(--text-dim);text-transform:uppercase;letter-spacing:0.5px;margin-bottom:4px">Positions (${d.positions.length})</div>
        <div style="max-height:260px;overflow-y:auto">
          ${positionRows}
        </div>

        <!-- Demo badge -->
        <div style="margin-top:10px;padding:6px;text-align:center;background:rgba(52,152,219,0.1);border:1px solid rgba(52,152,219,0.2);border-radius:4px">
          <span style="font-size:10px;color:#3498db;font-weight:500">DEMO &middot; $50K income &middot; $10K invested &middot; Working-class persona</span>
        </div>
      </div>`;

    this.setContent(html);
  }
}
