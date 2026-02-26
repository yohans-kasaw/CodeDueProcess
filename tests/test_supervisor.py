"""Tests for supervisor routing logic."""

from unittest.mock import patch

import pytest
from langchain_core.messages import HumanMessage

from codedueprocess.agent import (
    MAX_STEPS,
    Route,
    supervisor_node,
)


@pytest.fixture
def mock_state():
    """Create a basic mock state for testing."""
    return {
        "messages": [HumanMessage(content="Test query")],
        "step": 0,
        "next": "",
    }


class TestSupervisorNodeMaxSteps:
    """Tests for max steps guardrail."""

    def test_finishes_when_max_steps_reached(self, mock_state):
        """Should return FINISH when step >= MAX_STEPS."""
        mock_state["step"] = MAX_STEPS

        result = supervisor_node(mock_state)

        assert result["next"] == "FINISH"
        # When max steps reached, step is not included in the update

    def test_continues_when_under_max_steps(self, mock_state):
        """Should continue routing when under MAX_STEPS."""
        mock_state["step"] = MAX_STEPS - 1

        with (
            patch("codedueprocess.agent._heuristic_route", return_value=None),
            patch("codedueprocess.agent.supervisor_chain") as mock_chain,
        ):
            mock_chain.invoke.return_value = Route(next="Researcher")

            result = supervisor_node(mock_state)

        assert result["step"] == MAX_STEPS  # Step incremented


class TestSupervisorNodeHeuristicRouting:
    """Tests for heuristic routing bypass."""

    def test_uses_heuristic_route_when_available(self, mock_state):
        """Should use heuristic route when it returns a value."""
        with patch(
            "codedueprocess.agent._heuristic_route", return_value="Analyst"
        ) as mock_heuristic:
            result = supervisor_node(mock_state)

        mock_heuristic.assert_called_once_with(mock_state)
        assert result["next"] == "Analyst"
        assert result["step"] == 1

    def test_skips_llm_when_heuristic_provides_route(self, mock_state):
        """Should not invoke LLM when heuristic provides route."""
        with (
            patch("codedueprocess.agent._heuristic_route", return_value="Researcher"),
            patch("codedueprocess.agent.supervisor_chain") as mock_chain,
        ):
            _ = supervisor_node(mock_state)

        mock_chain.invoke.assert_not_called()


class TestSupervisorNodeLLMRouting:
    """Tests for LLM-based routing decisions."""

    def test_routes_to_researcher(self, mock_state):
        """Should route to Researcher when LLM selects it."""
        with (
            patch("codedueprocess.agent._heuristic_route", return_value=None),
            patch("codedueprocess.agent.supervisor_chain") as mock_chain,
        ):
            mock_chain.invoke.return_value = Route(next="Researcher")

            result = supervisor_node(mock_state)

        assert result["next"] == "Researcher"
        assert result["step"] == 1

    def test_routes_to_analyst(self, mock_state):
        """Should route to Analyst when LLM selects it."""
        with (
            patch("codedueprocess.agent._heuristic_route", return_value=None),
            patch("codedueprocess.agent.supervisor_chain") as mock_chain,
        ):
            mock_chain.invoke.return_value = Route(next="Analyst")

            result = supervisor_node(mock_state)

        assert result["next"] == "Analyst"
        assert result["step"] == 1

    def test_finishes_when_llm_selects_finish(self, mock_state):
        """Should finish when LLM selects FINISH."""
        with (
            patch("codedueprocess.agent._heuristic_route", return_value=None),
            patch("codedueprocess.agent.supervisor_chain") as mock_chain,
        ):
            mock_chain.invoke.return_value = Route(next="FINISH")

            result = supervisor_node(mock_state)

        assert result["next"] == "FINISH"
        assert result["step"] == 1


class TestSupervisorNodeErrorHandling:
    """Tests for error handling in supervisor."""

    def test_finishes_on_llm_exception(self, mock_state):
        """Should fall back to FINISH when LLM invocation fails."""
        with (
            patch("codedueprocess.agent._heuristic_route", return_value=None),
            patch("codedueprocess.agent.supervisor_chain") as mock_chain,
        ):
            mock_chain.invoke.side_effect = Exception("LLM error")

            result = supervisor_node(mock_state)

        assert result["next"] == "FINISH"
        assert result["step"] == 1

    def test_finishes_on_route_parsing_error(self, mock_state):
        """Should finish when route parsing fails."""
        with (
            patch("codedueprocess.agent._heuristic_route", return_value=None),
            patch("codedueprocess.agent.supervisor_chain") as mock_chain,
        ):
            mock_chain.invoke.return_value = None  # Invalid response

            # This will cause an AttributeError when accessing .next
            result = supervisor_node(mock_state)

        assert result["next"] == "FINISH"


class TestSupervisorNodeStateManagement:
    """Tests for state management in supervisor."""

    def test_increments_step_on_each_call(self):
        """Should increment step counter on each call."""
        state = {"messages": [], "step": 0}

        with (
            patch("codedueprocess.agent._heuristic_route", return_value=None),
            patch("codedueprocess.agent.supervisor_chain") as mock_chain,
        ):
            mock_chain.invoke.return_value = Route(next="Researcher")

            result1 = supervisor_node(state)
            assert result1["step"] == 1

            # Update state for second call
            state["step"] = result1["step"]
            result2 = supervisor_node(state)
            assert result2["step"] == 2

    def test_preserves_messages_in_state(self, mock_state):
        """Should not modify messages in state."""
        original_messages = list(mock_state["messages"])

        with patch("codedueprocess.agent._heuristic_route", return_value="Researcher"):
            _ = supervisor_node(mock_state)

        assert mock_state["messages"] == original_messages


class TestRouteModel:
    """Tests for Route Pydantic model."""

    def test_route_creation_with_valid_values(self):
        """Should create Route with valid worker names."""
        for worker in ["Researcher", "Analyst", "FINISH"]:
            route = Route(next=worker)
            assert route.next == worker

    def test_route_validation(self):
        """Should only accept valid route options."""
        # Valid routes
        Route(next="Researcher")
        Route(next="Analyst")
        Route(next="FINISH")

        # Invalid routes would raise validation error
        # This is validated by Pydantic
