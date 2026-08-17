"""Prompt templates for the research agent."""

from __future__ import annotations

TOPIC_REFINEMENT_PROMPT = """Given this research topic: '{topic}'
Suggest a more specific research focus.
Return one single line with no preamble, quotes or explanation."""

QUESTION_PROMPT = """Generate 3 specific research questions about: {topic}

Rules:
- Questions must be searchable and factual.
- Avoid questions already covered below.
- Return only the questions, one per line, with no numbering.

Already covered:
{covered}"""

ANALYSIS_PROMPT = """Analyse these search results about '{topic}':

{results}

Extract 5 key findings.
Return only the findings, one per line, with no numbering."""

REPORT_PROMPT = """Create a comprehensive research report based on this information:

Topic: {topic}

Research Questions:
{questions}

Key Findings:
{findings}

Number of sources consulted: {source_count}

Generate a well-structured report in markdown with:
1. Executive Summary
2. Key Findings
3. Conclusion

Keep it concise but informative."""
