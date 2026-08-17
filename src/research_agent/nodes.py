"""Graph nodes for the iterative research agent.

These functions are deliberately UI-free: they never import Streamlit, so the
same graph can be driven from a notebook, a script or the web app. Problems are
appended to ``state["errors"]`` instead of being printed.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from langgraph_capstone.llm import complete, lines_from
from langgraph_capstone.research_agent.prompts import (
    ANALYSIS_PROMPT,
    QUESTION_PROMPT,
    REPORT_PROMPT,
    TOPIC_REFINEMENT_PROMPT,
)
from langgraph_capstone.research_agent.state import ResearchState
from langgraph_capstone.search import SearchError, web_search

QUESTIONS_PER_ROUND = 3
RESULTS_PER_QUESTION = 2
FINDINGS_PER_ROUND = 5
RESULTS_TO_ANALYSE = 10
FINDING_WEIGHT = 0.2

NODE_LABELS: dict[str, str] = {
    "input": "📥 Input Processor",
    "questions": "❓ Question Generator",
    "search": "🔍 Search Tool",
    "analyze": "🔬 Analyzer",
    "report": "📝 Report Generator",
}


# ---------------------------------------------------------------------------
# 1. Input processing
# ---------------------------------------------------------------------------
def input_processor_node(state: ResearchState) -> dict[str, Any]:
    """Sharpen a broad topic into a more specific research focus."""
    prompt = TOPIC_REFINEMENT_PROMPT.format(topic=state["topic"])

    try:
        refined = complete(prompt).splitlines()[0].strip().strip('"')
    except Exception as exc:  # noqa: BLE001 - a vague topic still works
        return {
            "status": "topic_processed",
            "errors": [*state["errors"], f"Topic refinement failed: {exc}"],
        }

    return {
        "topic": refined or state["topic"],
        "status": "topic_processed",
    }


# ---------------------------------------------------------------------------
# 2. Question generation
# ---------------------------------------------------------------------------
def question_generator_node(state: ResearchState) -> dict[str, Any]:
    """Add a fresh batch of searchable questions."""
    existing = state["research_questions"]
    prompt = QUESTION_PROMPT.format(
        topic=state["topic"],
        covered="\n".join(existing) or "(nothing yet)",
    )

    try:
        questions = lines_from(complete(prompt), limit=QUESTIONS_PER_ROUND)
    except Exception as exc:  # noqa: BLE001
        return {
            "status": "questions_generated",
            "errors": [*state["errors"], f"Question generation failed: {exc}"],
        }

    return {
        "research_questions": _dedupe([*existing, *questions]),
        "status": "questions_generated",
    }


# ---------------------------------------------------------------------------
# 3. Search
# ---------------------------------------------------------------------------
def search_tool_node(state: ResearchState) -> dict[str, Any]:
    """Search the web for every question that has not been searched yet."""
    # Copy before mutating: never edit the lists held in state in place.
    results = list(state["search_results"])
    searched = list(state["search_queries"])
    errors = list(state["errors"])

    for question in state["research_questions"]:
        if question in searched:
            continue

        try:
            hits = web_search(question, max_results=RESULTS_PER_QUESTION)
        except SearchError as exc:
            errors.append(f"Search failed for {question!r}: {exc}")
            continue

        results.extend(hit.as_snippet() for hit in hits)
        searched.append(question)

    return {
        "search_results": _dedupe(results),
        "search_queries": searched,
        "iteration": state["iteration"] + 1,
        "status": "search_completed",
        "errors": errors,
    }


# ---------------------------------------------------------------------------
# 4. Analysis
# ---------------------------------------------------------------------------
def analyzer_node(state: ResearchState) -> dict[str, Any]:
    """Turn raw search snippets into key findings and score the research."""
    if not state["search_results"]:
        return {
            "key_findings": state["key_findings"],
            "quality_score": 0.0,
            "status": "analysis_completed",
            "errors": [*state["errors"], "No search results were available to analyse."],
        }

    prompt = ANALYSIS_PROMPT.format(
        topic=state["topic"],
        results="\n".join(state["search_results"][:RESULTS_TO_ANALYSE]),
    )

    try:
        findings = lines_from(complete(prompt), limit=FINDINGS_PER_ROUND)
    except Exception as exc:  # noqa: BLE001
        return {
            "status": "analysis_completed",
            "errors": [*state["errors"], f"Analysis failed: {exc}"],
        }

    all_findings = _dedupe([*state["key_findings"], *findings])

    return {
        "key_findings": all_findings,
        "quality_score": min(len(all_findings) * FINDING_WEIGHT, 1.0),
        "status": "analysis_completed",
    }


# ---------------------------------------------------------------------------
# 5. Router
# ---------------------------------------------------------------------------
def should_continue_research(state: ResearchState) -> Literal["search", "report"]:
    """Loop back for more research, or stop and write the report."""
    if state["iteration"] >= state["max_iterations"]:
        return "report"

    if state["quality_score"] >= state["quality_threshold"]:
        return "report"

    if len(state["key_findings"]) >= state["max_findings"]:
        return "report"

    return "search"


# ---------------------------------------------------------------------------
# 6. Report generation
# ---------------------------------------------------------------------------
def report_generator_node(state: ResearchState) -> dict[str, Any]:
    """Compile everything into a markdown report with a metadata footer."""
    prompt = REPORT_PROMPT.format(
        topic=state["topic"],
        questions="\n".join(state["research_questions"]) or "(none)",
        findings="\n".join(state["key_findings"]) or "(none)",
        source_count=len(state["search_results"]),
    )

    try:
        report = complete(prompt)
        errors = state["errors"]
    except Exception as exc:  # noqa: BLE001
        report = "# Report unavailable\n\nThe language model could not generate the report."
        errors = [*state["errors"], f"Report generation failed: {exc}"]

    return {
        "final_report": report + _metadata_footer(state),
        "status": "report_completed",
        "errors": errors,
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _metadata_footer(state: ResearchState) -> str:
    """Render the run statistics appended to every report."""
    rows = {
        "Topic": state["topic"],
        "Original request": state["original_topic"],
        "Questions asked": len(state["research_questions"]),
        "Sources consulted": len(state["search_results"]),
        "Key findings": len(state["key_findings"]),
        "Research iterations": state["iteration"],
        "Generated": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }
    lines = "\n".join(f"- **{label}:** {value}" for label, value in rows.items())
    return f"\n\n---\n\n### 📊 Research metadata\n\n{lines}\n"


def _dedupe(items: list[str]) -> list[str]:
    """Remove case-insensitive duplicates while preserving order."""
    seen: set[str] = set()
    unique: list[str] = []
    for item in items:
        key = item.strip().lower()
        if key and key not in seen:
            seen.add(key)
            unique.append(item.strip())
    return unique
