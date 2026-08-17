#!/usr/bin/env python3
"""Streamlit app: research a topic, draft an email, approve it, send it.

    uv run streamlit run app.py

The LangGraph workflow pauses at its `human_review` node. That pause is what the
"Approve & send" / "Request changes" buttons below resume.
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

import streamlit as st
from langgraph.types import Command

from agent import DEFAULT_MAX_REVISIONS, NODE_LABELS, build_graph, initial_state
from agent.config import MISSING_KEY_HELP, ConfigError, get_settings
from agent.sender import DRY_RUN_MESSAGE

PHASE_IDLE = "idle"
PHASE_REVIEW = "review"
PHASE_DONE = "done"

SESSION_KEYS = ("graph", "config", "phase", "state", "log", "error")


# Session plumbing
def init_session() -> None:
    """Create the graph once per browser session.

    The graph holds an in-memory checkpointer, and `thread_id` identifies this
    session's run inside it - together they let the workflow survive the script
    reruns that every Streamlit interaction triggers.
    """
    if "graph" in st.session_state:
        return

    st.session_state.graph = build_graph()
    st.session_state.config = {"configurable": {"thread_id": f"email-{uuid4().hex[:12]}"}}
    st.session_state.phase = PHASE_IDLE
    st.session_state.state = {}
    st.session_state.log = []
    st.session_state.error = ""


def reset_session() -> None:
    """Throw the current run away so a new topic can be started."""
    for key in SESSION_KEYS:
        st.session_state.pop(key, None)


def advance(payload: Any) -> None:
    """Run the graph until it pauses or finishes, then update the session.

    Args:
        payload: the initial state to start, or a ``Command`` to resume.
    """
    graph = st.session_state.graph
    config = st.session_state.config

    try:
        for chunk in graph.stream(payload, config, stream_mode="updates"):
            for node in chunk:
                # LangGraph emits `__interrupt__` when it pauses; not a node.
                if not node.startswith("__"):
                    st.session_state.log.append(NODE_LABELS.get(node, node))
    except ConfigError as exc:
        st.session_state.error = str(exc)
        return
    except Exception as exc:  # noqa: BLE001 - surface anything to the user
        st.session_state.error = f"{type(exc).__name__}: {exc}"
        return

    # The checkpointer holds the authoritative merged state.
    snapshot = graph.get_state(config)
    st.session_state.error = ""
    st.session_state.state = dict(snapshot.values)
    st.session_state.phase = PHASE_REVIEW if snapshot.interrupts else PHASE_DONE



# Sidebar
def render_sidebar() -> None:
    """Show configuration status and the reset button."""
    settings = get_settings()

    with st.sidebar:
        st.header("⚙️ Status")

        if settings.llm_ready:
            st.success(f"Model: `{settings.groq_model}`")
        else:
            st.error("GROQ_API_KEY is missing")

        if settings.email_ready:
            st.success(f"Sending as `{settings.email_from}`")
        else:
            st.warning("Dry run: no email will actually be sent")

        if st.session_state.log:
            st.divider()
            st.subheader("📋 Progress")
            for entry in st.session_state.log:
                st.caption(entry)

        if st.session_state.phase != PHASE_IDLE:
            st.divider()
            if st.button("🔄 Start over"):
                reset_session()
                st.rerun()


# Step 1 - the topic form
def render_form() -> None:
    """Collect the topic and recipient, then run research and drafting."""
    settings = get_settings()

    st.subheader("1. What should the email be about?")

    with st.form("topic_form"):
        topic = st.text_input(
            "Topic to research",
            placeholder="e.g., Recent breakthroughs in solid-state batteries",
        )
        recipient = st.text_input(
            "Send to",
            placeholder="someone@example.com",
        )
        max_revisions = st.slider(
            "Revisions allowed before giving up",
            min_value=1,
            max_value=5,
            value=DEFAULT_MAX_REVISIONS,
        )
        submitted = st.form_submit_button("🚀 Research & draft", type="primary")

    if not submitted:
        return

    if not settings.llm_ready:
        st.error(MISSING_KEY_HELP)
        return

    if not topic.strip():
        st.warning("Enter a topic first.")
        return

    if "@" not in recipient:
        st.warning("Enter a valid recipient email address.")
        return

    with st.spinner("Searching the web, extracting facts and writing a draft..."):
        advance(initial_state(topic, recipient, max_revisions))

    st.rerun()


# Step 2 - the human-in-the-loop review
def render_review() -> None:
    """Show the draft and let the human approve it or ask for changes."""
    state = st.session_state.state
    revision = state.get("revision_count", 0)
    allowed = state.get("max_revisions", DEFAULT_MAX_REVISIONS)
    last_chance = revision >= allowed

    st.subheader("2. Review before sending")
    st.caption(f"Revision {revision} of {allowed} allowed")

    with st.container(border=True):
        st.markdown(f"**To:** {state.get('recipient', '')}")
        st.markdown(f"**Subject:** {state.get('email_subject', '')}")
        st.divider()
        st.write(state.get("email_draft", ""))

    if last_chance:
        st.warning(
            "You have used every allowed revision. Requesting changes now will "
            "stop the workflow without sending."
        )

    with st.form("review_form"):
        feedback = st.text_area(
            "What should change?",
            placeholder="e.g., Make it shorter and drop the third paragraph",
            help="Only needed when requesting changes.",
        )
        approve_col, reject_col = st.columns(2)
        approved = approve_col.form_submit_button("✅ Approve & send", type="primary")
        rejected = reject_col.form_submit_button("✏️ Request changes")

    if approved:
        with st.spinner("Sending..."):
            advance(Command(resume={"approved": True, "feedback": ""}))
        st.rerun()

    if rejected:
        if not feedback.strip():
            st.warning("Describe what should change first.")
            return
        with st.spinner("Rewriting the draft..."):
            advance(Command(resume={"approved": False, "feedback": feedback.strip()}))
        st.rerun()

    render_research_details()


# Step 3 - the outcome
def render_result() -> None:
    """Report what happened to the email."""
    state = st.session_state.state
    send_error = state.get("send_error", "")

    st.subheader("3. Result")

    if state.get("email_sent"):
        st.success(f"Email delivered to {state.get('recipient', '')}")
    elif send_error == DRY_RUN_MESSAGE:
        st.info(
            "Dry run - the draft was approved but not delivered. "
            "Add `RESEND_API_KEY` to `.env` and restart to send for real."
        )
    elif not state.get("approved"):
        st.warning(send_error or "Stopped without sending.")
    else:
        st.error(f"Sending failed: {send_error}")

    with st.container(border=True):
        st.markdown(f"**To:** {state.get('recipient', '')}")
        st.markdown(f"**Subject:** {state.get('email_subject', '')}")
        st.divider()
        st.write(state.get("email_draft", ""))

    st.download_button(
        "📥 Download the email",
        data=f"Subject: {state.get('email_subject', '')}\n\n{state.get('email_draft', '')}",
        file_name="email.txt",
        mime="text/plain",
    )

    render_research_details()

    if st.button("🔄 Start another email"):
        reset_session()
        st.rerun()


# Shared detail panels
def render_research_details() -> None:
    """Expanders showing the research, the revision trail and any warnings."""
    state = st.session_state.state

    facts = state.get("facts", [])
    sources = state.get("research_results", [])
    drafts = state.get("draft_history", [])
    feedback_history = state.get("feedback_history", [])
    warnings = state.get("warnings", [])

    st.divider()

    with st.expander(f"🧠 Facts used ({len(facts)})"):
        for fact in facts:
            st.markdown(f"- {fact}")

    with st.expander(f"🔎 Sources ({len(sources)})"):
        for source in sources:
            st.text(source)
            st.divider()

    if feedback_history:
        with st.expander(f"✏️ Your feedback ({len(feedback_history)})"):
            for index, entry in enumerate(feedback_history, 1):
                st.markdown(f"**Round {index}:** {entry}")

    if len(drafts) > 1:
        with st.expander(f"📝 Draft history ({len(drafts)})"):
            for index, draft in enumerate(drafts, 1):
                st.markdown(f"**Draft {index}**")
                st.text(draft)
                st.divider()

    if warnings:
        with st.expander(f"⚠️ Warnings ({len(warnings)})"):
            for warning in warnings:
                st.warning(warning)


# Entry point
def main() -> None:
    """Render the app for the current phase."""
    st.set_page_config(page_title="Research → Email Agent", page_icon="📧")

    init_session()

    st.title("📧 Research → Email Agent")
    st.caption("LangGraph researches a topic, drafts an email, and waits for your approval.")

    render_sidebar()

    if st.session_state.error:
        st.error(st.session_state.error)

    phase = st.session_state.phase
    if phase == PHASE_IDLE:
        render_form()
    elif phase == PHASE_REVIEW:
        render_review()
    else:
        render_result()


main()
