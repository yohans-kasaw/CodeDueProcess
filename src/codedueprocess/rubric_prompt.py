"""Rubric prompt block helpers shared across agents and tracing."""

from __future__ import annotations

from codedueprocess.schemas.models import Dimension, RubricMetadata, SynthesisRules


def format_rubric_metadata(metadata: RubricMetadata) -> str:
    """Render rubric metadata as a compact multiline block."""
    return (
        "Rubric metadata:\n"
        f"- name: {metadata.rubric_name}\n"
        f"- grading_target: {metadata.grading_target}\n"
        f"- version: {metadata.version}"
    )


def format_synthesis_rules(rules: SynthesisRules) -> str:
    """Render synthesis rules for chief and judge prompts."""
    return (
        "Synthesis rules:\n"
        f"- security_override: {rules.security_override}\n"
        f"- fact_supremacy: {rules.fact_supremacy}\n"
        f"- functionality_weight: {rules.functionality_weight}\n"
        f"- dissent_requirement: {rules.dissent_requirement}\n"
        f"- variance_re_evaluation: {rules.variance_re_evaluation}"
    )


def format_dimensions(
    dimensions: list[Dimension],
    *,
    target_artifact: str | None = None,
) -> str:
    """Render dimensions, optionally filtered by target artifact."""
    selected = dimensions
    if target_artifact is not None:
        selected = [d for d in dimensions if d.target_artifact == target_artifact]

    if not selected:
        return "Dimensions:\n- none"

    lines: list[str] = ["Dimensions:"]
    for dimension in selected:
        lines.extend(
            [
                (
                    "- "
                    f"id={dimension.id} | name={dimension.name} "
                    f"| target_artifact={dimension.target_artifact}"
                ),
                f"  forensic_instruction: {dimension.forensic_instruction}",
                f"  success_pattern: {dimension.success_pattern}",
                f"  failure_pattern: {dimension.failure_pattern}",
            ]
        )
    return "\n".join(lines)


def format_full_rubric(
    metadata: RubricMetadata,
    dimensions: list[Dimension],
    rules: SynthesisRules,
) -> str:
    """Render full rubric details without summarization."""
    return (
        f"{format_rubric_metadata(metadata)}\n\n"
        f"{format_synthesis_rules(rules)}\n\n"
        f"{format_dimensions(dimensions)}"
    )
