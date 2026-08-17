"""Wiring for the email agent graph.

START -> research -> extract_facts -> draft_email -> human_review
                                                          |
                                    +---------------------+---------------------+
                                    |                     |                     |
                                 approve             reject (<= max)      reject (> max)
                                    |                     |                     |
                                    v                     v                     v
                                  send                 revise                 abort
                                    |                     |                     |
                                    v                     +---> human_review    v
                                   END                                         END
"""

from __future__ import annotations

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from langgraph_capstone.email_agent.nodes import (
    abort_node,
    draft_email_node,
    extract_facts_node,
    human_review_node,
    research_node,
    review_router,
    revise_email_node,
    send_email_node,
)
from langgraph_capstone.email_agent.state import EmailAgentState


def build_email_agent(checkpointer: MemorySaver | None = None) -> CompiledStateGraph:
    """Compile the email workflow.

    A checkpointer is mandatory for ``interrupt`` / resume to work, so one is
    created automatically when the caller does not supply it.
    """
    workflow = StateGraph(EmailAgentState)

    workflow.add_node("research", research_node)
    workflow.add_node("extract_facts", extract_facts_node)
    workflow.add_node("draft_email", draft_email_node)
    workflow.add_node("human_review", human_review_node)
    workflow.add_node("revise", revise_email_node)
    workflow.add_node("send", send_email_node)
    workflow.add_node("abort", abort_node)

    workflow.add_edge(START, "research")
    workflow.add_edge("research", "extract_facts")
    workflow.add_edge("extract_facts", "draft_email")
    workflow.add_edge("draft_email", "human_review")

    workflow.add_conditional_edges(
        "human_review",
        review_router,
        {"send": "send", "revise": "revise", "abort": "abort"},
    )

    # A revised draft always goes back to the human.
    workflow.add_edge("revise", "human_review")
    workflow.add_edge("send", END)
    workflow.add_edge("abort", END)

    return workflow.compile(checkpointer=checkpointer or MemorySaver())
