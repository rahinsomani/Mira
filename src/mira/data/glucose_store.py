"""Glucose reading access. Replace with the real CGM data pipeline.

Pr1 constraint: callers must confirm a real, explicit user request before
calling `current_reading()` or `history()` — this module does not enforce
that on its own, the orchestrator does (see orchestrator.py).
"""

from datetime import datetime, timedelta

from mira.data.models import GlucoseReading, Trend

_MOCK_HISTORY = [
    GlucoseReading(6.1, Trend.STEADY, datetime.now() - timedelta(hours=3)),
    GlucoseReading(6.8, Trend.RISING, datetime.now() - timedelta(hours=2)),
    GlucoseReading(7.4, Trend.RISING, datetime.now() - timedelta(hours=1)),
    GlucoseReading(7.1, Trend.STEADY, datetime.now()),
]


class GlucoseStore:
    def current_reading(self) -> GlucoseReading:
        return _MOCK_HISTORY[-1]

    def history(self, hours: int = 6) -> list[GlucoseReading]:
        cutoff = datetime.now() - timedelta(hours=hours)
        return [r for r in _MOCK_HISTORY if r.timestamp >= cutoff]
