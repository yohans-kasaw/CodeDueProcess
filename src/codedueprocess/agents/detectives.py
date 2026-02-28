"""Enhanced detective node factories with VisionInspector and AST analysis."""

from __future__ import annotations

import json
from typing import cast

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langgraph.prebuilt import create_react_agent
from pydantic import BaseModel

from codedueprocess.agents.types import StateNode
from codedueprocess.enhanced_tools import get_enhanced_audit_tools
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


class VisualArtifacts(BaseModel):
    """Visual artifacts detected by VisionInspector."""

    evidences: list[Evidence]


def make_repo_investigator_node(
    llm: BaseChatModel,
    tracer: AuditTracer | None = None,
) -> StateNode:
    """Create a repo investigator node with AST parsing and git progression analysis."""

    def repo_investigator_node(state: AgentState) -> dict[str, object]:
        repo_path = state.get("repo_path", "")
        rubric_metadata = state.get("rubric_metadata")
        rubric_dimensions = state.get("rubric_dimensions", [])
        if rubric_metadata is None:
            raise ValueError("rubric_metadata is required for repo_investigator")
        if not rubric_dimensions:
            raise ValueError("rubric_dimensions is required for repo_investigator")

        # Get both basic and enhanced tools
        tools = get_audit_tools(repo_path)
        enhanced_tools = get_enhanced_audit_tools(repo_path)
        all_tools = tools + enhanced_tools

        if tracer is not None:
            tracer.tools_loaded(
                "repo_investigator",
                [getattr(tool, "name", tool.__class__.__name__) for tool in all_tools],
            )

        system_prompt = (
            "You are a Repository Investigator with advanced forensic capabilities. "
            "Your goal is to gather comprehensive facts about the codebase using "
            "structural analysis (AST parsing), git progression patterns, and "
            "call pattern extraction.\n"
            "\n"
            "CAPABILITIES:\n"
            "1. Use analyze_ast_structure to parse Python files and extract class/function patterns\n"
            "2. Use analyze_git_progression to extract commit history and author patterns\n"
            "3. Use extract_call_patterns to analyze function call wiring and fan-out metrics\n"
            "4. Use standard file tools to explore the repository structure\n"
            "\n"
            "Tool usage is mandatory before drafting findings. "
            "You must analyze at least 3 Python files using AST parsing.\n"
            "Ground each finding with location, rationale, and confidence score.\n\n"
            f"{format_rubric_metadata(rubric_metadata)}\n\n"
            f"{format_dimensions(rubric_dimensions, target_artifact='github_repo')}"
        )

        agent = create_react_agent(llm, all_tools, prompt=system_prompt)
        callbacks = (
            [ToolLifecycleCallback(tracer, "repo_investigator")] if tracer else []
        )
        config = cast(
            RunnableConfig,
            {"recursion_limit": 15, "callbacks": callbacks},
        )
        response = agent.invoke(
            {
                "messages": [
                    (
                        "user",
                        "Investigate this repository using AST parsing and git analysis. "
                        "Focus on structural patterns, call wiring, and development progression.",
                    )
                ]
            },
            config=config,
        )
        messages = _extract_messages(response)

        tool_calls = _count_tool_calls(messages)
        if tool_calls < 3:
            raise ValueError(
                f"repo_investigator produced only {tool_calls} tool calls; "
                "at least 3 tool calls (AST, git, patterns) are mandatory"
            )

        extractor = llm.with_structured_output(RepositoryFacts)
        transcript = _serialize_transcript(messages)
        prompt = (
            "Extract a complete list of Evidence entries from this full detective "
            "transcript. Include structural analysis findings, git progression patterns, "
            "and call pattern analysis. Each Evidence must have:\n"
            "- goal: what was investigated\n"
            "- found: whether the artifact exists\n"
            "- location: file path, commit hash, or line number\n"
            "- rationale: explanation for the finding\n"
            "- confidence: 0.0-1.0 score\n\n"
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
    """Create a doc analyst node with chunked PDF ingestion (RAG-lite)."""

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
            "You are a Documentation Analyst with RAG-lite PDF ingestion capabilities. "
            "Your goal is to verify claims in the audit report against the codebase "
            "using chunked document analysis.\n"
            f"The audit report is located at: {doc_path}\n"
            "\n"
            "PROCESS:\n"
            "1. Read the documentation file\n"
            "2. Break it into semantic chunks (500-token segments with overlap)\n"
            "3. Extract claims and verify each against the codebase\n"
            "4. Use file tools to verify file existence and content\n"
            "\n"
            "Tool usage is mandatory before drafting findings.\n"
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
        transcript = _serialize_transcript(messages)
        prompt = (
            "Extract a complete list of Evidence entries from this full detective "
            "transcript. Include both positive and negative findings, and keep "
            "location/rationale/confidence grounded in the transcript.\n\n"
            f"{transcript}"
        )
        structured_output = cast(ClaimSet, extractor.invoke(prompt))
        if len(structured_output.evidences) == 0:
            raise ValueError("doc_analyst extracted zero evidences from transcript")

        return {"evidences": {"claim_set": structured_output.evidences}}

    return doc_analyst_node


def make_vision_inspector_node(
    llm: BaseChatModel,
    tracer: AuditTracer | None = None,
) -> StateNode:
    """Create a VisionInspector node for multimodal LLM analysis of images."""

    def vision_inspector_node(state: AgentState) -> dict[str, object]:
        repo_path = state.get("repo_path", "")
        rubric_metadata = state.get("rubric_metadata")
        rubric_dimensions = state.get("rubric_dimensions", [])
        if rubric_metadata is None:
            raise ValueError("rubric_metadata is required for vision_inspector")

        enhanced_tools = get_enhanced_audit_tools(repo_path)

        if tracer is not None:
            tracer.tools_loaded(
                "vision_inspector",
                [
                    getattr(tool, "name", tool.__class__.__name__)
                    for tool in enhanced_tools
                ],
            )

        system_prompt = (
            "You are a VisionInspector - a multimodal forensic analyst. "
            "Your goal is to analyze visual artifacts in the repository including:\n"
            "- Architecture diagrams\n"
            "- Flow charts\n"
            "- Screenshots and mockups\n"
            "- Data visualizations\n"
            "\n"
            "Use inspect_image_artifact to encode images for analysis. "
            "Then use multimodal capabilities to extract meaningful information.\n"
            "Ground each finding with image path, rationale, and confidence.\n\n"
            f"{format_rubric_metadata(rubric_metadata)}\n\n"
            f"{format_dimensions(rubric_dimensions)}"
        )

        agent = create_react_agent(llm, enhanced_tools, prompt=system_prompt)
        callbacks = (
            [ToolLifecycleCallback(tracer, "vision_inspector")] if tracer else []
        )
        config = cast(
            RunnableConfig,
            {"recursion_limit": 10, "callbacks": callbacks},
        )
        response = agent.invoke(
            {
                "messages": [
                    (
                        "user",
                        "Search for and analyze all image files in the repository. "
                        "Focus on architecture diagrams, charts, and documentation images.",
                    )
                ]
            },
            config=config,
        )
        messages = _extract_messages(response)

        tool_calls = _count_tool_calls(messages)

        extractor = llm.with_structured_output(VisualArtifacts)
        transcript = _serialize_transcript(messages)
        prompt = (
            "Extract a complete list of Evidence entries from this vision inspection "
            "transcript. For each image found, create an Evidence with:\n"
            "- goal: what the image represents (e.g., 'Architecture diagram')\n"
            "- found: true if image was analyzed\n"
            "- location: file path of the image\n"
            "- rationale: description of what the image contains\n"
            "- confidence: 0.0-1.0 based on clarity\n\n"
            f"{transcript}"
        )
        structured_output = cast(VisualArtifacts, extractor.invoke(prompt))

        return {"evidences": {"visual_artifacts": structured_output.evidences}}

    return vision_inspector_node


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
