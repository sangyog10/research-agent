"""Helpers for starting, inspecting and resuming an email agent run."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Command

from langgraph_capstone.email_agent.state import DEFAULT_MAX_REVISIONS, initial_state

RunConfig = dict[str, Any]


def new_config(thread_id: str | None = None) -> RunConfig:
    """Build a LangGraph config with a unique thread id.

    The thread id is what lets the checkpointer resume this exact run, so each
    run gets its own id instead of a shared hard-coded one.
    """
    return {"configurable": {"thread_id": thread_id or f"email-{uuid4().hex[:12]}"}}


def start_workflow(
    app: CompiledStateGraph,
    topic: str,
    recipient: str,
    *,
    max_revisions: int = DEFAULT_MAX_REVISIONS,
    thread_id: str | None = None,
) -> tuple[dict[str, Any], RunConfig]:
    """Run the graph up to the first human review interrupt."""
    config = new_config(thread_id)
    result = app.invoke(initial_state(topic, recipient, max_revisions), config)
    return result, config


def resume_workflow(
    app: CompiledStateGraph,
    config: RunConfig,
    *,
    approved: bool,
    feedback: str = "",
) -> dict[str, Any]:
    """Resume a paused run with the human's decision.

    Args:
        approved: ``True`` sends the email, ``False`` triggers a revision.
        feedback: What to change; only used when ``approved`` is ``False``.
    """
    decision = {"approved": approved, "feedback": feedback}
    return app.invoke(Command(resume=decision), config)


def is_waiting_for_human(app: CompiledStateGraph, config: RunConfig) -> bool:
    """True when the graph is paused on an interrupt."""
    snapshot = app.get_state(config)
    return bool(getattr(snapshot, "interrupts", ()))
