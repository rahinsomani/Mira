"""Glucose reading access, backed by Dexcom sandbox-shaped data for now."""

import json
from pathlib import Path

_DATA_FILE = Path(__file__).parent / "sandbox_egvs.json"


class GlucoseStore:
    def __init__(self):
        self._egvs = json.loads(_DATA_FILE.read_text())["egvs"]

    def current_reading(self):
        return self._egvs[-1]

    def history(self):
        return self._egvs
