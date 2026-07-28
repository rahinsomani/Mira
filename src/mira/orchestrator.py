"""Wires data -> llm together for a single question."""

from mira import audit_log, llm, trend_analysis
from mira.data.glucose_store import GlucoseStore
from mira.data.nutrition_store import NutritionStore

# F6: scripted, not LLM-generated, so it's safe to speak even when the LLM
# or glucose data itself is unreachable.
DATA_UNAVAILABLE_MESSAGE = (
    "I can't reach your glucose sensor right now, so I don't have a current "
    "reading. Please check your sensor and app, or use a blood glucose meter "
    "as a backup."
)

NOT_ENOUGH_TREND_DATA_MESSAGE = "I don't have enough recent readings yet for a trend."

# Deliberately simple keyword match rather than an LLM call: this only
# decides which deterministic path to take, so it needs to be cheap and
# predictable, not another thing that can hallucinate.
_TREND_KEYWORDS = (
    "trend", "pattern", "over time", "past few hours", "last few hours",
    "last 6 hours", "past 6 hours", "how have i been", "how has it been",
    "how's my glucose been", "graph", "chart", "history",
)


def _looks_like_trend_question(text):
    lowered = text.lower()
    return any(keyword in lowered for keyword in _TREND_KEYWORDS)


class Orchestrator:
    def __init__(self):
        self.glucose_store = GlucoseStore()
        self.nutrition_store = NutritionStore()

    def handle_query(self, question_text):
        status = self.glucose_store.status()
        if not status["available"]:
            audit_log.log("cgm_unavailable", DATA_UNAVAILABLE_MESSAGE, reason=status["reason"])
            return {
                "response_text": DATA_UNAVAILABLE_MESSAGE,
                "glucose_reading": None,
                "food_info": None,
                "message_type": "unavailable",
            }

        if _looks_like_trend_question(question_text):
            return self._handle_trend_query()

        glucose_reading = status["reading"]
        food_info = self.nutrition_store.lookup(question_text)
        response_text = llm.answer(question_text, glucose_reading, food_info)

        value = glucose_reading["value"]
        # Reuses llm's own thresholds rather than redefining them here, so
        # the "is this urgent" line never drifts out of sync with llm.answer.
        message_type = "urgent" if (value < llm.LOW_MMOL or value > llm.HIGH_MMOL) else "normal"

        return {
            "response_text": response_text,
            "glucose_reading": glucose_reading,
            "food_info": food_info,
            "message_type": message_type,
        }

    def _handle_trend_query(self):
        readings = self.glucose_store.recent(hours=6)
        if not readings:
            audit_log.log("trend_unavailable", NOT_ENOUGH_TREND_DATA_MESSAGE)
            return {
                "response_text": NOT_ENOUGH_TREND_DATA_MESSAGE,
                "glucose_reading": None,
                "food_info": None,
                "message_type": "unavailable",
            }

        stats = trend_analysis.compute(readings)
        response_text = llm.narrate_trend(stats)

        return {
            "response_text": response_text,
            "glucose_reading": None,
            "food_info": None,
            "message_type": "trend",
            "trend_stats": stats,
        }
