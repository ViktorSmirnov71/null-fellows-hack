# Null Fellows Demo Script — 3 Minutes

---

## INTRO — Non-technical teammate (30 seconds max)

"Every day, retail investors make portfolio decisions competing with institutional players and some filthy rich people with professional wealth managers. They see stock prices, but they're not empowered with the resources to leverage signals that actually move markets — a military escalation in the Strait of Hormuz, a surprise rate decision from the Fed, a regime change in a commodity-producing nation. This information asymmetry makes wealth democratisation impossible, and leaves so much commercial opportunitity on the table for investment managers as well. 

We built a system to fix this. It watches the world, interprets the signal, and autonomously acts on it."

---

## PORTFOLIO VIEW — Henry (45 seconds)

"Let me show you what autonomous allocation actually looks like.

This is our live portfolio. Thirteen positions across equities, managed futures, structured credit, private credit BDCs, and real assets. These weights weren't set by a human — they were evolved by our AutoAllocator agent.

The system runs a continuous loop: it proposes a mutation to the portfolio — maybe tilting defensive into gold and Treasuries because geopolitical risk just spiked — then it backtests that change against five years of historical data. If the Sharpe ratio improves and max drawdown stays above our negative-twenty-five-percent hard stop, it keeps the change and commits it. If not, it reverts. Every decision has a paper trail.

Right now you can see our live Sharpe, Sortino, and Calmar ratios updating in real time against a sixty-forty benchmark. This isn't a recommendation engine — it has agency. It researches, decides, and executes."

---

## WORLD EVENTS — Henry (60 seconds)

"Now here's where the alpha actually comes from — the signal layer.

This is our World Events dashboard. We're ingesting from GDELT — that's fifteen minutes of latency on every global news event — plus USGS seismic data, FRED macroeconomic indicators, commodity futures, and VIX. Every signal gets classified by sector: energy, metals, conflict, rates, equity, credit, trade.

These aren't just headlines. Each event flows through our three-tier AI sentiment cascade. First, Groq running Llama 70B does a fast relevance filter — is this financially material? Then FinBERT, a domain-specific transformer, scores the sentiment and extracts ticker and sector signals. And for high-conviction signals — above zero-point-seven — Claude does deep second-order analysis. What does a Houthi attack on a tanker actually mean for shipping rates, insurance premiums, and energy ETFs?

The output is a composite world risk score — broken into geopolitical, macro, and volatility components — that feeds directly into the portfolio optimizer. When risk spikes, the system autonomously rotates into defensive positions. When it drops, it leans into growth. No human in the loop."

---

## AUTO RESEARCH / WRAP-UP — Henry (45 seconds)

"What you're seeing is the autoresearch pattern applied to finance. The AutoAllocator doesn't just rebalance — it runs experiments. It has six mutation strategies: pair shifts, defensive tilts, growth tilts, random perturbation, concentration, and world-signal-driven moves. Each experiment is logged with its timestamp, Sharpe delta, and outcome — kept or discarded.

The entire investment policy is codified. No single position exceeds twenty-five percent. The portfolio holds at least eight distinct positions. Annual turnover is capped at three hundred percent. These aren't guidelines — they're hard constraints the agent cannot violate.

This is what we believe the future of portfolio management looks like: a system with real-time global awareness, autonomous decision-making, and full auditability. Every trade has a reason. Every reason traces back to a signal. And every signal traces back to the real world.

---

**Total time: ~3 minutes**
**Screens to show: Portfolio view -> World Events dashboard -> AutoAllocator experiments log**
</content>
</invoke>
