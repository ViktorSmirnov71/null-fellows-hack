"""
Signal Aggregator
Time-weighted aggregation of sentiment signals per ticker/sector.
"""

import math
from collections import defaultdict
from dataclasses import replace
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
                # Safe timezone handling — two explicit cases:
                # 1. No tzinfo at all → assume UTC and attach it
                # 2. Has tzinfo → convert to UTC properly with astimezone
                ts = signal.timestamp
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
                else:
                    ts = ts.astimezone(timezone.utc)

                age_hours = max(
                    (now - ts).total_seconds() / 3600,
                    0.01
                )
                weight = math.exp(
                    -math.log(2) * age_hours / self.half_life_hours
                )
                weighted_sum += signal.direction * weight
                weight_total += weight

            if weight_total > 0:
                avg_direction = weighted_sum / weight_total

                # Conviction = 70% signal strength + 30% corroborating volume
                # A single strong signal (0.9) scores 0.66
                # Five weak signals (0.1) score 0.22
                # Volume credit maxes out at 10 signals
                strength_score = abs(avg_direction)
                volume_score   = min(len(group) / 10, 1.0)
                conviction     = min(
                    0.7 * strength_score + 0.3 * volume_score,
                    1.0
                )

                # dataclasses.replace() creates a new object with updated fields
                # The original signal in the pipeline's list stays untouched
                latest = max(group, key=lambda s: s.timestamp)
                aggregated_signal = replace(
                    latest,
                    direction=avg_direction,
                    conviction=conviction
                )
                aggregated.append(aggregated_signal)

        return sorted(
            aggregated,
            key=lambda s: abs(s.direction),
            reverse=True
        )