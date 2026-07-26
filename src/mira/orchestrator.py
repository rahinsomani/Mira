"""Wires data -> llm together for a single question."""

from mira import llm
from mira.data.glucose_store import GlucoseStore
from mira.data.nutrition_store import NutritionStore


class Orchestrator:
    def __init__(self):
        self.glucose_store = GlucoseStore()
        self.nutrition_store = NutritionStore()

    def handle_query(self, question_text):
        glucose_reading = self.glucose_store.current_reading()
        food_info = self.nutrition_store.lookup(question_text)
        response_text = llm.answer(question_text, glucose_reading, food_info)

        return {
            "response_text": response_text,
            "glucose_reading": glucose_reading,
            "food_info": food_info,
        }
