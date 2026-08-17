"""Wiring for the research agent graph.

START -> input -> questions -> search -> analyze -> router
                      ^                               |
                      |          "search"             |
                      +-------------------------------+
                                                      | "report"
                                                      v
                                                    report -> END
"""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from research_agent.nodes import (
    analyzer_node,
    input_processor_node,
    question_generator_node,
    report_generator_node,
    search_tool_node,
    should_continue_research,
)
from research_agent.state import ResearchState

# Rough progress weight per node, used to drive a progress bar in the UI.
NODE_PROGRESS: dict[str, float] = {
    "input": 0.10,
    "questions": 0.30,
    "search": 0.55,
    "analyze": 0.80,
    "report": 1.00,
}


def build_research_agent() -> CompiledStateGraph:
    """Compile the research workflow.

    No checkpointer is needed: this graph never interrupts.
    """
    workflow = StateGraph(ResearchState)

    workflow.add_node("input", input_processor_node)
    workflow.add_node("questions", question_generator_node)
    workflow.add_node("search", search_tool_node)
    workflow.add_node("analyze", analyzer_node)
    workflow.add_node("report", report_generator_node)

    workflow.add_edge(START, "input")
    workflow.add_edge("input", "questions")
    workflow.add_edge("questions", "search")
    workflow.add_edge("search", "analyze")

    # Looping back to "questions" widens the research with new angles.
    workflow.add_conditional_edges(
        "analyze",
        should_continue_research,
        {"search": "questions", "report": "report"},
    )

    workflow.add_edge("report", END)

    return workflow.compile()
