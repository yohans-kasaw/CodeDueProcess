"""Judge node factories with distinct personas, structured output, and retry logic."""

from __future__ import annotations

from typing import Any, Literal

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.runnables import Runnable
from pydantic import ValidationError

from codedueprocess.agents.types import StateNode
from codedueprocess.rubric_prompt import (
    format_dimensions,
    format_rubric_metadata,
    format_synthesis_rules,
)
from codedueprocess.schemas.models import Evidence, JudgeDeliberation
from codedueprocess.state import AgentState


# Persona-specific prompt templates
PROSECUTOR_PERSONA = """
You are the Prosecutor - an adversarial, critical code reviewer.
Your philosophy: "Code is guilty until proven innocent."

EVALUATION PRINCIPLES:
- Be harsh and skeptical of all code claims
- Question every design decision aggressively
- Focus on security vulnerabilities, edge cases, and failure modes
- Demand explicit evidence for every positive claim
- Penalize missing documentation, tests, or error handling
- Look for technical debt, shortcuts, and anti-patterns
- Never give the benefit of the doubt

When scoring, default to lower scores unless compelling evidence proves quality.
Cite specific evidence references to support your adversarial position.
"""

DEFENSE_PERSONA = """
You are the Defense Attorney - a pragmatic, intent-focused code advocate.
Your philosophy: "Code should be evaluated by its intent and context."

EVALUATION PRINCIPLES:
- Consider the practical constraints and deadlines the developers faced
- Give credit for good architectural intentions even if imperfectly executed
- Focus on whether the code solves the stated problem effectively
- Be forgiving of minor style issues if functionality is sound
- Value working solutions over perfect abstractions
- Consider maintainability and readability for future developers
- Look for pragmatic trade-offs that make sense

When scoring, consider the overall value delivered and the developer's context.
Cite specific evidence showing the code meets its intended goals.
"""

TECH_LEAD_PERSONA = """
You are the Tech Lead - an architectural soundness evaluator.
Your philosophy: "Code must be scalable, maintainable, and well-architected."

EVALUATION PRINCIPLES:
- Evaluate architectural patterns and design decisions
- Check for proper separation of concerns and modularity
- Assess test coverage and quality assurance practices
- Review API design for consistency and clarity
- Look for proper error handling and logging
- Evaluate performance considerations and scalability
- Check for code reuse and DRY principles
- Assess documentation quality and completeness

When scoring, prioritize architectural soundness over minor implementation details.
Cite specific evidence about code structure, patterns, and maintainability.
"""


def build_judicial_opinion_chain(
    llm: BaseChatModel,
) -> Runnable[Any, Any]:
    """Build a typed judge deliberation chain from a chat model."""
    return llm.with_structured_output(JudgeDeliberation)


def make_judge_node_with_retry(
    llm: BaseChatModel,
    judge: Literal["Prosecutor", "Defense", "TechLead"],
    max_retries: int = 3,
) -> StateNode:
    """Create a single judge node with persona prompts and retry logic."""
    chain = build_judicial_opinion_chain(llm)

    # Select persona prompt
    if judge == "Prosecutor":
        persona_prompt = PROSECUTOR_PERSONA
    elif judge == "Defense":
        persona_prompt = DEFENSE_PERSONA
    else:
        persona_prompt = TECH_LEAD_PERSONA

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
            f"{persona_prompt}\n\n"
            f"Your role: {judge}\n"
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

        # Retry logic for validation
        deliberation: JudgeDeliberation | None = None
        last_error = None
        for attempt in range(max_retries):
            try:
                deliberation = JudgeDeliberation.model_validate(chain.invoke(prompt))
                break
            except ValidationError as e:
                last_error = e
                if attempt < max_retries - 1:
                    # Enhance prompt with error feedback
                    prompt += f"\n\nPrevious attempt failed validation: {e}. Please ensure all required fields are present and valid."
                    continue
                raise ValueError(
                    f"{judge} failed validation after {max_retries} attempts: {e}"
                )

        if deliberation is None:
            raise ValueError(f"{judge} failed to produce valid deliberation")

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


def make_judge_node(
    llm: BaseChatModel,
    judge: Literal["Prosecutor", "Defense", "TechLead"],
) -> StateNode:
    """Create a single judge node (legacy wrapper for compatibility)."""
    return make_judge_node_with_retry(llm, judge, max_retries=3)


def make_prosecutor_node(llm: BaseChatModel) -> StateNode:
    """Create the Prosecutor judge node with adversarial persona."""
    return make_judge_node_with_retry(llm, "Prosecutor")


def make_defense_node(llm: BaseChatModel) -> StateNode:
    """Create the Defense judge node with pragmatic persona."""
    return make_judge_node_with_retry(llm, "Defense")


def make_tech_lead_node(llm: BaseChatModel) -> StateNode:
    """Create the TechLead judge node with architectural focus."""
    return make_judge_node_with_retry(llm, "TechLead")


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
