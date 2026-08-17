"""Single place where the language model is created and called."""

from __future__ import annotations

from functools import lru_cache

from langchain_groq import ChatGroq

from agent.config import get_settings


@lru_cache(maxsize=1)
def get_llm() -> ChatGroq:
    """Return a cached Groq chat model.

    Raises:
        ConfigError: if ``GROQ_API_KEY`` is missing.
    """
    settings = get_settings()
    return ChatGroq(
        model=settings.groq_model,
        api_key=settings.require_llm(),
        temperature=settings.temperature,
    )


def complete(prompt: str) -> str:
    """Send one prompt to the LLM and return the text response."""
    response = get_llm().invoke(prompt)
    return str(response.content).strip()


def lines_from(text: str, limit: int | None = None) -> list[str]:
    """Split an LLM answer into clean, non-empty lines."""
    items = [line.strip() for line in text.splitlines() if line.strip()]
    return items[:limit] if limit else items
