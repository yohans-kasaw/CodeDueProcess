"""Judge node factories with BaseChatModel dependency injection."""

from __future__ import annotations

from typing import Any, Literal

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.runnables import Runnable

from codedueprocess.agents.types import StateNode
from codedueprocess.schemas.models import Evidence, JudicialOpinion
from codedueprocess.state import AgentState


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
        evidence_refs = _flatten_evidence(state.get("evidences", {}))
        if not evidence_refs:
            raise ValueError("evidences is empty; judges require detective evidence")

        evidence_catalog = "\n".join(
            _format_evidence_reference(reference, evidence)
            for reference, evidence in evidence_refs
        )

        prompt = (
            f"Judge role: {judge}\n"
            f"Criterion: {criterion_id}\n"
            "You must base your opinion only on the evidence list below. "
            "In cited_evidence, include only evidence reference IDs from the list.\n\n"
            f"Evidence list:\n{evidence_catalog}\n\n"
            "Return one JudicialOpinion."
        )
        opinion = JudicialOpinion.model_validate(chain.invoke(prompt))
        if len(opinion.cited_evidence) == 0:
            raise ValueError(f"{judge} returned opinion without cited evidence")

        valid_references = {reference for reference, _ in evidence_refs}
        unknown_refs = [
            reference
            for reference in opinion.cited_evidence
            if reference not in valid_references
        ]
        if unknown_refs:
            raise ValueError(
                f"{judge} cited unknown evidence references: {', '.join(unknown_refs)}"
            )

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


def _flatten_evidence(
    evidences: object,
) -> list[tuple[str, Evidence]]:
    if not isinstance(evidences, dict):
        return []

    flattened: list[tuple[str, Evidence]] = []
    for group_name, items in evidences.items():
        if not isinstance(group_name, str) or not isinstance(items, list):
            continue
        for index, item in enumerate(items, start=1):
            if isinstance(item, Evidence):
                flattened.append((f"{group_name}:{index}", item))
    return flattened


def _format_evidence_reference(reference: str, evidence: Evidence) -> str:
    content = evidence.content or ""
    return (
        f"- {reference} | found={evidence.found} | location={evidence.location} "
        f"| goal={evidence.goal} | rationale={evidence.rationale} "
        f"| confidence={evidence.confidence:.2f} | content={content}"
    )
