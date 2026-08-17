"""State carried through the graph."""

from __future__ import annotations

from typing import TypedDict

DEFAULT_MAX_REVISIONS = 3


class EmailAgentState(TypedDict):
    """Every key is initialised up front so nodes can read them directly."""

    # Input
    topic: str
    recipient: str

    # Research phase
    research_results: list[str]
    facts: list[str]

    # Draft
    email_subject: str
    email_draft: str
    draft_history: list[str]

    # Human feedback
    feedback: str
    feedback_history: list[str]
    approved: bool

    # Revision tracking
    revision_count: int
    max_revisions: int

    # Outcome
    email_sent: bool
    send_error: str

    # Non-fatal problems worth showing in the UI
    warnings: list[str]


def initial_state(
    topic: str,
    recipient: str,
    max_revisions: int = DEFAULT_MAX_REVISIONS,
) -> EmailAgentState:
    """Build a fully populated starting state."""
    return EmailAgentState(
        topic=topic.strip(),
        recipient=recipient.strip(),
        research_results=[],
        facts=[],
        email_subject="",
        email_draft="",
        draft_history=[],
        feedback="",
        feedback_history=[],
        approved=False,
        revision_count=0,
        max_revisions=max(0, max_revisions),
        email_sent=False,
        send_error="",
        warnings=[],
    )
