"""LLM client interface. Swap MockLLMClient for a real provider (Anthropic, etc.)
by implementing LLMClient and wiring it up in orchestrator.py based on
config.settings.llm_provider."""

from abc import ABC, abstractmethod


class LLMClient(ABC):
    @abstractmethod
    def generate(self, prompt: str) -> str:
        """Return a raw model response for the given prompt. Callers are
        responsible for running the response through llm.safety.check()."""


class MockLLMClient(LLMClient):
    """Canned responses for local development without an API key."""

    def generate(self, prompt: str) -> str:
        return (
            "Your glucose is a bit above your usual range and trending up. "
            "Nothing urgent, but keep an eye on it over the next hour."
        )
