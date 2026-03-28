# Investment Policy Constraints

These constraints are immutable. The AutoAllocator loop must respect them at all times.

## Position Limits
- No single position may exceed 25% of total portfolio
- No single position may be below 1% (avoid dust positions)
- Portfolio must hold at least 8 distinct positions

## Asset Class Limits
- Core equity: 15-40% of portfolio
- Managed futures / trend-following: 10-30%
- CLO / structured credit: 5-20%
- Private credit (BDCs): 5-20%
- Real assets (gold, commodities): 5-15%
- Bonds / fixed income: 5-20%

## Risk Limits
- Maximum drawdown: -25% (hard stop — any strategy breaching this is rejected)
- Minimum Sharpe ratio: must exceed 60/40 benchmark
- Maximum annual turnover: 300% (avoid excessive trading)
- Maximum single-month loss: -12%

## Rebalancing
- Allowed frequencies: weekly, monthly, quarterly
- Default: monthly

## Universe
- Only allocate to tickers defined in PORTFOLIO_UNIVERSE (allocator.py)
- Do not add new tickers without updating the universe
- All positions must be liquid (daily trading volume > $1M)

## Benchmark
- Primary: 60/40 (SPY 60% / AGG 40%)
- Secondary: S&P 500 (SPY)
- Must beat primary benchmark on Sharpe ratio
