"""Detective node factories with LLM dependency injection."""

from __future__ import annotations

from langchain_core.language_models.chat_models import BaseChatModel
from pydantic import BaseModel

from src.codedueprocess.agents.types import StateNode
from src.codedueprocess.schemas.models import Evidence
from src.codedueprocess.state import AgentState


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
    chain = llm.with_structured_output(RepositoryFacts)

    def repo_investigator_node(state: AgentState) -> dict[str, object]:
        repo_path = state.get("repo_path", "")
        repo_url = state.get("repo_url", "")
        prompt = (
            "Inspect repository facts and return forensic evidence. "
            f"Repository path: {repo_path}. Repository URL: {repo_url}"
        )
        output = RepositoryFacts.model_validate(chain.invoke(prompt))
        return {"evidences": {"repository_facts": output.evidences}}

    return repo_investigator_node


def make_doc_analyst_node(
    llm: BaseChatModel,
) -> StateNode:
    """Create a doc analyst node that emits reducer-friendly state updates."""
    chain = llm.with_structured_output(ClaimSet)

    def doc_analyst_node(state: AgentState) -> dict[str, object]:
        docs_path = state.get("docs_path", "")
        pdf_path = state.get("pdf_path", "")
        prompt = (
            "Inspect repository docs and external report claims. "
            f"Docs path: {docs_path}. External report path: {pdf_path}"
        )
        output = ClaimSet.model_validate(chain.invoke(prompt))
        return {"evidences": {"claim_set": output.evidences}}

    return doc_analyst_node
