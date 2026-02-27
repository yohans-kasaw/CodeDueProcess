"""Shared fixtures for test suite."""

import json
from collections.abc import Iterator
from itertools import cycle
from typing import Any

import pytest
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.runnables import RunnableLambda


@pytest.fixture(autouse=True)
def disable_tracing(monkeypatch):
    """Disable LangChain tracing for all tests to prevent hangs."""
    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "false")


@pytest.fixture(autouse=True)
def mock_langsmith_testing(monkeypatch):
    """Mock langsmith testing functions to prevent network calls."""
    try:
        import langsmith.testing

        monkeypatch.setattr(
            langsmith.testing, "log_inputs", lambda *args, **kwargs: None
        )
        monkeypatch.setattr(
            langsmith.testing, "log_outputs", lambda *args, **kwargs: None
        )
        monkeypatch.setattr(
            langsmith.testing, "log_reference_outputs", lambda *args, **kwargs: None
        )
        monkeypatch.setattr(
            langsmith.testing, "log_feedback", lambda *args, **kwargs: None
        )
    except ImportError:
        pass


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


class StructuredGenericFakeChatModel(GenericFakeChatModel):
    """Generic fake chat model with deterministic structured output parsing."""

    def with_structured_output(self, schema: Any, **_kwargs: Any) -> RunnableLambda:
        """Return a runnable that validates JSON payloads against a schema."""

        def _invoke(prompt_input: Any) -> Any:
            raw_message = self.invoke(prompt_input)
            if isinstance(raw_message.content, str):
                payload = raw_message.content
            else:
                payload = json.dumps(raw_message.content)
            return schema.model_validate_json(payload)

        return RunnableLambda(_invoke)


def _repeat_message(payload: str, count: int = 8) -> Iterator[AIMessage]:
    """Provide multiple deterministic messages to tolerate retries/replays."""
    del count
    return cycle([AIMessage(content=payload)])


@pytest.fixture
def mockllm_judicial_opinion() -> GenericFakeChatModel:
    """Provide deterministic mock LLM output for successful JudicialOpinion parsing."""
    payload = (
        '{"judge":"Prosecutor","criterion_id":"git_history","score":4,'
        '"argument":"Commit history shows deliberate progress.",'
        '"cited_evidence":["repo:commits", "docs:milestones"]}'
    )
    return StructuredGenericFakeChatModel(messages=_repeat_message(payload))


@pytest.fixture
def mockllm_defense_opinion() -> GenericFakeChatModel:
    """Provide deterministic defense judicial opinion payload."""
    payload = (
        '{"judge":"Defense","criterion_id":"git_history","score":3,'
        '"argument":"Repository demonstrates partial requirement coverage.",'
        '"cited_evidence":["repo:modules", "docs:claims"]}'
    )
    return StructuredGenericFakeChatModel(messages=_repeat_message(payload))


@pytest.fixture
def mockllm_techlead_opinion() -> GenericFakeChatModel:
    """Provide deterministic tech lead judicial opinion payload."""
    payload = (
        '{"judge":"TechLead","criterion_id":"git_history","score":4,'
        '"argument":"Architecture is maintainable with minor caveats.",'
        '"cited_evidence":["repo:tree", "doc:architecture"]}'
    )
    return StructuredGenericFakeChatModel(messages=_repeat_message(payload))


@pytest.fixture
def mockllm_malformed_judicial_opinion() -> GenericFakeChatModel:
    """Provide deterministic malformed output for schema-failure testing."""
    payload = '{"judge":"Prosecutor","criterion_id":"git_history","score":"bad"}'
    return StructuredGenericFakeChatModel(messages=_repeat_message(payload))


@pytest.fixture
def mockllm_repo_evidence() -> GenericFakeChatModel:
    """Provide deterministic repository evidence payload."""
    payload = (
        '{"evidences":[{"goal":"Track commit quality","found":true,'
        '"content":"12 commits with meaningful messages",'
        '"location":".git/logs","rationale":"History is descriptive",'
        '"confidence":0.92}]}'
    )
    return StructuredGenericFakeChatModel(messages=_repeat_message(payload))


@pytest.fixture
def mockllm_doc_evidence() -> GenericFakeChatModel:
    """Provide deterministic documentation evidence payload."""
    payload = (
        '{"evidences":[{"goal":"Validate architecture claim","found":true,'
        '"content":"Architecture describes layered DAG",'
        '"location":"docs/architecture.md:16",'
        '"rationale":"Claim is explicit in documentation",'
        '"confidence":0.88}]}'
    )
    return StructuredGenericFakeChatModel(messages=_repeat_message(payload))


@pytest.fixture
def mockllm_audit_report() -> GenericFakeChatModel:
    """Provide deterministic final audit report payload."""
    payload = (
        '{"repo_url":"https://github.com/example/repo",'
        '"executive_summary":"Overall implementation is on track.",'
        '"overall_score":4.1,'
        '"criteria":[{"dimension_id":"git_history",'
        '"dimension_name":"Git History",'
        '"final_score":4,'
        '"judge_opinions":[{"judge":"TechLead","criterion_id":"git_history",'
        '"score":4,"argument":"Consistent progress.",'
        '"cited_evidence":["repo:.git/logs"]}],'
        '"dissent_summary":null,'
        '"remediation":"Keep commit messages descriptive."}],'
        '"remediation_plan":"Address medium-priority findings in next sprint."}'
    )
    return StructuredGenericFakeChatModel(messages=_repeat_message(payload))
