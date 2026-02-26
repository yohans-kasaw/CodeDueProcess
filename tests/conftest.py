"""Shared fixtures for test suite."""

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage


@pytest.fixture
def sample_human_message():
    """Provide a sample human message."""
    return HumanMessage(content="Sample query")


@pytest.fixture
def sample_ai_message():
    """Provide a sample AI message."""
    return AIMessage(content="Sample response")


@pytest.fixture
def sample_tool_message():
    """Provide a sample tool message."""
    return ToolMessage(content="Tool result", tool_call_id="test-123")


@pytest.fixture
def sample_conversation():
    """Provide a sample conversation with multiple message types."""
    return [
        HumanMessage(content="What's the weather?"),
        AIMessage(
            content="",
            tool_calls=[{"id": "1", "name": "get_weather", "args": {"city": "Paris"}}],
        ),
        ToolMessage(content="The weather in Paris is sunny", tool_call_id="1"),
        AIMessage(content="It's sunny in Paris today!"),
    ]


@pytest.fixture
def empty_state():
    """Provide an empty agent state."""
    return {
        "messages": [],
        "step": 0,
        "next": "",
    }


@pytest.fixture
def basic_state():
    """Provide a basic agent state with one message."""
    return {
        "messages": [HumanMessage(content="Test query")],
        "step": 0,
        "next": "",
    }
