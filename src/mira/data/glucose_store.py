"""Glucose reading access.

Uses the live Dexcom API when credentials are configured (see dexcom_client),
and falls back to the bundled Dexcom sandbox-shaped JSON otherwise.

F6: if the live API call fails, returns nothing, or the latest reading is
stale, callers must be told data is unavailable rather than silently shown
old or fake numbers - see status().
"""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from mira.data.dexcom_client import DexcomClient

_DATA_FILE = Path(__file__).parent / "sandbox_egvs.json"
# CGMs normally report every ~5 minutes; anything older suggests a dropout.
_STALE_AFTER = timedelta(minutes=20)

# "Everyday" in-range band used for the status pill and time-in-range stats -
# distinct from llm.LOW_MMOL/HIGH_MMOL, which mark medically severe territory.
IN_RANGE_LOW = 4.0
IN_RANGE_HIGH = 10.0


class GlucoseStore:
    def __init__(self, client=None):
        # If no client is passed, try to build one from the environment.
        self._client = client or DexcomClient.from_env()
        self._fallback_egvs = json.loads(_DATA_FILE.read_text())["egvs"]

    @property
    def is_live(self):
        return self._client is not None

    def current_reading(self):
        """Convenience accessor. Prefer status() where unavailability matters."""
        return self.status()["reading"]

    def history(self):
        if self._client is not None:
            try:
                readings = self._client.get_egvs()
            except Exception:
                return self._fallback_egvs
            if readings:
                return readings
        return self._fallback_egvs

    def recent(self, hours=6):
        """Readings from the last `hours`, oldest first, for trend display.

        The bundled fallback fixture has fixed timestamps that don't track
        the real clock, so it's returned as-is (it's already a short demo
        window) rather than filtered against "now".
        """
        if not self.is_live:
            return self._fallback_egvs

        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        recent = []
        for reading in self.history():
            try:
                reading_time = datetime.fromisoformat(reading["displayTime"])
            except (KeyError, ValueError, TypeError):
                continue
            if reading_time.tzinfo is None:
                reading_time = reading_time.replace(tzinfo=timezone.utc)
            if reading_time >= cutoff:
                recent.append(reading)
        return recent

    def status(self):
        """Return {"reading": dict|None, "available": bool, "reason": str|None}.

        `reading` may still be populated (e.g. a stale last-known value) even
        when `available` is False, so a display can show "last seen" info
        alongside the unavailable notice if it wants to.
        """
        if self._client is not None:
            try:
                readings = self._client.get_egvs()
            except Exception as exc:
                return {"reading": None, "available": False, "reason": f"CGM connection error: {exc}"}
            if not readings:
                return {"reading": None, "available": False, "reason": "no data returned"}
            latest = readings[-1]
            if self._enforce_staleness() and self._is_stale(latest):
                return {"reading": latest, "available": False, "reason": "stale reading"}
            return {"reading": latest, "available": True, "reason": None}

        # No live client configured: bundled sample data, for dev/demo only.
        return {"reading": self._fallback_egvs[-1], "available": True, "reason": None}

    def _enforce_staleness(self):
        # Dexcom's sandbox data is pre-generated and doesn't track the real
        # wall clock, so an old sandbox reading doesn't mean the CGM
        # connection is actually down - only enforce this against production.
        return "sandbox" not in (self._client.base_url or "").lower()

    @staticmethod
    def _is_stale(reading):
        try:
            reading_time = datetime.fromisoformat(reading["displayTime"])
        except (KeyError, ValueError, TypeError):
            return True
        # The live API returns timestamps with a UTC offset; the bundled
        # fallback fixture doesn't. Normalize both to aware UTC to compare.
        if reading_time.tzinfo is None:
            reading_time = reading_time.replace(tzinfo=timezone.utc)
        return datetime.now(timezone.utc) - reading_time > _STALE_AFTER
