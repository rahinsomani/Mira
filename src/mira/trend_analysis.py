"""Deterministic glucose trend metrics (AI4: computed by code, never by the LLM -
llm.narrate_trend() only turns these numbers into a sentence, it doesn't compute them)."""

from dataclasses import dataclass

from mira.data.glucose_store import IN_RANGE_HIGH, IN_RANGE_LOW


@dataclass
class TrendStats:
    readings: list
    average: float
    minimum: float
    maximum: float
    direction: str  # "steady" | "rising" | "falling"
    time_in_range_pct: int


def compute(readings):
    """readings: list of {"displayTime", "value", "trend"}, oldest first. Non-empty."""
    values = [r["value"] for r in readings]

    half = len(values) // 2 or 1
    first_half_avg = sum(values[:half]) / half
    second_half = values[half:] or values[:half]
    second_half_avg = sum(second_half) / len(second_half)
    delta = second_half_avg - first_half_avg
    if delta > 0.5:
        direction = "rising"
    elif delta < -0.5:
        direction = "falling"
    else:
        direction = "steady"

    in_range_count = sum(1 for v in values if IN_RANGE_LOW <= v <= IN_RANGE_HIGH)

    return TrendStats(
        readings=readings,
        average=round(sum(values) / len(values), 1),
        minimum=min(values),
        maximum=max(values),
        direction=direction,
        time_in_range_pct=round(in_range_count / len(values) * 100),
    )
