"""Nutrition lookup for meal guidance (F2)."""

import json
import re
from pathlib import Path

_DATA_FILE = Path(__file__).parent / "nutrition_data.json"


class NutritionStore:
    def __init__(self):
        self._foods = json.loads(_DATA_FILE.read_text())["foods"]

    def lookup(self, text):
        """Return the first food entry whose name appears in `text`, or None.

        Matching is a case-insensitive substring/word check since the text
        comes from speech transcription and won't match exactly.
        """
        lowered = text.lower()
        for food in self._foods:
            if re.search(r"\b" + re.escape(food["name"]) + r"\b", lowered):
                return food
        return None
