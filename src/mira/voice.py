"""Speech-to-text and text-to-speech, both via Groq."""

import os
import re

import requests

_TRANSCRIPTIONS_URL = "https://api.groq.com/openai/v1/audio/transcriptions"
_STT_MODEL = "whisper-large-v3-turbo"

_SPEECH_URL = "https://api.groq.com/openai/v1/audio/speech"
_TTS_MODEL = "canopylabs/orpheus-v1-english"
_DEFAULT_VOICE = "hannah"


def _api_key():
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("Missing GROQ_API_KEY. Set it in your environment or .env.")
    return api_key


def transcribe(audio_bytes, filename="audio.webm"):
    """Transcribe recorded audio to text."""
    resp = requests.post(
        _TRANSCRIPTIONS_URL,
        headers={"Authorization": f"Bearer {_api_key()}"},
        files={"file": (filename, audio_bytes)},
        data={"model": _STT_MODEL},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["text"].strip()


def synthesize(text, voice=_DEFAULT_VOICE):
    """Synthesize speech audio (wav bytes) for the given text."""
    resp = requests.post(
        _SPEECH_URL,
        headers={"Authorization": f"Bearer {_api_key()}"},
        json={
            "model": _TTS_MODEL,
            "input": _for_speech(text),
            "voice": voice,
            "response_format": "wav",
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.content


def _for_speech(text):
    """Rewrite unit abbreviations so the TTS model reads them naturally.

    The on-screen text keeps "mmol/L" (AI1 requires Canadian units in any
    displayed copy); only the audio needs the spoken-out form.
    """
    return re.sub(r"mmol/L", "millimoles per litre", text, flags=re.IGNORECASE)
