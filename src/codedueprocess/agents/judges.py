"""Judge node factories with BaseChatModel dependency injection."""

from __future__ import annotations

from typing import Any, Literal

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.runnables import Runnable

from codedueprocess.agents.types import StateNode
from codedueprocess.rubric_prompt import (
    format_dimensions,
    format_rubric_metadata,
    format_synthesis_rules,
)
from codedueprocess.schemas.models import Evidence, JudgeDeliberation
from codedueprocess.state import AgentState


def build_judicial_opinion_chain(
    llm: BaseChatModel,
) -> Runnable[Any, Any]:
    """Build a typed judge deliberation chain from a chat model."""
    return llm.with_structured_output(JudgeDeliberation)


def make_judge_node(
    llm: BaseChatModel,
    judge: Literal["Prosecutor", "Defense", "TechLead"],
) -> StateNode:
    """Create a single judge node that appends a `JudicialOpinion` to state."""
    chain = build_judicial_opinion_chain(llm)

    def judge_node(state: AgentState) -> dict[str, object]:
        rubric_metadata = state.get("rubric_metadata")
        synthesis_rules = state.get("synthesis_rules")
        dimensions = state.get("rubric_dimensions")
        if rubric_metadata is None:
            raise ValueError("rubric_metadata is required for judges")
        if synthesis_rules is None:
            raise ValueError("synthesis_rules is required for judges")
        if not dimensions:
            raise ValueError(
                "rubric_dimensions is required and must contain at least one dimension"
            )

        evidence_refs = _flatten_evidence(state.get("evidences", {}))
        if not evidence_refs:
            raise ValueError("evidences is empty; judges require detective evidence")

        evidence_catalog = "\n".join(
            _format_evidence_reference(reference, evidence)
            for reference, evidence in evidence_refs
        )

        prompt = (
            f"Judge role: {judge}\n"
            "You must score every rubric dimension, with one JudicialOpinion "
            "per dimension, and set criterion_id exactly to dimension id.\n"
            "You must base your opinions only on the evidence list below. "
            "In cited_evidence, include only evidence reference IDs from the list.\n\n"
            f"{format_rubric_metadata(rubric_metadata)}\n\n"
            f"{format_synthesis_rules(synthesis_rules)}\n\n"
            f"{format_dimensions(dimensions)}\n\n"
            f"Evidence list:\n{evidence_catalog}\n\n"
            "Return JudgeDeliberation with opinions covering all dimensions."
        )
        deliberation = JudgeDeliberation.model_validate(chain.invoke(prompt))
        if not deliberation.opinions:
            raise ValueError(f"{judge} returned no opinions")

        valid_references = {reference for reference, _ in evidence_refs}
        required_dimensions = {dimension.id for dimension in dimensions}
        returned_dimensions: set[str] = set()

        for opinion in deliberation.opinions:
            if opinion.judge != judge:
                raise ValueError(
                    f"{judge} returned mismatched opinion judge={opinion.judge}"
                )
            returned_dimensions.add(opinion.criterion_id)
            if opinion.criterion_id not in required_dimensions:
                raise ValueError(
                    f"{judge} returned unknown criterion_id: {opinion.criterion_id}"
                )
            if len(opinion.cited_evidence) == 0:
                raise ValueError(
                    f"{judge} returned opinion without cited evidence for "
                    f"{opinion.criterion_id}"
                )
            unknown_refs = [
                reference
                for reference in opinion.cited_evidence
                if reference not in valid_references
            ]
            if unknown_refs:
                raise ValueError(
                    f"{judge} cited unknown evidence references: "
                    f"{', '.join(unknown_refs)}"
                )

        missing_dimensions = required_dimensions - returned_dimensions
        if missing_dimensions:
            raise ValueError(
                f"{judge} did not score all dimensions. Missing: "
                f"{', '.join(sorted(missing_dimensions))}"
            )

        return {"opinions": deliberation.opinions}

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
