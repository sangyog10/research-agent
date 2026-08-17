"""Graph nodes for the human-in-the-loop email agent.

Each node takes the current state and returns only the keys it changes.
"""

from __future__ import annotations

from typing import Any, Literal

from langgraph.types import interrupt

from . import console
from email_agent.parsing import DEFAULT_SUBJECT, parse_email_draft
from email_agent.prompts import (
    DRAFT_PROMPT,
    FACT_EXTRACTION_PROMPT,
    REVISION_PROMPT,
)
from email_agent.sender import send_email
from email_agent.state import EmailAgentState
from llm import complete, lines_from
from search import SearchError, web_search

MAX_SEARCH_RESULTS = 5
APPROVE_WORDS = frozenset({"approve", "approved", "yes", "y", "true", "ok"})

Route = Literal["send", "revise", "abort"]


# ---------------------------------------------------------------------------
# 1. Research
# ---------------------------------------------------------------------------
def research_node(state: EmailAgentState) -> dict[str, Any]:
    """Search the web for the topic and store formatted sources."""
    topic = state["topic"]

    console.header("🔎 RESEARCH")
    console.info(f"Topic: {topic}")
    console.info("Searching the web...")

    try:
        results = web_search(topic, max_results=MAX_SEARCH_RESULTS)
    except SearchError as exc:
        console.warn(f"Search failed: {exc}")
        return {"research_results": [f"Search failed: {exc}"]}

    if not results:
        console.warn("No search results were found.")
        return {"research_results": ["No search results were found."]}

    for index, result in enumerate(results, 1):
        console.step(f"✓ Result {index}: {result.title[:60]}")

    return {
        "research_results": [result.as_source(index) for index, result in enumerate(results, 1)]
    }


# ---------------------------------------------------------------------------
# 2. Fact extraction
# ---------------------------------------------------------------------------
def extract_facts_node(state: EmailAgentState) -> dict[str, Any]:
    """Condense raw search results into a short list of facts."""
    console.header("🧠 FACT EXTRACTION")

    prompt = FACT_EXTRACTION_PROMPT.format(
        topic=state["topic"],
        research="\n\n".join(state["research_results"]),
    )

    try:
        facts = lines_from(complete(prompt))
    except Exception as exc:  # noqa: BLE001 - keep the workflow alive
        console.warn(f"Fact extraction failed: {exc}")
        facts = []

    if not facts:
        facts = ["Unable to extract facts from research."]

    console.ok(f"Extracted {len(facts)} facts")
    for fact in facts:
        console.step(f"• {fact[:100]}")

    return {"facts": facts}


# ---------------------------------------------------------------------------
# 3. First draft
# ---------------------------------------------------------------------------
def draft_email_node(state: EmailAgentState) -> dict[str, Any]:
    """Write the initial email draft from the extracted facts."""
    console.header("✍️  EMAIL DRAFT")

    prompt = DRAFT_PROMPT.format(
        topic=state["topic"],
        facts="\n".join(state["facts"]),
    )

    try:
        draft = complete(prompt)
    except Exception as exc:  # noqa: BLE001
        console.warn(f"Draft generation failed: {exc}")
        draft = (
            f"SUBJECT: {DEFAULT_SUBJECT}\n\n"
            "BODY:\nPlease find the latest information regarding the requested topic."
        )

    subject, body = parse_email_draft(draft)
    _print_draft("📧 Generated Draft", subject, body)

    return {
        "email_subject": subject,
        "email_draft": body,
        "draft_history": [draft],
    }


# ---------------------------------------------------------------------------
# 4. Human review (the interrupt)
# ---------------------------------------------------------------------------
def human_review_node(state: EmailAgentState) -> dict[str, Any]:
    """Pause the graph until a human approves or rejects the draft.

    ``interrupt()`` raises internally, so everything after it only runs once the
    graph is resumed with ``Command(resume=...)``.
    """
    console.header("👤 HUMAN REVIEW")
    console.info(f"To: {state['recipient']}")
    console.info(f"Subject: {state['email_subject']}")
    print()
    console.block(state["email_draft"])

    decision = interrupt(
        {
            "type": "email_review",
            "message": "Review the email before it is sent.",
            "recipient": state["recipient"],
            "subject": state["email_subject"],
            "body": state["email_draft"],
            "revision_count": state["revision_count"],
            "options": ["approve", "reject"],
        }
    )

    approved, feedback = _read_decision(decision)
    console.info(f"\n👤 Human decision: {'approve' if approved else 'reject'}")

    return {"approved": approved, "feedback": feedback}


# ---------------------------------------------------------------------------
# 5. Router
# ---------------------------------------------------------------------------
def review_router(state: EmailAgentState) -> Route:
    """Decide what happens after the human review."""
    console.info("\n🚦 REVIEW ROUTER")

    if state["approved"]:
        console.step("→ Email approved, sending.")
        return "send"

    if state["revision_count"] >= state["max_revisions"]:
        console.step("→ Maximum revisions reached, giving up.")
        return "abort"

    console.step("→ Email rejected, sending draft for revision.")
    return "revise"


# ---------------------------------------------------------------------------
# 6. Revision
# ---------------------------------------------------------------------------
def revise_email_node(state: EmailAgentState) -> dict[str, Any]:
    """Rewrite the draft using the human's feedback."""
    console.header("🔄 REVISION")
    console.info(f"Revision: {state['revision_count'] + 1}/{state['max_revisions']}")
    console.info(f"Human feedback: {state['feedback'] or '(none given)'}")

    prompt = REVISION_PROMPT.format(
        topic=state["topic"],
        subject=state["email_subject"],
        body=state["email_draft"],
        feedback=state["feedback"] or "Make the email clearer and more professional.",
    )

    try:
        new_draft = complete(prompt)
    except Exception as exc:  # noqa: BLE001
        console.warn(f"Revision failed, keeping the previous draft: {exc}")
        new_draft = f"SUBJECT: {state['email_subject']}\n\nBODY:\n{state['email_draft']}"

    subject, body = parse_email_draft(new_draft)
    _print_draft("📧 Revised Draft", subject, body)

    return {
        "email_subject": subject,
        "email_draft": body,
        "revision_count": state["revision_count"] + 1,
        "draft_history": [*state["draft_history"], new_draft],
        # Clear the feedback so the next review starts from a clean slate.
        "feedback": "",
    }


# ---------------------------------------------------------------------------
# 7. Send
# ---------------------------------------------------------------------------
def send_email_node(state: EmailAgentState) -> dict[str, Any]:
    """Deliver the approved email (or report why it could not be delivered)."""
    console.header("📨 SEND EMAIL")

    # Defensive guard: the router should never route an unapproved draft here.
    if not state["approved"]:
        console.warn("Email was not approved, refusing to send.")
        return {"email_sent": False, "send_error": "Email was not approved."}

    outcome = send_email(
        recipient=state["recipient"],
        subject=state["email_subject"],
        body=state["email_draft"],
    )

    if outcome.sent:
        console.ok(f"Email sent to {state['recipient']}!")
    elif outcome.dry_run:
        console.warn(outcome.error)
        console.step("Add RESEND_API_KEY to .env to deliver for real.")
    else:
        console.error(f"Email sending failed: {outcome.error}")

    return {"email_sent": outcome.sent, "send_error": outcome.error}


# ---------------------------------------------------------------------------
# 8. Abort
# ---------------------------------------------------------------------------
def abort_node(state: EmailAgentState) -> dict[str, Any]:
    """Terminate without sending after too many rejected revisions."""
    console.header("🛑 ABORTED")
    message = (
        f"Stopped after {state['revision_count']} revision(s) without approval; nothing was sent."
    )
    console.warn(message)
    return {"email_sent": False, "send_error": message}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _read_decision(decision: Any) -> tuple[bool, str]:
    """Normalise whatever the caller passed to ``Command(resume=...)``.

    Accepts ``{"approved": bool, "feedback": str}`` as well as plain strings
    like ``"approve"`` / ``"no"``.
    """
    if isinstance(decision, dict):
        return bool(decision.get("approved", False)), str(decision.get("feedback", "") or "")

    if isinstance(decision, bool):
        return decision, ""

    return str(decision).strip().lower() in APPROVE_WORDS, ""


def _print_draft(title: str, subject: str, body: str) -> None:
    """Show a draft in a consistent way."""
    print(f"\n{title}:")
    console.rule("-")
    print(f"Subject: {subject}")
    console.rule("-")
    print(body)
    console.rule("-")
