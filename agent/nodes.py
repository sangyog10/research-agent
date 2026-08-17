"""Graph nodes.

Every node takes the state and returns only the keys it changes. Nothing here
prints or imports Streamlit: non-fatal problems are appended to
``state["warnings"]`` and the UI decides how to show them.
"""

from __future__ import annotations

from typing import Any, Literal

from langgraph.types import interrupt

from agent.llm import complete, lines_from
from agent.parsing import DEFAULT_SUBJECT, parse_email_draft
from agent.prompts import DRAFT_PROMPT, FACT_EXTRACTION_PROMPT, REVISION_PROMPT
from agent.search import SearchError, web_search
from agent.sender import send_email
from agent.state import EmailAgentState

MAX_SEARCH_RESULTS = 5
APPROVE_WORDS = frozenset({"approve", "approved", "yes", "y", "true", "ok"})

Route = Literal["send", "revise", "abort"]


# 1. Research
def research_node(state: EmailAgentState) -> dict[str, Any]:
    """Search the web for the topic and store formatted sources."""
    try:
        results = web_search(state["topic"], max_results=MAX_SEARCH_RESULTS)
    except SearchError as exc:
        return {
            "research_results": [f"Search failed: {exc}"],
            "warnings": [*state["warnings"], f"Web search failed: {exc}"],
        }

    if not results:
        return {
            "research_results": ["No search results were found."],
            "warnings": [*state["warnings"], "The web search returned no results."],
        }

    return {
        "research_results": [result.as_source(index) for index, result in enumerate(results, 1)]
    }


# 2. Fact extraction
def extract_facts_node(state: EmailAgentState) -> dict[str, Any]:
    """Condense raw search results into a short list of facts."""
    prompt = FACT_EXTRACTION_PROMPT.format(
        topic=state["topic"],
        research="\n\n".join(state["research_results"]),
    )

    try:
        facts = lines_from(complete(prompt))
        warnings = state["warnings"]
    except Exception as exc: 
        facts = []
        warnings = [*state["warnings"], f"Fact extraction failed: {exc}"]

    if not facts:
        facts = ["Unable to extract facts from the research."]

    return {"facts": facts, "warnings": warnings}


# 3. First draft
def draft_email_node(state: EmailAgentState) -> dict[str, Any]:
    """Write the initial email draft from the extracted facts."""
    prompt = DRAFT_PROMPT.format(
        topic=state["topic"],
        facts="\n".join(state["facts"]),
    )

    try:
        draft = complete(prompt)
        warnings = state["warnings"]
    except Exception as exc:  # noqa: BLE001
        draft = (
            f"SUBJECT: {DEFAULT_SUBJECT}\n\n"
            "BODY:\nPlease find the latest information regarding the requested topic."
        )
        warnings = [*state["warnings"], f"Draft generation failed: {exc}"]

    subject, body = parse_email_draft(draft)

    return {
        "email_subject": subject,
        "email_draft": body,
        "draft_history": [draft],
        "warnings": warnings,
    }


# 4. Human review - this is where the graph pauses
def human_review_node(state: EmailAgentState) -> dict[str, Any]:
    """Pause until a human approves or rejects the draft.

    ``interrupt()`` stops execution and hands the payload to the caller. When
    the caller resumes with ``Command(resume=...)`` this node runs again from
    the top, and ``interrupt()`` returns that value instead of pausing.
    """
    decision = interrupt(
        {
            "type": "email_review",
            "message": "Review the email before it is sent.",
            "recipient": state["recipient"],
            "subject": state["email_subject"],
            "body": state["email_draft"],
            "revision_count": state["revision_count"],
            "max_revisions": state["max_revisions"],
            "options": ["approve", "reject"],
        }
    )

    approved, feedback = read_decision(decision)
    return {"approved": approved, "feedback": feedback}


# 5. Router
def review_router(state: EmailAgentState) -> Route:
    """Decide what happens after the human review."""
    if state["approved"]:
        return "send"

    if state["revision_count"] >= state["max_revisions"]:
        return "abort"

    return "revise"


# 6. Revision
def revise_email_node(state: EmailAgentState) -> dict[str, Any]:
    """Rewrite the draft using the human's feedback."""
    feedback = state["feedback"] or "Make the email clearer and more professional."

    prompt = REVISION_PROMPT.format(
        topic=state["topic"],
        subject=state["email_subject"],
        body=state["email_draft"],
        feedback=feedback,
    )

    try:
        new_draft = complete(prompt)
        warnings = state["warnings"]
    except Exception as exc:  # noqa: BLE001
        new_draft = f"SUBJECT: {state['email_subject']}\n\nBODY:\n{state['email_draft']}"
        warnings = [*state["warnings"], f"Revision failed, kept the previous draft: {exc}"]

    subject, body = parse_email_draft(new_draft)

    return {
        "email_subject": subject,
        "email_draft": body,
        "revision_count": state["revision_count"] + 1,
        "draft_history": [*state["draft_history"], new_draft],
        "feedback_history": [*state["feedback_history"], feedback],
        # Clear the feedback so the next review starts from a clean slate.
        "feedback": "",
        "warnings": warnings,
    }


# 7. Send
def send_email_node(state: EmailAgentState) -> dict[str, Any]:
    """Deliver the approved email, or record why it could not be delivered."""
    # Defensive guard: the router never routes an unapproved draft here.
    if not state["approved"]:
        return {"email_sent": False, "send_error": "Email was not approved."}

    outcome = send_email(
        recipient=state["recipient"],
        subject=state["email_subject"],
        body=state["email_draft"],
    )

    return {"email_sent": outcome.sent, "send_error": outcome.error}


# 8. Abort
def abort_node(state: EmailAgentState) -> dict[str, Any]:
    """Stop without sending after too many rejected revisions."""
    return {
        "email_sent": False,
        "send_error": (
            f"Stopped after {state['revision_count']} revision(s) "
            "without approval; nothing was sent."
        ),
    }


# Helper
def read_decision(decision: Any) -> tuple[bool, str]:
    """Normalise whatever was passed to ``Command(resume=...)``.

    Accepts ``{"approved": bool, "feedback": str}``, a bare bool, or a string
    such as ``"approve"`` / ``"no"``.
    """
    if isinstance(decision, dict):
        return bool(decision.get("approved", False)), str(decision.get("feedback", "") or "")

    if isinstance(decision, bool):
        return decision, ""

    return str(decision).strip().lower() in APPROVE_WORDS, ""
