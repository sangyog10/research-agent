"""Tiny terminal formatting helpers.

Keeps the ``print("=" * 60)`` noise out of the graph nodes.
"""

from __future__ import annotations

RULE_WIDTH = 60


def rule(char: str = "=") -> None:
    """Print a horizontal rule."""
    print(char * RULE_WIDTH)


def header(title: str) -> None:
    """Print a blank line and a titled banner."""
    print()
    rule()
    print(title)
    rule()


def info(message: str) -> None:
    """Print a plain message."""
    print(message)


def step(message: str) -> None:
    """Print an indented sub-step."""
    print(f"   {message}")


def ok(message: str) -> None:
    """Print a success message."""
    print(f"✅ {message}")


def warn(message: str) -> None:
    """Print a warning."""
    print(f"⚠️  {message}")


def error(message: str) -> None:
    """Print an error."""
    print(f"❌ {message}")


def block(text: str) -> None:
    """Print text fenced by dashed rules."""
    rule("-")
    print(text)
    rule("-")
