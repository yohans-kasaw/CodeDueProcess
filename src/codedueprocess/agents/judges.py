"""Judge node factories with BaseChatModel dependency injection."""

from __future__ import annotations

from typing import Any, Literal

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.runnables import Runnable

from src.codedueprocess.agents.types import StateNode
from src.codedueprocess.schemas.models import JudicialOpinion
from src.codedueprocess.state import AgentState


def build_judicial_opinion_chain(
    llm: BaseChatModel,
) -> Runnable[Any, Any]:
    """Build a typed judicial opinion chain from a chat model."""
    return llm.with_structured_output(JudicialOpinion)


def make_judge_node(
    llm: BaseChatModel,
    judge: Literal["Prosecutor", "Defense", "TechLead"],
) -> StateNode:
    """Create a single judge node that appends a `JudicialOpinion` to state."""
    chain = build_judicial_opinion_chain(llm)

    def judge_node(state: AgentState) -> dict[str, object]:
        dimensions = state.get("rubric_dimensions")
        if not dimensions:
            raise ValueError(
                "rubric_dimensions is required and must contain at least one dimension"
            )

        criterion_id = dimensions[0].id
        prompt = (
            f"Judge role: {judge}. "
            f"Criterion: {criterion_id}. "
            "Return a judicial opinion with evidence references."
        )
        opinion = JudicialOpinion.model_validate(chain.invoke(prompt))
        return {"opinions": [opinion]}

    return judge_node


def make_prosecutor_node(llm: BaseChatModel) -> StateNode:
    """Create the Prosecutor judge node."""
    return make_judge_node(llm, "Prosecutor")


def make_defense_node(llm: BaseChatModel) -> StateNode:
    """Create the Defense judge node."""
    return make_judge_node(llm, "Defense")


def make_tech_lead_node(llm: BaseChatModel) -> StateNode:
    """Create the TechLead judge node."""
    return make_judge_node(llm, "TechLead")
