"""Independent safety check on LLM output, required by AI1. This runs after
generation and before the response reaches TTS/display — it is not the LLM
checking itself, it's a separate rule-based gate."""

import re
from dataclasses import dataclass

_MEDICATION_CHANGE_PATTERNS = [
    r"\btake (an? )?(extra|less|more)\b.*\b(insulin|dose|medication|pill)\b",
    r"\bstop (taking )?(your )?(insulin|medication|metformin)\b",
    r"\bincrease your (dose|insulin)\b",
    r"\bdecrease your (dose|insulin)\b",
    r"\bskip your (dose|medication|insulin)\b",
]

_DIAGNOSIS_PATTERNS = [
    r"\byou have (diabetes|hypoglycemia|hyperglycemia)\b",
    r"\byou('re| are) diagnosed with\b",
]


@dataclass
class SafetyResult:
    passed: bool
    reason: str = ""


def check(response_text: str) -> SafetyResult:
    lowered = response_text.lower()

    for pattern in _MEDICATION_CHANGE_PATTERNS:
        if re.search(pattern, lowered):
            return SafetyResult(False, "response suggests a medication/dose change")

    for pattern in _DIAGNOSIS_PATTERNS:
        if re.search(pattern, lowered):
            return SafetyResult(False, "response makes a diagnosis")

    return SafetyResult(True)
