"""Shared Rich console configuration."""

from __future__ import annotations

from datetime import datetime

from rich.console import Console
from rich.theme import Theme

_THEME = Theme(
    {
        "layer": "bold cyan",
        "agent": "bold bright_white",
        "ok": "bold green",
        "warn": "bold yellow",
        "error": "bold red",
        "metric": "bold magenta",
        "dimmed": "dim white",
    }
)

console = Console(theme=_THEME)


def now_timestamp() -> str:
    """Return a HH:MM:SS timestamp string for event lines."""
    return datetime.now().strftime("%H:%M:%S")
