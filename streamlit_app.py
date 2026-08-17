#!/usr/bin/env python3
"""Entry point for the Streamlit research assistant.

    uv run streamlit run streamlit_app.py

Note: this file must NOT be named `streamlit.py`, or `import streamlit` would
resolve to itself instead of the real package.
"""

from __future__ import annotations

from langgraph_capstone.ui import main

main()
