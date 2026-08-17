"""Interactive terminal front-end for the email agent."""

from __future__ import annotations

import argparse
from typing import Any

from langgraph_capstone import console
from langgraph_capstone.config import ConfigError, get_settings
from langgraph_capstone.email_agent import (
    DEFAULT_MAX_REVISIONS,
    build_email_agent,
    is_waiting_for_human,
    resume_workflow,
    start_workflow,
)
from langgraph_capstone.llm import get_llm

YES = {"y", "yes"}
NO = {"n", "no"}
DEFAULT_FEEDBACK = "Improve the email and make it more professional."


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="email-agent",
        description="Research a topic, draft an email, and send it after your approval.",
    )
    parser.add_argument("--topic", help="Topic to research (prompted if omitted).")
    parser.add_argument("--to", dest="recipient", help="Recipient email (prompted if omitted).")
    parser.add_argument(
        "--max-revisions",
        type=int,
        default=DEFAULT_MAX_REVISIONS,
        help=f"How many rejections to allow before giving up (default: {DEFAULT_MAX_REVISIONS}).",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Approve the first draft automatically (non-interactive demo).",
    )
    return parser.parse_args(argv)


def _prompt(label: str, value: str | None) -> str:
    """Return ``value`` if given, otherwise ask the user for it."""
    return (value or input(label)).strip()


def display_final_result(result: dict[str, Any]) -> None:
    """Print a summary of the finished run."""
    console.header("📊 FINAL RESULT")

    console.info(f"Topic:      {result.get('topic', '')}")
    console.info(f"Revisions:  {result.get('revision_count', 0)}")
    console.info(f"Approved:   {result.get('approved', False)}")
    console.info(f"Email sent: {result.get('email_sent', False)}")

    if result.get("send_error"):
        console.info(f"Note:       {result['send_error']}")

    print("\nFinal Email:")
    console.rule("-")
    console.info(f"To:      {result.get('recipient', '')}")
    console.info(f"Subject: {result.get('email_subject', '')}")
    console.rule("-")
    print(result.get("email_draft", ""))
    console.rule("-")


def review_loop(app: Any, config: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    """Keep approving/rejecting until the graph reaches the end."""
    while is_waiting_for_human(app, config):
        console.header("👤 YOUR DECISION")

        choice = input("\nApprove email? [y/n]: ").strip().lower()

        if choice in YES:
            console.ok("You approved the email.")
            return resume_workflow(app, config, approved=True)

        if choice in NO:
            feedback = input("\nWhat should be changed? ").strip() or DEFAULT_FEEDBACK
            console.info("\n🔄 Sending feedback to the revision node...")
            result = resume_workflow(app, config, approved=False, feedback=feedback)
            continue

        console.warn("Please enter y or n.")

    return result


def main(argv: list[str] | None = None) -> int:
    """Entry point. Returns a process exit code."""
    args = _parse_args(argv)

    console.header("📧 RESEARCH → EMAIL HUMAN-IN-THE-LOOP AGENT")

    # Fail fast with a helpful message instead of a stack trace mid-workflow.
    try:
        get_llm()
    except ConfigError as exc:
        console.error(str(exc))
        return 1

    if not get_settings().email_ready:
        console.warn("RESEND_API_KEY is not set - running in dry-run mode (no email is sent).")

    topic = _prompt("\nEnter a topic to research: ", args.topic)
    if not topic:
        console.error("Topic cannot be empty.")
        return 1

    recipient = _prompt("Enter recipient email: ", args.recipient)
    if not recipient:
        console.error("Recipient cannot be empty.")
        return 1

    app = build_email_agent()

    try:
        result, config = start_workflow(
            app,
            topic,
            recipient,
            max_revisions=args.max_revisions,
        )

        if args.yes:
            console.ok("Auto-approving the first draft (--yes).")
            result = resume_workflow(app, config, approved=True)
        else:
            result = review_loop(app, config, result)

    except KeyboardInterrupt:
        console.warn("\nWorkflow cancelled by user.")
        return 130
    except Exception as exc:  # noqa: BLE001 - last resort for a CLI
        console.error(f"Unexpected error: {type(exc).__name__}: {exc}")
        return 1

    display_final_result(result)
    return 0
