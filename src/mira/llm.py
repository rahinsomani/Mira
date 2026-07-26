"""LLM client (Groq chat completions) with the AI1 safety checks on its output.

AI1 requires: no medication-change guidance ever, an independent safety check
(not just prompt instructions), and a scripted fallback if the model or the
check fails. Those three things are kept together in this one file since they
describe a single pipeline: ask -> check -> return something safe.
"""

import os
import re

import requests

_CHAT_URL = "https://api.groq.com/openai/v1/chat/completions"
_MODEL = "openai/gpt-oss-120b"

_SYSTEM_PROMPT = """You are Mira, a voice assistant on a smart mirror that helps an \
older adult understand their glucose readings and food choices at home.

Rules you must always follow:
- Speak in plain, warm, human-sounding language. No jargon, no em dashes.
- Use Canadian units only: mmol/L for glucose, never mg/dL.
- You are not a clinician. Never suggest starting, stopping, or changing a \
medication or insulin dose, and never give a specific dose. For anything \
medication-related, tell the person to check with their doctor, pharmacist, \
or diabetes care team.
- If a reading or symptom sounds urgent or dangerous, tell the person plainly \
and suggest they contact their care provider or emergency services rather \
than trying to manage it themselves.
- Keep answers very short: one or two short sentences, about 25 words total, \
suitable for reading aloud. Do not pad with extra caveats or repetition.
"""

_MAX_SPOKEN_SENTENCES = 2

LOW_MMOL = 4.0
HIGH_MMOL = 13.9

_MEDICATION_PATTERNS = [
    r"\bincrease your (insulin|dose|dosage)\b",
    r"\bdecrease your (insulin|dose|dosage)\b",
    r"\btake \d+ (units?|mg|milligrams?)\b",
    r"\bstop taking\b",
    r"\bskip your (dose|medication|insulin)\b",
    r"\badjust your (dose|dosage|insulin)\b",
    r"\bchange your (dose|dosage|medication)\b",
]

FALLBACK_MESSAGE = (
    "I'm not able to answer that safely right now. Please check with your "
    "doctor, pharmacist, or care team, or contact them directly if this feels "
    "urgent."
)


def answer(question, glucose_reading, food_info=None):
    """Ask the LLM, then run its response through the AI1 safety checks.

    Always returns *something* safe to speak: an urgent scripted message, the
    generic fallback, or the model's own response if nothing was flagged.
    """
    value = glucose_reading["value"]
    if value < LOW_MMOL or value > HIGH_MMOL:
        return _urgent_message(value)

    try:
        response_text = _ask_groq(question, glucose_reading, food_info)
    except Exception:
        return FALLBACK_MESSAGE

    response_text = _truncate_to_sentences(response_text, _MAX_SPOKEN_SENTENCES)
    if _contains_medication_language(response_text):
        return FALLBACK_MESSAGE
    return response_text


def _ask_groq(question, glucose_reading, food_info):
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("Missing GROQ_API_KEY. Set it in your environment or .env.")

    context_lines = [
        f"Current glucose reading: {glucose_reading['value']} mmol/L, "
        f"trend: {glucose_reading.get('trend', 'unknown')}."
    ]
    if food_info:
        context_lines.append(
            f"Food mentioned: {food_info['name']}, about {food_info['carbs_g']}g carbs, "
            f"{food_info['glycemic_impact']} glycemic impact. Note: {food_info['note']}."
        )
    context_lines.append(f"Question: {question}")

    resp = requests.post(
        _CHAT_URL,
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "model": _MODEL,
            "max_tokens": 150,
            # gpt-oss is a reasoning model; without this it can spend the
            # whole max_tokens budget on hidden reasoning and return an
            # empty/truncated answer (finish_reason "length").
            "reasoning_effort": "low",
            "messages": [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": "\n".join(context_lines)},
            ],
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"].strip()


def _urgent_message(value):
    if value < LOW_MMOL:
        return (
            f"Your glucose is reading {value} mmol/L, which is low. Please "
            "treat this now with a fast-acting sugar and let a family member "
            "or your care provider know."
        )
    return (
        f"Your glucose is reading {value} mmol/L, which is high. Please "
        "contact your care provider if this doesn't come down or if you feel "
        "unwell."
    )


def _truncate_to_sentences(text, max_sentences):
    """Hard cap on spoken length, independent of what the model was asked for."""
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    return " ".join(sentences[:max_sentences]).strip()


def _contains_medication_language(text):
    lowered = text.lower()
    return any(re.search(pattern, lowered) for pattern in _MEDICATION_PATTERNS)
