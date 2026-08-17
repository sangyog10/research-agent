"""Prompt templates.

Kept apart from the graph so wording can change without touching logic.
"""

from __future__ import annotations

FACT_EXTRACTION_PROMPT = """You are a research assistant.

Topic:
{topic}

Research results:
{research}

Extract the most useful and reliable facts.

Rules:
- Extract 5 to 8 important facts.
- Do not invent information.
- Prefer facts supported by multiple sources.
- Keep each fact concise.
- Return ONLY a numbered list.
"""

DRAFT_PROMPT = """Write a professional email based on the research below.

Topic:
{topic}

Facts:
{facts}

Requirements:
- Write a concise professional email.
- Do not invent facts.
- Do not mention that an AI wrote the email.
- Include a clear subject line.
- Keep the body reasonably short.
- Use the facts naturally.

Return exactly this format:

SUBJECT: <subject>

BODY:
<email body>
"""

REVISION_PROMPT = """Revise the following email.

Original topic:
{topic}

Current subject:
{subject}

Current email:
{body}

Human feedback:
{feedback}

Important:
- Follow the human feedback.
- Keep the factual information accurate.
- Do not invent information.
- Keep the email professional.
- Keep it concise.

Return exactly this format:

SUBJECT: <new subject>

BODY:
<new email body>
"""
