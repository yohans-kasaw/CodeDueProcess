"""Detective node factories with LLM dependency injection."""

from __future__ import annotations

from typing import cast

from langchain_core.language_models.chat_models import BaseChatModel
from langgraph.prebuilt import create_react_agent
from pydantic import BaseModel

from codedueprocess.agents.types import StateNode
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
) -> StateNode:
    """Create a repo investigator node that emits reducer-friendly state updates."""

    def repo_investigator_node(state: AgentState) -> dict[str, object]:
        repo_path = state.get("repo_path", "")
        # repo_url = state.get("repo_url", "") # Not needed for local file tools

        tools = get_audit_tools(repo_path)

        system_prompt = (
            "You are a Repository Investigator. "
            "Your goal is to gather facts about the codebase.\n"
            "Use the provided tools to explore the file system and git history.\n"
            "Focus on:\n"
            "- Git commit patterns (frequency, messages, authors)\n"
            "- File structure and key configuration files\n"
            "- Presence of tests and documentation\n"
            "Return your findings as a list of structured Evidence."
        )

        agent = create_react_agent(llm, tools, prompt=system_prompt)
        # Use recursion_limit in invoke if needed.
        # create_react_agent handles the agent loop.
        response = agent.invoke(
            {"messages": [("user", "Investigate this repository.")]},
            config={"recursion_limit": 10},
        )
        final_message = response["messages"][-1].content

        extractor = llm.with_structured_output(RepositoryFacts)
        prompt = f"Extract evidences from this investigation report:\n\n{final_message}"
        structured_output = cast(RepositoryFacts, extractor.invoke(prompt))

        if structured_output:
            return {"evidences": {"repository_facts": structured_output.evidences}}
        return {"evidences": {"repository_facts": []}}

    return repo_investigator_node


def make_doc_analyst_node(
    llm: BaseChatModel,
) -> StateNode:
    """Create a doc analyst node that emits reducer-friendly state updates."""

    def doc_analyst_node(state: AgentState) -> dict[str, object]:
        repo_path = state.get("repo_path", "")
        doc_path = state.get("doc_path", "")

        tools = get_audit_tools(repo_path)

        system_prompt = (
            "You are a Documentation Analyst. "
            "Your goal is to verify claims in the audit report "
            "against the codebase.\n"
            f"The audit report is located at: {doc_path}\n"
            "Use tools to read the report and then check the code "
            "to verify its claims.\n"
            "Focus on:\n"
            "- Accuracy of architectural descriptions\n"
            "- Verification of cited features\n"
            "Return your findings as a list of structured Evidence."
        )

        agent = create_react_agent(llm, tools, prompt=system_prompt)
        response = agent.invoke(
            {"messages": [("user", "Analyze the documentation and verify claims.")]},
            config={"recursion_limit": 10},
        )
        final_message = response["messages"][-1].content

        extractor = llm.with_structured_output(ClaimSet)
        prompt = (
            f"Extract verified claims/evidences from this analysis:\n\n{final_message}"
        )
        structured_output = cast(ClaimSet, extractor.invoke(prompt))

        if structured_output:
            return {"evidences": {"claim_set": structured_output.evidences}}
        return {"evidences": {"claim_set": []}}

    return doc_analyst_node
