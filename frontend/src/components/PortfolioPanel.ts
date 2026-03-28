import { Panel } from './Panel';
import { escapeHtml } from '@/utils/sanitize';
import * as d3 from 'd3';

/* ── Types ── */

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

interface DailyValue { date: string; value: number; }

interface PortfolioState {
  totalValue: number;
  initialInvestment: number;
  pnl: number;
  pnlPct: number;
  dataSource: string;
  dailyValues: DailyValue[];
  positions: Position[];
  riskScore: number;
  lastRebalance: string;
}

/* ── Bloomberg-inspired palette ── */

const ASSET_CLASS_COLORS: Record<string, string> = {
  'Equity':            '#4da6ff',
  'Managed Futures':   '#b388ff',
  'Structured Credit': '#64ffda',
  'Private Credit':    '#ff8a65',
  'Real Assets':       '#ffd740',
  'Fixed Income':      '#90a4ae',
};

const POS_GREEN = '#00e676';
const POS_RED   = '#ff1744';
const AMBER     = '#ff9800';

function defaultPositions(): Position[] {
  return [
    { ticker: 'SPY',  name: 'S&P 500 ETF',           weight: 0.20, value: 2000, price: 0, shares: 0, assetClass: 'Equity',            color: '#4da6ff', dailyChange: 0, changePct: 0 },
    { ticker: 'VTI',  name: 'Total Stock Market',     weight: 0.10, value: 1000, price: 0, shares: 0, assetClass: 'Equity',            color: '#4da6ff', dailyChange: 0, changePct: 0 },
    { ticker: 'DBMF', name: 'Managed Futures',        weight: 0.10, value: 1000, price: 0, shares: 0, assetClass: 'Managed Futures',   color: '#b388ff', dailyChange: 0, changePct: 0 },
    { ticker: 'KMLM', name: 'Mt Lucas Futures',       weight: 0.05, value: 500,  price: 0, shares: 0, assetClass: 'Managed Futures',   color: '#b388ff', dailyChange: 0, changePct: 0 },
    { ticker: 'RPAR', name: 'Risk Parity',            weight: 0.05, value: 500,  price: 0, shares: 0, assetClass: 'Managed Futures',   color: '#b388ff', dailyChange: 0, changePct: 0 },
    { ticker: 'JAAA', name: 'AAA CLO ETF',            weight: 0.10, value: 1000, price: 0, shares: 0, assetClass: 'Structured Credit', color: '#64ffda', dailyChange: 0, changePct: 0 },
    { ticker: 'CLOA', name: 'iShares AAA CLO',        weight: 0.05, value: 500,  price: 0, shares: 0, assetClass: 'Structured Credit', color: '#64ffda', dailyChange: 0, changePct: 0 },
    { ticker: 'ARCC', name: 'Ares Capital',           weight: 0.08, value: 800,  price: 0, shares: 0, assetClass: 'Private Credit',    color: '#ff8a65', dailyChange: 0, changePct: 0 },
    { ticker: 'BXSL', name: 'Blackstone Lending',     weight: 0.07, value: 700,  price: 0, shares: 0, assetClass: 'Private Credit',    color: '#ff8a65', dailyChange: 0, changePct: 0 },
    { ticker: 'GLDM', name: 'Gold MiniShares',        weight: 0.05, value: 500,  price: 0, shares: 0, assetClass: 'Real Assets',       color: '#ffd740', dailyChange: 0, changePct: 0 },
    { ticker: 'PDBC', name: 'Diversified Commodity',  weight: 0.05, value: 500,  price: 0, shares: 0, assetClass: 'Real Assets',       color: '#ffd740', dailyChange: 0, changePct: 0 },
    { ticker: 'AGG',  name: 'US Aggregate Bond',      weight: 0.05, value: 500,  price: 0, shares: 0, assetClass: 'Fixed Income',      color: '#90a4ae', dailyChange: 0, changePct: 0 },
    { ticker: 'SRLN', name: 'Senior Loan ETF',        weight: 0.05, value: 500,  price: 0, shares: 0, assetClass: 'Fixed Income',      color: '#90a4ae', dailyChange: 0, changePct: 0 },
  ];
}

/* ── Helpers ── */

function chgColor(v: number): string { return v >= 0 ? POS_GREEN : POS_RED; }
function chgSign(v: number): string  { return v >= 0 ? '+' : ''; }

/* ── Panel ── */

export class PortfolioPanel extends Panel {
  private state: PortfolioState;
  private hasRendered = false;
  private pollTimer: ReturnType<typeof setInterval> | null = null;

  constructor() {
    super({
      id: 'portfolio',
      title: 'Portfolio',
      showCount: false,
      className: 'panel-wide',
      infoTooltip: 'AI-optimized portfolio with alternative investments. Drag sliders to adjust allocation weights. Totals auto-normalize to 100%.',
    });
    this.state = {
      totalValue: 700000,
      initialInvestment: 700000,
      pnl: 0,
      pnlPct: 0,
      dataSource: 'demo',
      dailyValues: [],
      positions: defaultPositions(),
      riskScore: 0.42,
      lastRebalance: '2026-03-25',
    };
  }

  /* ── Data fetching (unchanged logic) ── */

  public async fetchData(): Promise<boolean> {
    if (!this.hasRendered) this.showLoading('Fetching live prices...');
    let isLive = false;
    try {
      const resp = await fetch('http://localhost:8000/api/portfolio');
      if (resp.ok) {
        const data = await resp.json();
        if (data.positions?.length > 0) {
          this.state.totalValue = data.totalValue;
          this.state.initialInvestment = data.initialInvestment || 700000;
          this.state.pnl = data.pnl || 0;
          this.state.pnlPct = data.pnlPct || 0;
          this.state.dailyValues = data.dailyValues || [];
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
            color: p.color || ASSET_CLASS_COLORS[p.assetClass] || '#90a4ae',
            dailyChange: p.dailyChange,
            changePct: p.changePct || 0,
          }));
          isLive = true;
        }
      }
    } catch { /* API unavailable — keep demo state */ }
    this.render();
    this.hasRendered = true;
    this.setDataBadge(isLive ? 'live' : 'cached');
    if (!this.pollTimer) {
      this.pollTimer = setInterval(() => void this.fetchData(), 5000);
    }
    return true;
  }

  /* ── Weight recalculation ── */

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

  /* ── Main render ── */

  private render(): void {
    const d = this.state;
    const dailyTotal = d.positions.reduce((s, p) => s + p.dailyChange, 0);
    const dailyPct = d.positions.reduce((s, p) => s + p.changePct * p.weight, 0);

    // Aggregate by asset class
    const classMap = new Map<string, { color: string; weight: number; value: number }>();
    for (const p of d.positions) {
      const ex = classMap.get(p.assetClass);
      if (ex) { ex.weight += p.weight; ex.value += p.value; }
      else classMap.set(p.assetClass, {
        color: ASSET_CLASS_COLORS[p.assetClass] || p.color,
        weight: p.weight,
        value: p.value,
      });
    }

    const riskLabel = d.riskScore < 0.3 ? 'LOW' : d.riskScore < 0.6 ? 'MOD' : 'HIGH';
    const riskColor = d.riskScore < 0.3 ? POS_GREEN : d.riskScore < 0.6 ? '#ffd740' : POS_RED;

    const el = document.createElement('div');
    el.className = 'pf-terminal';

    /* ── Value bar ── */
    el.innerHTML = `
      <div class="pf-value-bar">
        <div>
          <div class="pf-total-value">$${d.totalValue.toLocaleString()}</div>
          <div class="pf-pnl-daily" style="color:${chgColor(dailyTotal)}">
            ${chgSign(dailyPct)}${Math.abs(dailyPct).toFixed(2)}% today
            (${chgSign(dailyTotal)}$${Math.abs(dailyTotal).toFixed(0)})
          </div>
        </div>
        <div class="pf-pnl-group">
          <div class="pf-pnl-7d" style="color:${chgColor(d.pnl)}">
            ${chgSign(d.pnl)}$${Math.abs(d.pnl).toLocaleString()}
            (${chgSign(d.pnlPct)}${Math.abs(d.pnlPct).toFixed(2)}%)
          </div>
          <div style="font-size:8px;color:var(--text-muted);text-align:right;margin-top:1px">7-DAY P&amp;L</div>
        </div>
      </div>

      <!-- Charts rendered by D3 after DOM insertion -->
      <div class="pf-charts-row">
        <div class="pf-donut-wrap" id="pf-donut"></div>
        <div class="pf-chart-wrap" id="pf-area">${d.dailyValues.length < 2
          ? '<div style="display:flex;align-items:center;justify-content:center;height:120px;color:var(--text-muted);font-size:10px">Awaiting price history&hellip;</div>'
          : ''}</div>
      </div>

      <div class="pf-legend">
        ${Array.from(classMap.entries()).map(([cls, info]) => `
          <div class="pf-legend-item">
            <div class="pf-legend-dot" style="background:${info.color}"></div>
            <span class="pf-legend-label">${escapeHtml(cls)}</span>
            <span class="pf-legend-pct">${(info.weight * 100).toFixed(0)}%</span>
          </div>`).join('')}
      </div>

      <div class="pf-metrics">
        <div class="pf-metric">
          <div class="pf-metric-label">Risk</div>
          <div class="pf-metric-value" style="color:${riskColor}">${riskLabel}</div>
        </div>
        <div class="pf-metric">
          <div class="pf-metric-label">Positions</div>
          <div class="pf-metric-value">${d.positions.length}</div>
        </div>
        <div class="pf-metric">
          <div class="pf-metric-label">Rebalanced</div>
          <div class="pf-metric-value">${escapeHtml(d.lastRebalance.slice(5))}</div>
        </div>
        <div class="pf-metric">
          <div class="pf-metric-label">Daily &Delta;</div>
          <div class="pf-metric-value" style="color:${chgColor(dailyPct)}">${chgSign(dailyPct)}${Math.abs(dailyPct).toFixed(2)}%</div>
        </div>
      </div>

      <div class="pf-alloc-header">Allocations &mdash; drag to adjust</div>
      <div class="pf-alloc-list" id="pf-alloc-list">
        ${d.positions.map(p => {
          const fillPct = (Math.round(p.weight * 100) / 40) * 100;
          const classColor = ASSET_CLASS_COLORS[p.assetClass] || p.color;
          return `
          <div class="pf-alloc-row">
            <div>
              <div class="pf-ticker" style="color:${classColor}">${escapeHtml(p.ticker)}</div>
              <div class="pf-name">${p.price > 0 ? `$${p.price.toFixed(2)}` : escapeHtml(p.name)}</div>
            </div>
            <div style="display:flex;align-items:center;gap:4px">
              <input type="range" min="1" max="40" step="1" value="${Math.round(p.weight * 100)}"
                data-ticker="${p.ticker}"
                class="pf-slider"
                style="--thumb-color:${classColor};background:linear-gradient(90deg,${classColor}55 0%,${classColor}55 ${fillPct.toFixed(0)}%,rgba(255,255,255,0.06) ${fillPct.toFixed(0)}%,rgba(255,255,255,0.06) 100%)" />
            </div>
            <div class="pf-weight-col">
              <div class="pf-weight">${(p.weight * 100).toFixed(0)}%</div>
              <div class="pf-val-amount">$${p.value.toLocaleString()}</div>
              <div class="pf-change" style="color:${chgColor(p.changePct)}">
                ${chgSign(p.changePct)}${Math.abs(p.changePct).toFixed(2)}%${p.shares > 0 ? ` &middot; ${p.shares.toFixed(1)}sh` : ''}
              </div>
            </div>
          </div>`;
        }).join('')}
      </div>

      <div class="pf-status-bar">
        ${d.dataSource === 'demo' ? '&#9643; DEMO' : '&#9642; LIVE'}
        &middot; $700K PORTFOLIO &middot;
        ${d.dataSource !== 'demo' ? 'YAHOO FINANCE' : 'API OFFLINE'}
      </div>`;

    // Wire sliders
    el.querySelectorAll<HTMLInputElement>('input[type="range"]').forEach(slider => {
      slider.addEventListener('input', (e) => {
        const t = e.target as HTMLInputElement;
        this.handleSlider(t.dataset.ticker!, parseInt(t.value, 10));
      });
    });

    // Swap into DOM
    this.element.querySelector('.panel-content')!.replaceChildren(el);

    // D3 charts (require live DOM)
    this.renderDonut(el.querySelector('#pf-donut')!);
    if (d.dailyValues.length > 1) {
      this.renderAreaChart(el.querySelector('#pf-area')!);
    }
  }

  /* ─────────────────────────────────────────────
     D3 Donut Chart — grouped by asset class
     ───────────────────────────────────────────── */

  private renderDonut(container: HTMLElement): void {
    const d = this.state;
    const size = 140;
    const R = size / 2 - 4;
    const r = R * 0.55;

    // Aggregate by asset class
    const classMap = new Map<string, { color: string; weight: number }>();
    for (const p of d.positions) {
      const ex = classMap.get(p.assetClass);
      if (ex) ex.weight += p.weight;
      else classMap.set(p.assetClass, { color: ASSET_CLASS_COLORS[p.assetClass] || p.color, weight: p.weight });
    }
    const classData = Array.from(classMap.entries()).map(([name, info]) => ({
      name, color: info.color, weight: info.weight,
    }));

    const svg = d3.select(container)
      .append('svg')
      .attr('width', size)
      .attr('height', size)
      .attr('viewBox', `0 0 ${size} ${size}`)
      .append('g')
      .attr('transform', `translate(${size / 2},${size / 2})`);

    const pie = d3.pie<{ name: string; color: string; weight: number }>()
      .value(v => v.weight)
      .sort(null)
      .padAngle(0.02);

    const arc = d3.arc<d3.PieArcDatum<{ name: string; color: string; weight: number }>>()
      .innerRadius(r)
      .outerRadius(R)
      .cornerRadius(3);

    const arcHover = d3.arc<d3.PieArcDatum<{ name: string; color: string; weight: number }>>()
      .innerRadius(r - 2)
      .outerRadius(R + 4)
      .cornerRadius(3);

    svg.selectAll('path')
      .data(pie(classData))
      .join('path')
      .attr('d', arc as any)
      .attr('fill', v => v.data.color)
      .attr('opacity', 0.85)
      .attr('stroke', 'rgba(0,0,0,0.5)')
      .attr('stroke-width', 0.5)
      .style('cursor', 'pointer')
      .style('filter', 'drop-shadow(0 1px 4px rgba(0,0,0,0.4))')
      .on('mouseenter', function(_event, v) {
        d3.select(this).transition().duration(120)
          .attr('d', arcHover as any).attr('opacity', 1);
        svg.select('.pf-dc-top').text(v.data.name.length > 12 ? v.data.name.slice(0, 11) + '\u2026' : v.data.name);
        svg.select('.pf-dc-bot').text(`${(v.data.weight * 100).toFixed(1)}%`);
      })
      .on('mouseleave', function() {
        d3.select(this).transition().duration(120)
          .attr('d', arc as any).attr('opacity', 0.85);
        svg.select('.pf-dc-top').text('TOTAL');
        svg.select('.pf-dc-bot').text(`$${(d.totalValue / 1000).toFixed(0)}K`);
      });

    // Center label
    svg.append('text').attr('class', 'pf-dc-top')
      .attr('text-anchor', 'middle').attr('dy', '-0.3em')
      .attr('fill', AMBER).attr('font-size', '9px')
      .attr('font-weight', '600').attr('font-family', 'var(--font-mono)')
      .attr('letter-spacing', '0.5px').text('TOTAL');

    svg.append('text').attr('class', 'pf-dc-bot')
      .attr('text-anchor', 'middle').attr('dy', '1.1em')
      .attr('fill', 'var(--text)').attr('font-size', '14px')
      .attr('font-weight', '700').attr('font-family', 'var(--font-mono)')
      .text(`$${(d.totalValue / 1000).toFixed(0)}K`);
  }

  /* ─────────────────────────────────────────────
     D3 Area Chart — 7-day P&L with crosshair
     ───────────────────────────────────────────── */

  private renderAreaChart(container: HTMLElement): void {
    const values = this.state.dailyValues;
    if (values.length < 2) return;

    // Clear placeholder
    container.innerHTML = '';

    const margin = { top: 8, right: 8, bottom: 22, left: 50 };
    const width = Math.max(container.clientWidth || 200, 160);
    const height = 130;
    const iW = width - margin.left - margin.right;
    const iH = height - margin.top - margin.bottom;

    const svg = d3.select(container)
      .append('svg')
      .attr('width', width)
      .attr('height', height)
      .style('display', 'block');

    const g = svg.append('g')
      .attr('transform', `translate(${margin.left},${margin.top})`);

    // Scales
    const dates = values.map(v => new Date(v.date));
    const vals = values.map(v => v.value);
    const mn = Math.min(...vals);
    const mx = Math.max(...vals);
    const pad = (mx - mn) * 0.08 || 100;

    const x = d3.scaleTime().domain([dates[0]!, dates[dates.length - 1]!]).range([0, iW]);
    const y = d3.scaleLinear().domain([mn - pad, mx + pad]).range([iH, 0]);

    // Gridlines
    const yTicks = y.ticks(4);
    g.selectAll('.pf-gy')
      .data(yTicks)
      .join('line')
      .attr('x1', 0).attr('x2', iW)
      .attr('y1', v => y(v)).attr('y2', v => y(v))
      .attr('stroke', 'rgba(255,255,255,0.04)')
      .attr('stroke-dasharray', '2,4');

    // Gradient fill
    const up = vals[vals.length - 1]! >= vals[0]!;
    const color = up ? POS_GREEN : POS_RED;
    const gradId = `pf-ag-${Date.now()}`;
    const defs = svg.append('defs');
    const grad = defs.append('linearGradient')
      .attr('id', gradId).attr('x1', '0').attr('y1', '0').attr('x2', '0').attr('y2', '1');
    grad.append('stop').attr('offset', '0%').attr('stop-color', color).attr('stop-opacity', 0.22);
    grad.append('stop').attr('offset', '100%').attr('stop-color', color).attr('stop-opacity', 0.01);

    // Area
    const area = d3.area<DailyValue>()
      .x(v => x(new Date(v.date)))
      .y0(iH)
      .y1(v => y(v.value))
      .curve(d3.curveMonotoneX);

    g.append('path').datum(values).attr('d', area).attr('fill', `url(#${gradId})`);

    // Line
    const line = d3.line<DailyValue>()
      .x(v => x(new Date(v.date)))
      .y(v => y(v.value))
      .curve(d3.curveMonotoneX);

    g.append('path').datum(values)
      .attr('d', line)
      .attr('fill', 'none')
      .attr('stroke', color)
      .attr('stroke-width', 1.5);

    // End-of-line dot
    const last = values[values.length - 1]!;
    g.append('circle')
      .attr('cx', x(new Date(last.date)))
      .attr('cy', y(last.value))
      .attr('r', 3)
      .attr('fill', color)
      .attr('stroke', 'rgba(0,0,0,0.6)')
      .attr('stroke-width', 1);

    // Pulsing glow on latest point
    g.append('circle')
      .attr('cx', x(new Date(last.date)))
      .attr('cy', y(last.value))
      .attr('r', 3)
      .attr('fill', 'none')
      .attr('stroke', color)
      .attr('stroke-width', 0.8)
      .attr('opacity', 0.6)
      .append('animate')
      .attr('attributeName', 'r')
      .attr('from', '3').attr('to', '8')
      .attr('dur', '1.8s')
      .attr('repeatCount', 'indefinite');

    // Axes
    const xAxis = g.append('g')
      .attr('transform', `translate(0,${iH})`)
      .call(d3.axisBottom(x).ticks(Math.min(values.length, 5))
        .tickFormat(d3.timeFormat('%b %d') as any).tickSize(0))
      .attr('class', 'pf-axis');
    xAxis.select('.domain').attr('stroke', 'rgba(255,255,255,0.06)');

    const yAxis = g.append('g')
      .call(d3.axisLeft(y).ticks(4)
        .tickFormat(v => `$${d3.format('.2s')(v as number)}`).tickSize(0))
      .attr('class', 'pf-axis');
    yAxis.select('.domain').attr('stroke', 'rgba(255,255,255,0.06)');

    /* ── Crosshair overlay ── */

    const crossG = g.append('g').style('display', 'none');
    crossG.append('line').attr('class', 'cv')
      .attr('y1', 0).attr('y2', iH)
      .attr('stroke', `${AMBER}80`).attr('stroke-width', 0.5).attr('stroke-dasharray', '3,3');
    crossG.append('line').attr('class', 'ch')
      .attr('x1', 0).attr('x2', iW)
      .attr('stroke', `${AMBER}80`).attr('stroke-width', 0.5).attr('stroke-dasharray', '3,3');
    crossG.append('circle')
      .attr('r', 4).attr('fill', 'none').attr('stroke', AMBER).attr('stroke-width', 1.5);

    const tooltip = d3.select(container)
      .append('div').attr('class', 'pf-crosshair-tooltip').style('display', 'none');

    const bisect = d3.bisector<DailyValue, Date>(v => new Date(v.date)).left;

    g.append('rect')
      .attr('width', iW).attr('height', iH).attr('fill', 'transparent')
      .on('mouseenter', () => { crossG.style('display', null); tooltip.style('display', null); })
      .on('mouseleave', () => { crossG.style('display', 'none'); tooltip.style('display', 'none'); })
      .on('mousemove', (event) => {
        const [mx] = d3.pointer(event);
        const dateAt = x.invert(mx);
        const idx = Math.min(bisect(values, dateAt, 1), values.length - 1);
        const d0 = values[idx - 1];
        const d1 = values[idx];
        const pt = (d0 && d1)
          ? (+dateAt - +new Date(d0.date) > +new Date(d1.date) - +dateAt ? d1 : d0)
          : (d1 || d0);
        if (!pt) return;

        const cx = x(new Date(pt.date));
        const cy = y(pt.value);
        crossG.select('.cv').attr('x1', cx).attr('x2', cx);
        crossG.select('.ch').attr('y1', cy).attr('y2', cy);
        crossG.select('circle').attr('cx', cx).attr('cy', cy);

        // Keep tooltip inside container bounds
        const tipLeft = Math.min(cx + margin.left + 10, width - 90);
        tooltip
          .style('left', `${tipLeft}px`)
          .style('top', `${cy + margin.top - 12}px`)
          .html(`<div style="color:${AMBER};font-size:8px;letter-spacing:0.3px">${pt.date}</div>
                 <div style="font-weight:700">$${pt.value.toLocaleString()}</div>`);
      });
  }
}
