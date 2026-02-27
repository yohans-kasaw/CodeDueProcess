"""Shared type aliases for agent nodes."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from src.codedueprocess.state import AgentState

StateUpdate = dict[str, Any]
StateNode = Callable[[AgentState], StateUpdate]
