"""Environment driven configuration.

Every environment variable used by the project is read here and nowhere else.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache

from dotenv import load_dotenv

# Loads `.env` from the working directory, so `uv run streamlit run app.py`
# picks up your keys without extra setup.
load_dotenv()

DEFAULT_MODEL = "openai/gpt-oss-20b"
DEFAULT_SENDER = "onboarding@resend.dev"
DEFAULT_TEMPERATURE = 0.3

MISSING_KEY_HELP = (
    "GROQ_API_KEY is not set.\n\n"
    "1. Get a free key at https://console.groq.com/keys\n"
    "2. `cp .env.example .env`\n"
    "3. Add the key to `.env` and restart the app"
)


class ConfigError(RuntimeError):
    """Raised when a required setting is missing or malformed."""


def _env_float(name: str, default: float) -> float:
    """Read a float from the environment, falling back to ``default``."""
    raw = os.getenv(name)
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError as exc:
        raise ConfigError(f"{name} must be a number, got {raw!r}.") from exc


@dataclass(frozen=True)
class Settings:
    """Immutable snapshot of the runtime configuration."""

    groq_api_key: str | None
    groq_model: str
    temperature: float
    resend_api_key: str | None
    email_from: str

    @property
    def llm_ready(self) -> bool:
        """True when the language model can be created."""
        return bool(self.groq_api_key)

    @property
    def email_ready(self) -> bool:
        """True when an approved email will really be delivered."""
        return bool(self.resend_api_key)

    def require_llm(self) -> str:
        """Return the Groq key, or explain how to get one."""
        if not self.groq_api_key:
            raise ConfigError(MISSING_KEY_HELP)
        return self.groq_api_key


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the cached settings for this process."""
    return Settings(
        groq_api_key=os.getenv("GROQ_API_KEY") or None,
        groq_model=os.getenv("GROQ_MODEL") or DEFAULT_MODEL,
        temperature=_env_float("LLM_TEMPERATURE", DEFAULT_TEMPERATURE),
        resend_api_key=os.getenv("RESEND_API_KEY") or None,
        email_from=os.getenv("EMAIL_FROM") or DEFAULT_SENDER,
    )
