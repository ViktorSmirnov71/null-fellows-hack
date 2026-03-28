"""
Signal Aggregator
Time-weighted aggregation of sentiment signals per ticker/sector.
"""

import math
from collections import defaultdict
from datetime import datetime, timezone


class SignalAggregator:
    def __init__(self, half_life_hours: float = 6.0):
        self.half_life_hours = half_life_hours

    def aggregate(self, signals: list) -> list:
        """
        Aggregate signals per ticker/sector with exponential time-decay weighting.
        More recent signals get higher weight.
        """
        now = datetime.now(timezone.utc)
        grouped: dict[str, list] = defaultdict(list)

        for signal in signals:
            key = signal.ticker or signal.sector or "market"
            grouped[key].append(signal)

        aggregated = []
        for key, group in grouped.items():
            weighted_sum = 0.0
            weight_total = 0.0

            for signal in group:
                age_hours = max((now - signal.timestamp.replace(tzinfo=timezone.utc)).total_seconds() / 3600, 0.01)
                weight = math.exp(-math.log(2) * age_hours / self.half_life_hours)
                weighted_sum += signal.direction * weight
                weight_total += weight

            if weight_total > 0:
                avg_direction = weighted_sum / weight_total
                # Use the most recent signal as the base, update direction
                latest = max(group, key=lambda s: s.timestamp)
                latest.direction = avg_direction
                latest.conviction = min(abs(avg_direction) * len(group) / 5, 1.0)  # Scale by volume
                aggregated.append(latest)

        return sorted(aggregated, key=lambda s: abs(s.direction), reverse=True)
