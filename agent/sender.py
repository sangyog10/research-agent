"""Email delivery through Resend.

Nothing else imports :mod:`resend`, so swapping providers only touches this file.
"""

from __future__ import annotations

import html
from dataclasses import dataclass

import resend

from agent.config import get_settings

DRY_RUN_MESSAGE = "RESEND_API_KEY is not set - dry run, no email was delivered."


@dataclass(frozen=True)
class SendOutcome:
    """Result of an attempted send."""

    sent: bool
    error: str = ""
    dry_run: bool = False


def to_html(body: str) -> str:
    """Convert a plain-text body into escaped HTML paragraphs."""
    paragraphs = [block.strip() for block in body.split("\n\n") if block.strip()]
    return "".join(
        "<p>" + html.escape(block).replace("\n", "<br />") + "</p>" for block in paragraphs
    )


def send_email(recipient: str, subject: str, body: str) -> SendOutcome:
    """Send one email.

    Returns an outcome instead of raising, so the graph can record the failure
    in state and still finish cleanly.
    """
    settings = get_settings()

    if not settings.email_ready:
        return SendOutcome(sent=False, error=DRY_RUN_MESSAGE, dry_run=True)

    if not recipient:
        return SendOutcome(sent=False, error="No recipient address was provided.")

    # The Resend SDK reads its credential from this module-level attribute.
    resend.api_key = settings.resend_api_key

    try:
        resend.Emails.send(
            {
                "from": settings.email_from,
                "to": [recipient],
                "subject": subject or "(no subject)",
                "html": to_html(body),
                "text": body,
            }
        )
    except Exception as exc:  
        return SendOutcome(sent=False, error=f"{type(exc).__name__}: {exc}")

    return SendOutcome(sent=True)
