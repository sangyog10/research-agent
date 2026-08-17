"""State definition for the iterative research agent."""

from __future__ import annotations

from typing import TypedDict

DEFAULT_MAX_ITERATIONS = 2
DEFAULT_QUALITY_THRESHOLD = 0.8
DEFAULT_MAX_FINDINGS = 10


class ResearchState(TypedDict):
    """State passed between every node of the research graph."""

    # Input
    original_topic: str
    topic: str

    # Research loop
    research_questions: list[str]
    search_queries: list[str]
    search_results: list[str]
    key_findings: list[str]

    # Loop control
    iteration: int
    max_iterations: int
    quality_score: float
    quality_threshold: float
    max_findings: int

    # Output
    final_report: str
    status: str
    errors: list[str]


def initial_state(
    topic: str,
    *,
    max_iterations: int = DEFAULT_MAX_ITERATIONS,
    quality_threshold: float = DEFAULT_QUALITY_THRESHOLD,
    max_findings: int = DEFAULT_MAX_FINDINGS,
) -> ResearchState:
    """Build a fully populated starting state."""
    topic = topic.strip()
    return ResearchState(
        original_topic=topic,
        topic=topic,
        research_questions=[],
        search_queries=[],
        search_results=[],
        key_findings=[],
        iteration=0,
        max_iterations=max(1, max_iterations),
        quality_score=0.0,
        quality_threshold=quality_threshold,
        max_findings=max_findings,
        final_report="",
        status="initialized",
        errors=[],
    )
