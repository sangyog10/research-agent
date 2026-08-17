"""Turn the LLM's ``SUBJECT: ... BODY: ...`` answer into structured data."""

from __future__ import annotations

import re

DEFAULT_SUBJECT = "Information Update"

# Tolerates markdown emphasis and stray spacing, e.g. `**Subject:**  Hello`.
_SUBJECT_RE = re.compile(r"^\**\s*subject\s*:\**\s*(.*)$", re.IGNORECASE)
_BODY_RE = re.compile(r"^\**\s*body\s*:\**\s*(.*)$", re.IGNORECASE)


def parse_email_draft(draft: str) -> tuple[str, str]:
    """Split a raw draft into ``(subject, body)``.

    Falls back to :data:`DEFAULT_SUBJECT` and the whole text as the body when
    the model ignores the requested format.

    >>> parse_email_draft("SUBJECT: Hi\\n\\nBODY:\\nHello there")
    ('Hi', 'Hello there')
    """
    lines = draft.splitlines()

    subject = ""
    body_parts: list[str] = []
    body_started = False

    for line in lines:
        if body_started:
            body_parts.append(line)
            continue

        subject_match = _SUBJECT_RE.match(line)
        if subject_match:
            # Keeps the first non-empty subject we saw.
            subject = subject_match.group(1).strip() or subject
            continue

        body_match = _BODY_RE.match(line)
        if body_match:
            body_started = True
            inline = body_match.group(1).strip()
            if inline:
                body_parts.append(inline)

    if body_started:
        body = "\n".join(body_parts).strip()
    else:
        # No `BODY:` marker - treat everything except the subject line as body.
        body = "\n".join(line for line in lines if not _SUBJECT_RE.match(line)).strip()

    return subject or DEFAULT_SUBJECT, body or draft.strip()
