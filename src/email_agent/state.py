"""Shared state definition for the email agent."""

from __future__ import annotations

from typing import TypedDict

DEFAULT_MAX_REVISIONS = 3


class EmailAgentState(TypedDict):
    """State passed between every node of the email graph."""

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
    approved: bool

    # Revision tracking
    revision_count: int
    max_revisions: int

    # Outcome
    email_sent: bool
    send_error: str


def initial_state(
    topic: str,
    recipient: str,
    max_revisions: int = DEFAULT_MAX_REVISIONS,
) -> EmailAgentState:
    """Build a fully populated starting state.

    Every key is initialised so that nodes can read them without ``.get()``.
    """
    return EmailAgentState(
        topic=topic.strip(),
        recipient=recipient.strip(),
        research_results=[],
        facts=[],
        email_subject="",
        email_draft="",
        draft_history=[],
        feedback="",
        approved=False,
        revision_count=0,
        max_revisions=max(0, max_revisions),
        email_sent=False,
        send_error="",
    )
