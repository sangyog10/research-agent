"""Day 21 LangGraph capstone.

Two agents share the same core building blocks:

* :mod:`langgraph_capstone.email_agent`    - human-in-the-loop research to email (CLI)
* :mod:`langgraph_capstone.research_agent` - iterative research assistant (Streamlit)
"""

from langgraph_capstone.config import ConfigError, Settings, get_settings

__all__ = ["ConfigError", "Settings", "__version__", "get_settings"]

__version__ = "0.1.0"
