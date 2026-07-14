"""Wires one voice turn together: STT -> data lookup -> LLM (+ safety) -> TTS + display.

This is the piece most likely to need rework as real providers get swapped in;
keep the module boundaries (voice/data/llm/display) stable so that's a local change.
"""

from __future__ import annotations

from mira.data.glucose_store import GlucoseStore
from mira.data.nutrition_store import NutritionStore
from mira.display.server import update_display
from mira.llm.client import LLMClient, MockLLMClient
from mira.llm.fallback import GLUCOSE_UNAVAILABLE, MEAL_UNAVAILABLE, SAFETY_BLOCKED
from mira.llm.prompts import build_glucose_query_prompt, build_meal_query_prompt
from mira.llm.safety import check as safety_check
from mira.voice.stt import MockSTT, SpeechToText
from mira.voice.tts import MockTTS, TextToSpeech


class Orchestrator:
    def __init__(
        self,
        stt: SpeechToText | None = None,
        tts: TextToSpeech | None = None,
        llm: LLMClient | None = None,
    ) -> None:
        self.stt = stt or MockSTT()
        self.tts = tts or MockTTS()
        self.llm = llm or MockLLMClient()
        self.glucose = GlucoseStore()
        self.nutrition = NutritionStore()

    def handle_voice_turn(self, audio_bytes: bytes, requester_confirmed: bool) -> str:
        """requester_confirmed: caller must confirm the request came from a real,
        explicit household member interaction (Pr1) before this is invoked."""
        if not requester_confirmed:
            raise PermissionError("glucose data requires a confirmed explicit request (Pr1)")

        transcript = self.stt.transcribe(audio_bytes)
        reading = self.glucose.current_reading()

        food = self._extract_food_mention(transcript)
        if food:
            info = self.nutrition.lookup(food)
            if info is None:
                response_text = MEAL_UNAVAILABLE
            else:
                prompt = build_meal_query_prompt(
                    reading.value_mmol_l, reading.trend.value, info.food_name, info.carbs_g, info.glycemic_index
                )
                response_text = self._generate_safe_response(prompt, MEAL_UNAVAILABLE)
        else:
            prompt = build_glucose_query_prompt(reading.value_mmol_l, reading.trend.value)
            response_text = self._generate_safe_response(
                prompt, GLUCOSE_UNAVAILABLE.format(value=reading.value_mmol_l, trend=reading.trend.value)
            )

        self.tts.synthesize(response_text)
        update_display(str(reading.value_mmol_l), reading.trend.value, response_text)
        return response_text

    def _generate_safe_response(self, prompt: str, fallback_text: str) -> str:
        try:
            raw = self.llm.generate(prompt)
        except Exception:
            return fallback_text

        result = safety_check(raw)
        if not result.passed:
            return SAFETY_BLOCKED
        return raw

    def _extract_food_mention(self, transcript: str) -> str | None:
        for food in self.nutrition.all_foods():
            if food.food_name.lower() in transcript.lower():
                return food.food_name
        return None
