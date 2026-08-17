"""Streamlit front-end for the research agent.

Run it with::

    uv run streamlit run streamlit_app.py
"""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

import streamlit as st
from langgraph.graph.state import CompiledStateGraph

from config import ConfigError, get_settings
from research_agent import (
    DEFAULT_MAX_ITERATIONS,
    DEFAULT_QUALITY_THRESHOLD,
    NODE_LABELS,
    NODE_PROGRESS,
    build_research_agent,
    initial_state,
)

EXAMPLE_TOPICS = [
    "",
    "Benefits of LangGraph for AI agents",
    "State management in workflow systems",
    "Building production AI applications",
    "Graph-based vs linear AI workflows",
    "Tool integration in language models",
]

WORKFLOW_DIAGRAM = """```mermaid
graph TD
    Start([Start]) --> Input[📥 Input Processor]
    Input --> Questions[❓ Question Generator]
    Questions --> Search[🔍 Search Tool]
    Search --> Analyze[🔬 Analyzer]
    Analyze --> Router{🚦 Continue?}
    Router -->|more research| Questions
    Router -->|good enough| Report[📝 Report Generator]
    Report --> End([End])
```"""

HOW_IT_WORKS = """
1. **Input processing** - sharpens your topic into a specific research focus.
2. **Question generation** - writes searchable questions, skipping ones already covered.
3. **Search tool** - queries DuckDuckGo for each new question.
4. **Analysis** - extracts key findings and scores research quality.
5. **Routing** - loops back for another round or moves on.
6. **Report generation** - compiles a markdown report with metadata.
"""

LANGGRAPH_CONCEPTS = """
- **StateGraph** - a typed dict carried through every node.
- **Nodes** - plain functions returning only the keys they change.
- **Edges** - the fixed happy path.
- **Conditional routing** - `should_continue_research` picks the next hop.
- **Loops** - `analyze → questions` widens the research.
- **Streaming** - `graph.stream(..., stream_mode="updates")` drives live progress.
"""


@st.cache_resource
def get_graph() -> CompiledStateGraph:
    """Compile the graph once per server process."""
    return build_research_agent()


def run_research(
    graph: CompiledStateGraph,
    state: dict[str, Any],
    on_node: Callable[[str, dict[str, Any]], None],
) -> dict[str, Any]:
    """Stream the graph and report real progress after each node finishes.

    Args:
        graph: The compiled research graph.
        state: The initial state.
        on_node: Called with ``(node_name, accumulated_state)`` per completed node.

    Returns:
        The accumulated final state.
    """
    final: dict[str, Any] = dict(state)

    for chunk in graph.stream(state, stream_mode="updates"):
        for node, update in chunk.items():
            if isinstance(update, dict):
                final.update(update)
            on_node(node, final)

    return final


def _slugify(text: str) -> str:
    """Make a topic safe to use in a filename."""
    slug = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
    return slug[:60] or "report"


def _sidebar() -> tuple[int, float]:
    """Render the sidebar controls and return the chosen settings."""
    with st.sidebar:
        st.header("⚙️ Configuration")

        max_iterations = st.slider(
            "Max iterations",
            min_value=1,
            max_value=5,
            value=DEFAULT_MAX_ITERATIONS,
            help="How many research rounds the graph may run.",
        )

        quality_threshold = st.slider(
            "Quality threshold",
            min_value=0.2,
            max_value=1.0,
            value=DEFAULT_QUALITY_THRESHOLD,
            step=0.1,
            help="Stop early once the quality score reaches this value.",
        )

        st.divider()

        st.subheader("📚 Example topics")
        st.selectbox(
            "Load an example",
            EXAMPLE_TOPICS,
            key="example_topic",
            format_func=lambda item: item or "— none —",
        )

        st.divider()
        settings = get_settings()
        if settings.llm_ready:
            st.success(f"Model: `{settings.groq_model}`")
        else:
            st.error("GROQ_API_KEY is missing.")

    return max_iterations, quality_threshold


def _render_results(result: dict[str, Any], topic: str) -> None:
    """Show the finished report and all supporting data."""
    st.divider()
    st.subheader("📊 Research results")

    if result.get("errors"):
        with st.expander(f"⚠️ {len(result['errors'])} warning(s) during the run"):
            for message in result["errors"]:
                st.warning(message)

    tabs = st.tabs(["📝 Report", "❓ Questions", "🔍 Sources", "💡 Findings", "📈 Metadata"])

    with tabs[0]:
        st.markdown(result.get("final_report", "_No report was generated._"))
        st.download_button(
            label="📥 Download report",
            data=result.get("final_report", ""),
            file_name=f"research_{_slugify(topic)}.md",
            mime="text/markdown",
        )

    with tabs[1]:
        st.caption(f"Refined focus: {result.get('topic', '')}")
        for index, question in enumerate(result.get("research_questions", []), 1):
            st.write(f"{index}. {question}")

    with tabs[2]:
        sources = result.get("search_results", [])
        st.caption(f"{len(sources)} snippet(s) collected")
        for index, snippet in enumerate(sources, 1):
            with st.expander(f"Source {index}: {snippet[:70]}"):
                st.write(snippet)

    with tabs[3]:
        for index, finding in enumerate(result.get("key_findings", []), 1):
            st.info(f"**Finding {index}:** {finding}")

    with tabs[4]:
        left, middle, right = st.columns(3)
        with left:
            st.metric("Iterations", result.get("iteration", 0))
            st.metric("Questions", len(result.get("research_questions", [])))
        with middle:
            st.metric("Sources", len(result.get("search_results", [])))
            st.metric("Findings", len(result.get("key_findings", [])))
        with right:
            st.metric("Quality score", f"{result.get('quality_score', 0.0):.2f}")
            st.metric("Status", result.get("status", "unknown"))

        with st.expander("View complete state"):
            st.json({key: value for key, value in result.items() if key != "final_report"})


def _render_sidebar_docs() -> None:
    """Render the explanatory panels next to the form."""
    st.subheader("🗺️ Workflow")
    st.markdown(WORKFLOW_DIAGRAM)

    with st.expander("ℹ️ How it works"):
        st.markdown(HOW_IT_WORKS)

    with st.expander("🎓 LangGraph concepts"):
        st.markdown(LANGGRAPH_CONCEPTS)


def main() -> None:
    """Streamlit entry point."""
    st.set_page_config(
        page_title="LangGraph Research Assistant",
        page_icon="🤖",
        layout="wide",
    )

    st.title("🤖 LangGraph Research Assistant")
    st.markdown("**AI-powered research using LangGraph workflow orchestration**")

    max_iterations, quality_threshold = _sidebar()

    form_column, docs_column = st.columns([2, 1])

    with docs_column:
        _render_sidebar_docs()

    with form_column:
        st.subheader("🔍 Research topic")

        with st.form("research_form"):
            topic = st.text_input(
                "Enter your research topic:",
                value=st.session_state.get("example_topic", ""),
                placeholder="e.g., Benefits of LangGraph for AI agents",
            )
            submitted = st.form_submit_button("🚀 Start research", type="primary")

        if not submitted:
            return

        if not topic.strip():
            st.warning("Please enter a topic first.")
            return

        if not get_settings().llm_ready:
            st.error("GROQ_API_KEY is not set. Copy `.env.example` to `.env` and add your key.")
            return

        state = initial_state(
            topic,
            max_iterations=max_iterations,
            quality_threshold=quality_threshold,
        )

        st.subheader("🔄 Progress")
        progress_bar = st.progress(0.0)

        with st.status("Research in progress...", expanded=True) as status:

            def on_node(node: str, _state: dict[str, Any]) -> None:
                status.write(f"✅ {NODE_LABELS.get(node, node)}")
                progress_bar.progress(NODE_PROGRESS.get(node, 0.0))

            try:
                result = run_research(get_graph(), state, on_node)
            except ConfigError as exc:
                status.update(label="Configuration error", state="error")
                st.error(str(exc))
                return
            except Exception as exc:  # noqa: BLE001 - surface anything to the user
                status.update(label="Research failed", state="error")
                st.error(f"{type(exc).__name__}: {exc}")
                return

            progress_bar.progress(1.0)
            status.update(label="Research complete!", state="complete")

        _render_results(result, topic)
