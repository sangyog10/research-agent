"""Human-in-the-loop research-to-email agent."""

from email_agent.graph import build_email_agent
from email_agent.runner import (
    is_waiting_for_human,
    new_config,
    resume_workflow,
    start_workflow,
)
from email_agent.state import (
    DEFAULT_MAX_REVISIONS,
    EmailAgentState,
    initial_state,
)

__all__ = [
    "DEFAULT_MAX_REVISIONS",
    "EmailAgentState",
    "build_email_agent",
    "initial_state",
    "is_waiting_for_human",
    "new_config",
    "resume_workflow",
    "start_workflow",
]
