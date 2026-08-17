"""DuckDuckGo web search."""

from __future__ import annotations

from dataclasses import dataclass

from ddgs import DDGS

DEFAULT_MAX_RESULTS = 5
_UNTITLED = "Untitled"


class SearchError(RuntimeError):
    """Raised when the search backend fails or is rate limited."""


@dataclass(frozen=True)
class SearchResult:
    """One normalised search hit."""

    title: str
    body: str
    url: str

    def as_source(self, index: int) -> str:
        """Citation-style block handed to the fact-extraction prompt."""
        return f"Source {index}\nTitle: {self.title}\nContent: {self.body}\nURL: {self.url}"


def web_search(query: str, max_results: int = DEFAULT_MAX_RESULTS) -> list[SearchResult]:
    """Run a text search and return normalised results.

    Raises:
        SearchError: if the backend raises (network error, rate limit, ...).
    """
    query = query.strip()
    if not query:
        return []

    try:
        with DDGS() as ddgs:
            raw_results = list(ddgs.text(query, max_results=max_results))
    except Exception as exc:  # noqa: BLE001 - the backend raises many types
        raise SearchError(f"{type(exc).__name__}: {exc}") from exc

    return [
        SearchResult(
            title=(item.get("title") or _UNTITLED).strip(),
            body=(item.get("body") or "").strip(),
            url=(item.get("href") or item.get("url") or "").strip(),
        )
        for item in raw_results
    ]
