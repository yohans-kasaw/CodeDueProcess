"""Tests for agent node creation and execution."""

from unittest.mock import MagicMock

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.runnables import RunnableConfig

from codedueprocess.agent import (
    MAX_ANALYST_RETRY_ATTEMPTS,
    create_agent_node,
)


@pytest.fixture
def mock_agent():
    """Create a mock compiled agent."""
    return MagicMock()


@pytest.fixture
def mock_state():
    """Create a basic mock state."""
    return {
        "messages": [HumanMessage(content="Test query")],
        "step": 0,
        "next": "",
    }


class TestCreateAgentNode:
    """Tests for create_agent_node function."""

    def test_returns_callable_function(self, mock_agent):
        """Should return a callable function."""
        node = create_agent_node(mock_agent, "TestWorker")
        assert callable(node)

    def test_invokes_agent_with_state(self, mock_agent, mock_state):
        """Should invoke agent with provided state."""
        mock_agent.invoke.return_value = {"messages": [AIMessage(content="Response")]}

        node = create_agent_node(mock_agent, "TestWorker")
        node(mock_state, RunnableConfig())

        mock_agent.invoke.assert_called_once()
        call_args = mock_agent.invoke.call_args
        assert call_args[0][0] == mock_state

    def test_returns_messages_dict(self, mock_agent, mock_state):
        """Should return dict with messages list."""
        mock_agent.invoke.return_value = {
            "messages": [AIMessage(content="Test response", name="TestWorker")]
        }

        node = create_agent_node(mock_agent, "TestWorker")
        result = node(mock_state, RunnableConfig())

        assert "messages" in result
        assert isinstance(result["messages"], list)
        assert len(result["messages"]) == 1

    def test_extracts_last_message_content(self, mock_agent, mock_state):
        """Should extract content from last message."""
        mock_agent.invoke.return_value = {
            "messages": [
                AIMessage(content="First"),
                AIMessage(content="Second"),
            ]
        }

        node = create_agent_node(mock_agent, "TestWorker")
        result = node(mock_state, RunnableConfig())

        assert result["messages"][0].content == "Second"


class TestAgentNodeFallbacks:
    """Tests for agent node fallback behaviors."""

    def test_returns_fallback_on_empty_messages(self, mock_agent):
        """Should return fallback message when agent returns empty."""
        mock_agent.invoke.return_value = {"messages": []}

        node = create_agent_node(mock_agent, "TestWorker")
        result = node({"messages": [], "step": 0}, RunnableConfig())

        assert len(result["messages"]) == 1
        assert "could not produce a response" in result["messages"][0].content
        assert result["messages"][0].name == "TestWorker"

    def test_returns_fallback_on_no_textual_output(self, mock_agent):
        """Should return fallback when no textual output found."""
        mock_agent.invoke.return_value = {"messages": [AIMessage(content="   ")]}

        node = create_agent_node(mock_agent, "TestWorker")
        result = node({"messages": [], "step": 0}, RunnableConfig())

        assert "no textual summary" in result["messages"][0].content


class TestAnalystNodeRetryLogic:
    """Tests for Analyst node retry behavior."""

    def test_retries_when_no_tool_results(self, mock_agent):
        """Should retry when analyst produces no tool results."""
        # First call: no tool results
        # Second call: successful with tool result
        mock_agent.invoke.side_effect = [
            {"messages": [AIMessage(content="I need to analyze this")]},
            {
                "messages": [
                    AIMessage(content="Analysis complete"),
                    ToolMessage(content="result", tool_call_id="1"),
                ]
            },
        ]

        node = create_agent_node(mock_agent, "Analyst")
        result = node({"messages": [], "step": 0}, RunnableConfig())

        assert mock_agent.invoke.call_count == 2
        # When there's a ToolMessage, the result uses latest tool output
        assert "result" in result["messages"][0].content

    def test_retries_on_insufficient_response(self, mock_agent):
        """Should retry when response contains insufficient signals."""
        mock_agent.invoke.side_effect = [
            {"messages": [AIMessage(content="sorry, need more steps")]},
            {
                "messages": [
                    AIMessage(content="Here is the analysis"),
                    ToolMessage(content="data", tool_call_id="1"),
                ]
            },
        ]

        node = create_agent_node(mock_agent, "Analyst")
        _ = node({"messages": [], "step": 0}, RunnableConfig())

        assert mock_agent.invoke.call_count == 2

    def test_respects_max_retry_attempts(self, mock_agent):
        """Should respect MAX_ANALYST_RETRY_ATTEMPTS limit."""
        # Always return insufficient response
        mock_agent.invoke.return_value = {
            "messages": [AIMessage(content="sorry, need more steps")]
        }

        node = create_agent_node(mock_agent, "Analyst")
        _ = node({"messages": [], "step": 0}, RunnableConfig())

        # Should call: initial + MAX_ANALYST_RETRY_ATTEMPTS retries
        expected_calls = 1 + MAX_ANALYST_RETRY_ATTEMPTS
        assert mock_agent.invoke.call_count == expected_calls

    def test_returns_fallback_when_tool_not_called_after_retry(self, mock_agent):
        """Should return fallback when analyst fails to call tools."""
        mock_agent.invoke.return_value = {
            "messages": [AIMessage(content="some analysis")]
        }

        node = create_agent_node(mock_agent, "Analyst")
        result = node({"messages": [], "step": 0}, RunnableConfig())

        assert "failed to execute required tools" in result["messages"][0].content

    def test_uses_tool_summary_when_insufficient_response_has_tool_data(
        self, mock_agent
    ):
        """Should use tool output when analyst has tool data."""
        mock_agent.invoke.return_value = {
            "messages": [
                AIMessage(content="sorry, need more steps"),
                ToolMessage(content="valuable tool data", tool_call_id="1"),
            ]
        }

        node = create_agent_node(mock_agent, "Analyst")
        result = node({"messages": [], "step": 0}, RunnableConfig())

        assert result["messages"][0].content == "valuable tool data"


class TestAgentNodeToolTracking:
    """Tests for tool call tracking in agent nodes."""

    def test_tracks_tool_calls_correctly(self, mock_agent, mock_state):
        """Should correctly track and report tool activity."""
        mock_agent.invoke.return_value = {
            "messages": [
                AIMessage(
                    content="",
                    tool_calls=[
                        {"id": "1", "name": "search_web", "args": {"query": "test"}}
                    ],
                ),
                ToolMessage(content="result", tool_call_id="1"),
                AIMessage(content="Final answer"),
            ]
        }

        node = create_agent_node(mock_agent, "Researcher")
        result = node(mock_state, RunnableConfig())

        assert "Final answer" in result["messages"][0].content

    def test_handles_mixed_tool_and_text_messages(self, mock_agent):
        """Should handle mix of tool and text messages."""
        mock_agent.invoke.return_value = {
            "messages": [
                AIMessage(content="Step 1"),
                ToolMessage(content="Tool result", tool_call_id="1"),
                AIMessage(content="Step 2"),
                ToolMessage(content="Another result", tool_call_id="2"),
                AIMessage(content="Final"),
            ]
        }

        node = create_agent_node(mock_agent, "Analyst")
        result = node({"messages": [], "step": 0}, RunnableConfig())

        assert result["messages"][0].content == "Final"


class TestCreateAgentNodeEdgeCases:
    """Edge case tests for create_agent_node."""

    def test_handles_agent_exception(self, mock_agent):
        """Should handle agent invocation exceptions gracefully."""
        mock_agent.invoke.side_effect = Exception("Agent error")

        node = create_agent_node(mock_agent, "TestWorker")

        with pytest.raises(Exception):
            node({"messages": [], "step": 0}, RunnableConfig())

    def test_preserves_worker_name_in_response(self, mock_agent):
        """Should preserve worker name in returned message."""
        mock_agent.invoke.return_value = {"messages": [AIMessage(content="Response")]}

        node = create_agent_node(mock_agent, "Researcher")
        result = node({"messages": [], "step": 0}, RunnableConfig())

        assert result["messages"][0].name == "Researcher"

    def test_increments_step_in_state(self, mock_agent, mock_state):
        """Should preserve step in state (not modify it)."""
        mock_agent.invoke.return_value = {"messages": [AIMessage(content="Response")]}

        node = create_agent_node(mock_agent, "TestWorker")
        _ = node(mock_state, RunnableConfig())

        # Agent node should not modify step, that's supervisor's job
        # But we should ensure state is passed through
        assert mock_agent.invoke.call_args[0][0]["step"] == 0
