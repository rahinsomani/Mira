"""Glucose reading access.

Uses the live Dexcom API when credentials are configured (see dexcom_client),
and falls back to the bundled Dexcom sandbox-shaped JSON otherwise.
"""

import json
from pathlib import Path

from mira.data.dexcom_client import DexcomClient

_DATA_FILE = Path(__file__).parent / "sandbox_egvs.json"


class GlucoseStore:
    def __init__(self, client=None):
        # If no client is passed, try to build one from the environment.
        self._client = client or DexcomClient.from_env()
        self._fallback_egvs = json.loads(_DATA_FILE.read_text())["egvs"]

    @property
    def is_live(self):
        return self._client is not None

    def current_reading(self):
        return self.history()[-1]

    def history(self):
        if self._client is not None:
            readings = self._client.get_egvs()
            if readings:
                return readings
        # No client configured, or the live call returned nothing.
        return self._fallback_egvs
