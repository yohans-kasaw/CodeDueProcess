"""Tests for agent state helper functions."""

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from codedueprocess.agent import (
    INSUFFICIENT_RESPONSE_SIGNALS,
    MAX_ANALYST_RETRY_ATTEMPTS,
    MAX_STEPS,
    _extract_worker_response,
    _heuristic_route,
    _is_insufficient_response,
    _latest_tool_output,
    _message_preview,
    _tool_activity_counts,
    _with_retry_prompt,
)


class TestMessagePreview:
    """Tests for _message_preview helper."""

    def test_short_message_returns_unchanged(self):
        """Short messages under limit should return as-is."""
        message = AIMessage(content="Hello world")
        result = _message_preview(message, limit=100)
        assert result == "Hello world"

    def test_long_message_gets_truncated(self):
        """Long messages should be truncated with ellipsis."""
        message = AIMessage(content="A" * 200)
        result = _message_preview(message, limit=100)
        assert len(result) <= 103  # 100 + "..."
        assert result.endswith("...")

    def test_multiline_message_gets_single_line(self):
        """Multiline messages should be converted to single line."""
        message = AIMessage(content="Line 1\nLine 2\nLine 3")
        result = _message_preview(message)
        assert "\n" not in result
        assert "Line 1 Line 2 Line 3" in result

    def test_handles_non_string_content(self):
        """Should handle non-string content gracefully."""
        message = AIMessage(content=["item1", "item2"])
        result = _message_preview(message)
        assert isinstance(result, str)


class TestExtractWorkerResponse:
    """Tests for _extract_worker_response helper."""

    def test_extracts_last_non_empty_message(self):
        """Should return the last non-empty text message."""
        messages = [
            HumanMessage(content="Query"),
            AIMessage(content="Response 1"),
            AIMessage(content="Response 2"),
        ]
        result = _extract_worker_response(messages)
        assert result == "Response 2"

    def test_skips_empty_strings(self):
        """Should skip empty string messages."""
        messages = [
            AIMessage(content="First"),
            AIMessage(content="   "),
            AIMessage(content="Second"),
        ]
        result = _extract_worker_response(messages)
        assert result == "Second"

    def test_returns_none_for_no_valid_messages(self):
        """Should return None when no valid text found."""
        messages = [
            AIMessage(content=""),
            ToolMessage(content="", tool_call_id="1"),
        ]
        result = _extract_worker_response(messages)
        assert result is None

    def test_handles_empty_list(self):
        """Should return None for empty message list."""
        result = _extract_worker_response([])
        assert result is None


class TestToolActivityCounts:
    """Tests for _tool_activity_counts helper."""

    def test_counts_tool_calls_and_results(self):
        """Should correctly count tool calls and results."""
        messages = [
            AIMessage(
                content="",
                tool_calls=[
                    {"id": "1", "name": "search_web", "args": {"query": "test"}},
                    {"id": "2", "name": "get_weather", "args": {"city": "Paris"}},
                ],
            ),
            ToolMessage(content="Result 1", tool_call_id="1"),
            ToolMessage(content="Result 2", tool_call_id="2"),
        ]
        requested, returned = _tool_activity_counts(messages)
        assert requested == 2
        assert returned == 2

    def test_no_tool_calls_returns_zeros(self):
        """Should return zeros when no tool activity."""
        messages = [
            HumanMessage(content="Hello"),
            AIMessage(content="Hi"),
        ]
        requested, returned = _tool_activity_counts(messages)
        assert requested == 0
        assert returned == 0

    def test_counts_only_valid_tool_calls(self):
        """Should only count valid tool_calls list."""
        messages = [
            AIMessage(content="No tools here"),  # No tool_calls attribute or None
        ]
        requested, returned = _tool_activity_counts(messages)
        assert requested == 0
        assert returned == 0


class TestIsInsufficientResponse:
    """Tests for _is_insufficient_response helper."""

    @pytest.mark.parametrize("signal", INSUFFICIENT_RESPONSE_SIGNALS)
    def test_detects_all_insufficient_signals(self, signal):
        """Should detect all defined insufficient response signals."""
        assert _is_insufficient_response(signal) is True

    def test_case_insensitive_detection(self):
        """Should detect signals regardless of case."""
        assert _is_insufficient_response("SORRY, NEED MORE STEPS") is True
        assert _is_insufficient_response("Sorry, Need More Steps") is True

    def test_normal_response_returns_false(self):
        """Normal responses should return False."""
        assert _is_insufficient_response("Here is your answer") is False
        assert _is_insufficient_response("The result is 42") is False

    def test_empty_string_returns_false(self):
        """Empty string should return False."""
        assert _is_insufficient_response("") is False


class TestLatestToolOutput:
    """Tests for _latest_tool_output helper."""

    def test_extracts_latest_tool_message(self):
        """Should extract content from most recent ToolMessage."""
        messages = [
            ToolMessage(content="First result", tool_call_id="1"),
            AIMessage(content="Response"),
            ToolMessage(content="Latest result", tool_call_id="2"),
        ]
        result = _latest_tool_output(messages)
        assert result == "Latest result"

    def test_returns_none_when_no_tool_messages(self):
        """Should return None when no ToolMessages exist."""
        messages = [
            HumanMessage(content="Query"),
            AIMessage(content="Response"),
        ]
        result = _latest_tool_output(messages)
        assert result is None

    def test_skips_empty_tool_content(self):
        """Should skip ToolMessages with empty content."""
        messages = [
            ToolMessage(content="   ", tool_call_id="1"),
            ToolMessage(content="Valid result", tool_call_id="2"),
        ]
        result = _latest_tool_output(messages)
        assert result == "Valid result"


class TestWithRetryPrompt:
    """Tests for _with_retry_prompt helper."""

    def test_adds_retry_message_to_state(self):
        """Should add a HumanMessage with retry prompt to state."""
        state = {"messages": [HumanMessage(content="Original")], "step": 0}
        result = _with_retry_prompt(state, "Please retry")

        assert len(result["messages"]) == 2
        assert result["messages"][-1].content == "Please retry"
        assert isinstance(result["messages"][-1], HumanMessage)

    def test_preserves_other_state_fields(self):
        """Should preserve other state fields."""
        state = {"messages": [], "step": 5, "custom": "value"}
        result = _with_retry_prompt(state, "Retry")

        assert result["step"] == 5
        assert result["custom"] == "value"

    def test_creates_new_list_not_modify_original(self):
        """Should create new message list without modifying original."""
        original_messages = [HumanMessage(content="Original")]
        state = {"messages": original_messages}

        result = _with_retry_prompt(state, "Retry")

        assert len(original_messages) == 1  # Original unchanged
        assert len(result["messages"]) == 2


class TestHeuristicRoute:
    """Tests for _heuristic_route helper."""

    def test_routes_researcher_to_analyst_on_tool_limit(self):
        """Should route Researcher to Analyst when indicating tool limits."""
        state = {
            "messages": [
                AIMessage(
                    content="I don't have a tool for that",
                    name="Researcher",
                )
            ]
        }
        result = _heuristic_route(state)
        assert result == "Analyst"

    def test_routes_analyst_to_finish_on_tool_limit(self):
        """Should route Analyst to FINISH when indicating tool limits."""
        state = {
            "messages": [
                AIMessage(
                    content="I don't have a tool for that",
                    name="Analyst",
                )
            ]
        }
        result = _heuristic_route(state)
        assert result == "FINISH"

    def test_detects_various_no_tool_signals(self):
        """Should detect various 'no tool' signals."""
        signals = [
            "I cannot fulfill that request",
            "I do not have that capability",
            "I don't have a tool for this",
            "Tool is not available",
            "Please clarify your request",
        ]

        for signal in signals:
            state = {"messages": [AIMessage(content=signal, name="Researcher")]}
            result = _heuristic_route(state)
            assert result == "Analyst", f"Failed for signal: {signal}"

    def test_returns_none_for_normal_response(self):
        """Should return None for normal responses."""
        state = {
            "messages": [AIMessage(content="Here is the result", name="Researcher")]
        }
        result = _heuristic_route(state)
        assert result is None

    def test_returns_none_for_empty_messages(self):
        """Should return None for empty message list."""
        state = {"messages": []}
        result = _heuristic_route(state)
        assert result is None

    def test_returns_none_for_non_ai_message(self):
        """Should return None when last message is not AIMessage."""
        state = {"messages": [HumanMessage(content="Query")]}
        result = _heuristic_route(state)
        assert result is None


class TestConstants:
    """Tests for module constants."""

    def test_max_steps_is_positive(self):
        """MAX_STEPS should be a positive integer."""
        assert isinstance(MAX_STEPS, int)
        assert MAX_STEPS > 0

    def test_retry_attempts_is_non_negative(self):
        """MAX_ANALYST_RETRY_ATTEMPTS should be non-negative."""
        assert isinstance(MAX_ANALYST_RETRY_ATTEMPTS, int)
        assert MAX_ANALYST_RETRY_ATTEMPTS >= 0

    def test_insufficient_signals_is_tuple(self):
        """INSUFFICIENT_RESPONSE_SIGNALS should be a tuple of strings."""
        assert isinstance(INSUFFICIENT_RESPONSE_SIGNALS, tuple)
        assert len(INSUFFICIENT_RESPONSE_SIGNALS) > 0
        assert all(isinstance(s, str) for s in INSUFFICIENT_RESPONSE_SIGNALS)
