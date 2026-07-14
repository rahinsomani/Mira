"""Text-to-speech interface. Swap MockTTS for a real provider."""

from abc import ABC, abstractmethod


class TextToSpeech(ABC):
    @abstractmethod
    def synthesize(self, text: str) -> bytes:
        """Return audio bytes for the given text."""


class MockTTS(TextToSpeech):
    """Returns empty audio; logs what would have been spoken."""

    def synthesize(self, text: str) -> bytes:
        print(f"[MockTTS] would speak: {text!r}")
        return b""
