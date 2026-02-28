"""Detective node factories with LLM dependency injection."""

from __future__ import annotations

import json
from typing import cast

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langgraph.prebuilt import create_react_agent
from pydantic import BaseModel

from codedueprocess.agents.types import StateNode
from codedueprocess.printing.tracer import AuditTracer, ToolLifecycleCallback
from codedueprocess.rubric_prompt import format_dimensions, format_rubric_metadata
from codedueprocess.schemas.models import Evidence
from codedueprocess.state import AgentState
from codedueprocess.tools.setup import get_audit_tools


class RepositoryFacts(BaseModel):
    """Structured repository facts emitted by the repo investigator."""

    evidences: list[Evidence]


class ClaimSet(BaseModel):
    """Structured documentation claim set emitted by doc analyst."""

    evidences: list[Evidence]


def make_repo_investigator_node(
    llm: BaseChatModel,
    tracer: AuditTracer | None = None,
) -> StateNode:
    """Create a repo investigator node that emits reducer-friendly state updates."""

    def repo_investigator_node(state: AgentState) -> dict[str, object]:
        repo_path = state.get("repo_path", "")
        rubric_metadata = state.get("rubric_metadata")
        rubric_dimensions = state.get("rubric_dimensions", [])
        if rubric_metadata is None:
            raise ValueError("rubric_metadata is required for repo_investigator")
        if not rubric_dimensions:
            raise ValueError("rubric_dimensions is required for repo_investigator")
        # repo_url = state.get("repo_url", "") # Not needed for local file tools

        tools = get_audit_tools(repo_path)
        if tracer is not None:
            tracer.tools_loaded(
                "repo_investigator",
                [getattr(tool, "name", tool.__class__.__name__) for tool in tools],
            )

        system_prompt = (
            "You are a Repository Investigator. "
            "Your goal is to gather facts about the codebase.\n"
            "Use the provided tools to explore the file system and git history.\n"
            "Tool usage is mandatory before drafting findings.\n"
            "Follow the rubric metadata and dimension instructions below.\n"
            "Collect evidence that enables judges to score every rubric dimension.\n"
            "Ground each finding with location and rationale.\n\n"
            f"{format_rubric_metadata(rubric_metadata)}\n\n"
            f"{format_dimensions(rubric_dimensions, target_artifact='github_repo')}"
        )

        agent = create_react_agent(llm, tools, prompt=system_prompt)
        callbacks = (
            [ToolLifecycleCallback(tracer, "repo_investigator")] if tracer else []
        )
        config = cast(
            RunnableConfig,
            {"recursion_limit": 10, "callbacks": callbacks},
        )
        response = agent.invoke(
            {"messages": [("user", "Investigate this repository.")]},
            config=config,
        )
        messages = _extract_messages(response)

        tool_calls = _count_tool_calls(messages)
        if tool_calls < 1:
            raise ValueError(
                "repo_investigator produced zero tool calls; tool calling is mandatory"
            )

        extractor = llm.with_structured_output(RepositoryFacts)
        transcript = _serialize_transcript(messages)
        prompt = (
            "Extract a complete list of Evidence entries from this full detective "
            "transcript. Include both positive and negative findings, and keep "
            "location/rationale/confidence grounded in the transcript.\n\n"
            f"{transcript}"
        )
        structured_output = cast(RepositoryFacts, extractor.invoke(prompt))
        if len(structured_output.evidences) == 0:
            raise ValueError(
                "repo_investigator extracted zero evidences from transcript"
            )

        return {"evidences": {"repository_facts": structured_output.evidences}}

    return repo_investigator_node


def make_doc_analyst_node(
    llm: BaseChatModel,
    tracer: AuditTracer | None = None,
) -> StateNode:
    """Create a doc analyst node that emits reducer-friendly state updates."""

    def doc_analyst_node(state: AgentState) -> dict[str, object]:
        repo_path = state.get("repo_path", "")
        doc_path = state.get("doc_path", "")
        rubric_metadata = state.get("rubric_metadata")
        rubric_dimensions = state.get("rubric_dimensions", [])
        if rubric_metadata is None:
            raise ValueError("rubric_metadata is required for doc_analyst")
        if not rubric_dimensions:
            raise ValueError("rubric_dimensions is required for doc_analyst")

        tools = get_audit_tools(repo_path)
        if tracer is not None:
            tracer.tools_loaded(
                "doc_analyst",
                [getattr(tool, "name", tool.__class__.__name__) for tool in tools],
            )

        system_prompt = (
            "You are a Documentation Analyst. "
            "Your goal is to verify claims in the audit report "
            "against the codebase.\n"
            f"The audit report is located at: {doc_path}\n"
            "Use tools to read the report and then check the code "
            "to verify its claims.\n"
            "Tool usage is mandatory before drafting findings.\n"
            "Follow the rubric metadata and dimension instructions below.\n"
            "Collect evidence that enables judges to score every rubric dimension.\n"
            "Ground each finding with location and rationale.\n\n"
            f"{format_rubric_metadata(rubric_metadata)}\n\n"
            f"{format_dimensions(rubric_dimensions, target_artifact='docs')}"
        )

        agent = create_react_agent(llm, tools, prompt=system_prompt)
        callbacks = [ToolLifecycleCallback(tracer, "doc_analyst")] if tracer else []
        config = cast(
            RunnableConfig,
            {"recursion_limit": 10, "callbacks": callbacks},
        )
        response = agent.invoke(
            {"messages": [("user", "Analyze the documentation and verify claims.")]},
            config=config,
        )
        messages = _extract_messages(response)

        tool_calls = _count_tool_calls(messages)
        if tool_calls < 1:
            raise ValueError(
                "doc_analyst produced zero tool calls; tool calling is mandatory"
            )

        extractor = llm.with_structured_output(ClaimSet)
        prompt = (
            "Extract a complete list of Evidence entries from this full detective "
            "transcript. Include both positive and negative findings, and keep "
            "location/rationale/confidence grounded in the transcript.\n\n"
            f"{_serialize_transcript(messages)}"
        )
        structured_output = cast(ClaimSet, extractor.invoke(prompt))
        if len(structured_output.evidences) == 0:
            raise ValueError("doc_analyst extracted zero evidences from transcript")

        return {"evidences": {"claim_set": structured_output.evidences}}

    return doc_analyst_node


def _extract_messages(response: object) -> list[BaseMessage]:
    if not isinstance(response, dict):
        raise ValueError("detective response must be a dict containing messages")
    messages = response.get("messages")
    if not isinstance(messages, list):
        raise ValueError("detective response does not contain a messages list")
    typed_messages: list[BaseMessage] = []
    for message in messages:
        if isinstance(message, BaseMessage):
            typed_messages.append(message)
    return typed_messages


def _count_tool_calls(messages: list[BaseMessage]) -> int:
    total = 0
    for message in messages:
        if isinstance(message, AIMessage):
            total += len(message.tool_calls)
    return total


def _serialize_transcript(messages: list[BaseMessage]) -> str:
    lines: list[str] = []
    for index, message in enumerate(messages, start=1):
        role = message.type.upper()
        content = _stringify_content(message.content)
        lines.append(f"[{index}] {role}: {content}")

        if isinstance(message, AIMessage) and message.tool_calls:
            for tool_call in message.tool_calls:
                name = tool_call.get("name", "unknown")
                args = json.dumps(tool_call.get("args", {}), ensure_ascii=True)
                lines.append(f"    TOOL_CALL name={name} args={args}")

        if isinstance(message, ToolMessage):
            lines.append(f"    TOOL_RESULT id={message.tool_call_id}")

    return "\n".join(lines)


def _stringify_content(content: object) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return json.dumps(content, ensure_ascii=True)
    return str(content)
