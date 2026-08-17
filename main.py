#!/usr/bin/env python3
"""Entry point for the human-in-the-loop research-to-email agent.

uv run main.py
uv run main.py --topic "AI regulation in the EU" --to you@example.com
"""

from __future__ import annotations

import sys

from cli import main

if __name__ == "__main__":
    sys.exit(main())
