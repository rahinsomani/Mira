from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    llm_provider: str = os.getenv("LLM_PROVIDER", "anthropic")
    anthropic_api_key: str | None = os.getenv("ANTHROPIC_API_KEY")
    display_port: int = int(os.getenv("MIRA_DISPLAY_PORT", "8000"))


settings = Settings()
