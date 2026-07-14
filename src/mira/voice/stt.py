"""Speech-to-text interface. Swap MockSTT for a real provider (e.g. Whisper, Google STT)."""

from abc import ABC, abstractmethod


class SpeechToText(ABC):
    @abstractmethod
    def transcribe(self, audio_bytes: bytes) -> str:
        """Return the transcribed text for a chunk of recorded audio."""


class MockSTT(SpeechToText):
    """Returns a canned transcript so the rest of the pipeline can be built and tested
    before a real STT provider is wired in."""

    def __init__(self, canned_response: str = "what's my blood sugar right now"):
        self.canned_response = canned_response

    def transcribe(self, audio_bytes: bytes) -> str:
        return self.canned_response
