"""Research → email agent with a human approval step.

The graph is deliberately UI-free; :mod:`app` (Streamlit) drives it.
"""

from agent.graph import NODE_LABELS, build_graph
from agent.state import DEFAULT_MAX_REVISIONS, EmailAgentState, initial_state

__all__ = [
    "DEFAULT_MAX_REVISIONS",
    "NODE_LABELS",
    "EmailAgentState",
    "build_graph",
    "initial_state",
]
