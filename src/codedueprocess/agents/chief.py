"""Chief justice node factory with deterministic synthesis rules."""

from __future__ import annotations

from langchain_core.language_models.chat_models import BaseChatModel

from codedueprocess.agents.types import StateNode
from codedueprocess.rubric_prompt import format_full_rubric
from codedueprocess.schemas.models import (
    AuditReport,
    CriterionResult,
    Evidence,
    JudicialOpinion,
)
from codedueprocess.state import AgentState


# Deterministic synthesis rules (hardcoded Python logic)
SECURITY_SCORE_THRESHOLD = 2  # Scores at or below this trigger security override
SCORE_VARIANCE_THRESHOLD = 2  # Variance > 2 triggers dissent summary


def calculate_score_variance(opinions: list[JudicialOpinion]) -> tuple[float, bool]:
    """Calculate score variance and determine if dissent summary is required."""
    if len(opinions) < 2:
        return 0.0, False

    scores = [op.score for op in opinions]
    variance = max(scores) - min(scores)
    return variance, variance > SCORE_VARIANCE_THRESHOLD


def apply_security_override(opinions: list[JudicialOpinion]) -> bool:
    """Check if security override should be applied (any judge scored security-related low)."""
    for opinion in opinions:
        # Check if this is a security-related criterion (by convention)
        if (
            "security" in opinion.criterion_id.lower()
            and opinion.score <= SECURITY_SCORE_THRESHOLD
        ):
            return True
    return False


def apply_fact_supremacy(
    evidence: list[Evidence], opinions: list[JudicialOpinion]
) -> int:
    """Apply fact supremacy: evidence over claims determines score."""
    # Count positive vs negative evidence
    positive_evidence = sum(1 for e in evidence if e.found and e.confidence > 0.5)
    negative_evidence = sum(1 for e in evidence if not e.found or e.confidence <= 0.5)

    # Evidence-based adjustment
    if negative_evidence > positive_evidence:
        # More negative evidence - reduce scores
        return -1
    elif positive_evidence > negative_evidence * 2:
        # Strong positive evidence - may increase scores
        return 1
    return 0


def apply_functionality_weight(
    opinions: list[JudicialOpinion], tech_lead_weight: float = 1.3
) -> int:
    """Apply functionality weight: Tech Lead opinion gets priority."""
    weighted_sum = 0.0
    total_weight = 0.0

    for opinion in opinions:
        weight = tech_lead_weight if opinion.judge == "TechLead" else 1.0
        weighted_sum += opinion.score * weight
        total_weight += weight

    if total_weight > 0:
        return int(round(weighted_sum / total_weight))
    return 3  # Default neutral score


def make_chief_justice_node(
    llm: BaseChatModel,
) -> StateNode:
    """Create the chief justice node using deterministic synthesis rules.

    Implements:
    - Security Overrides: Low security scores take precedence
    - Fact Supremacy: Evidence outweighs judge claims
    - Functionality Weight: Tech Lead scores prioritized
    - Variance Detection: Dissent summaries for divergent opinions
    """
    chain = llm.with_structured_output(AuditReport)

    def chief_justice_node(state: AgentState) -> dict[str, object]:
        repo_url = state.get("repo_url", "")
        rubric_metadata = state.get("rubric_metadata")
        synthesis_rules = state.get("synthesis_rules")
        dimensions = state.get("rubric_dimensions", [])
        if rubric_metadata is None:
            raise ValueError(
                "rubric_metadata is required before chief_justice synthesis"
            )
        if synthesis_rules is None:
            raise ValueError(
                "synthesis_rules is required before chief_justice synthesis"
            )
        if not dimensions:
            raise ValueError(
                "rubric_dimensions is required before chief_justice synthesis"
            )

        evidences = state.get("evidences", {})
        evidence_refs = _flatten_evidence(evidences)
        if len(evidence_refs) == 0:
            raise ValueError(
                "evidences is required before chief_justice synthesis; "
                "run detective nodes first"
            )

        opinions = state.get("opinions", [])
        opinions_count = len(opinions)
        if opinions_count == 0:
            raise ValueError(
                "opinions is empty; run judge nodes before chief_justice synthesis"
            )

        required_dimensions = {dimension.id for dimension in dimensions}
        judged_dimensions = {opinion.criterion_id for opinion in opinions}
        missing_judge_dimensions = required_dimensions - judged_dimensions
        if missing_judge_dimensions:
            raise ValueError(
                "judge opinions do not cover all rubric dimensions. Missing: "
                f"{', '.join(sorted(missing_judge_dimensions))}"
            )

        # Group opinions by dimension for synthesis
        opinions_by_dimension: dict[str, list[JudicialOpinion]] = {}
        for opinion in opinions:
            if opinion.criterion_id not in opinions_by_dimension:
                opinions_by_dimension[opinion.criterion_id] = []
            opinions_by_dimension[opinion.criterion_id].append(opinion)

        # Apply deterministic synthesis rules
        criterion_results: list[CriterionResult] = []

        for dimension in dimensions:
            dim_opinions = opinions_by_dimension.get(dimension.id, [])
            if not dim_opinions:
                continue

            # Get relevant evidence for this dimension
            dim_evidence = [
                e
                for _, e in evidence_refs
                if dimension.id in e.goal.lower()
                or dimension.name.lower() in e.goal.lower()
            ]

            # Calculate variance and determine dissent
            variance, needs_dissent = calculate_score_variance(dim_opinions)

            # Apply deterministic rules
            base_score = apply_functionality_weight(dim_opinions)

            # Apply security override
            if apply_security_override(dim_opinions):
                # Find lowest security-related score
                security_scores = [
                    op.score
                    for op in dim_opinions
                    if "security" in op.criterion_id.lower()
                ]
                if security_scores:
                    base_score = min(security_scores)

            # Apply fact supremacy adjustment
            evidence_adjustment = apply_fact_supremacy(dim_evidence, dim_opinions)
            final_score = max(1, min(5, base_score + evidence_adjustment))

            # Generate dissent summary if variance is high
            dissent_summary = None
            if needs_dissent:
                scores_by_judge = {op.judge: op.score for op in dim_opinions}
                dissent_summary = (
                    f"Score variance of {variance:.0f} detected across judges. "
                    f"Prosecutor: {scores_by_judge.get('Prosecutor', 'N/A')}, "
                    f"Defense: {scores_by_judge.get('Defense', 'N/A')}, "
                    f"TechLead: {scores_by_judge.get('TechLead', 'N/A')}. "
                    f"Final score ({final_score}) weighted toward TechLead evaluation."
                )

            # Generate file-level remediation
            remediation = _generate_remediation(
                dim_opinions, dim_evidence, final_score, dimension.id
            )

            criterion_results.append(
                CriterionResult(
                    dimension_id=dimension.id,
                    dimension_name=dimension.name,
                    final_score=final_score,
                    judge_opinions=dim_opinions,
                    dissent_summary=dissent_summary,
                    remediation=remediation,
                )
            )

        # Build evidence and opinion catalogs for LLM context
        evidence_catalog = "\n".join(
            _format_evidence_reference(reference, evidence)
            for reference, evidence in evidence_refs
        )
        opinion_catalog = "\n".join(_format_opinion(opinion) for opinion in opinions)

        # Calculate overall score
        if criterion_results:
            overall_score = sum(cr.final_score for cr in criterion_results) / len(
                criterion_results
            )
        else:
            overall_score = 3.0

        # Generate remediation plan
        remediation_plan = _generate_remediation_plan(criterion_results)

        # Use LLM for executive summary only (deterministic scores already calculated)
        prompt = (
            "Generate an executive summary for this audit report based on the "
            "synthesized judge opinions and evidence below. The scores have already "
            "been determined using deterministic rules (Security Override, Fact Supremacy, "
            "Functionality Weight).\n\n"
            f"Repository URL: {repo_url}\n"
            f"Total evidence entries: {len(evidence_refs)}\n"
            f"Total opinions: {opinions_count}\n"
            f"Overall score: {overall_score:.1f}/5\n\n"
            f"{format_full_rubric(rubric_metadata, dimensions, synthesis_rules)}\n\n"
            f"Evidence list:\n{evidence_catalog}\n\n"
            f"Judge opinions:\n{opinion_catalog}\n\n"
            f"Synthesis rules applied:\n"
            f"- Security Override: Scores <= {SECURITY_SCORE_THRESHOLD} take precedence\n"
            f"- Fact Supremacy: Evidence determines final score adjustments\n"
            f"- Functionality Weight: Tech Lead opinions weighted at 1.3x\n"
            f"- Dissent Requirement: Variance > {SCORE_VARIANCE_THRESHOLD} triggers dissent summary\n"
        )

        report = AuditReport.model_validate(chain.invoke(prompt))

        # Override LLM-generated scores with our deterministic calculations
        report.criteria = criterion_results
        report.overall_score = overall_score
        report.remediation_plan = remediation_plan

        report_dimensions = {criterion.dimension_id for criterion in report.criteria}
        missing_report_dimensions = required_dimensions - report_dimensions
        if missing_report_dimensions:
            raise ValueError(
                "final report did not cover all rubric dimensions. Missing: "
                f"{', '.join(sorted(missing_report_dimensions))}"
            )
        return {"final_report": report}

    return chief_justice_node


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


def _format_opinion(opinion: object) -> str:
    if not isinstance(opinion, JudicialOpinion):
        return f"- invalid opinion payload: {opinion}"
    citations = ", ".join(opinion.cited_evidence)
    return (
        f"- judge={opinion.judge} criterion={opinion.criterion_id} "
        f"score={opinion.score} cited=[{citations}] argument={opinion.argument}"
    )


def _generate_remediation(
    opinions: list[JudicialOpinion],
    evidence: list[Evidence],
    final_score: int,
    dimension_id: str,
) -> str:
    """Generate specific file-level remediation instructions."""
    if final_score >= 4:
        return "No remediation required. Criterion meets quality standards."

    remediation_parts = []

    # Collect locations from evidence
    locations = [e.location for e in evidence if e.location and not e.found]
    if locations:
        remediation_parts.append(
            f"Address missing artifacts at: {', '.join(locations[:3])}"
        )

    # Add judge-specific recommendations
    prosecutor_ops = [op for op in opinions if op.judge == "Prosecutor"]
    if prosecutor_ops and prosecutor_ops[0].score <= 2:
        remediation_parts.append(
            f"Address security/concerns raised by Prosecutor: {prosecutor_ops[0].argument[:100]}"
        )

    tech_lead_ops = [op for op in opinions if op.judge == "TechLead"]
    if tech_lead_ops and tech_lead_ops[0].score <= 3:
        remediation_parts.append(
            f"Improve architectural patterns per TechLead: {tech_lead_ops[0].argument[:100]}"
        )

    if not remediation_parts:
        return f"Review and improve {dimension_id} to meet success patterns defined in rubric."

    return "; ".join(remediation_parts)


def _generate_remediation_plan(criteria: list[CriterionResult]) -> str:
    """Generate comprehensive remediation plan from all criterion results."""
    low_scores = [c for c in criteria if c.final_score <= 2]
    medium_scores = [c for c in criteria if 2 < c.final_score <= 3]

    plan_parts = ["# Remediation Plan\n"]

    if low_scores:
        plan_parts.append("\n## Priority 1: Critical Issues (Score <= 2)\n")
        for criterion in low_scores:
            plan_parts.append(
                f"\n### {criterion.dimension_name} ({criterion.dimension_id})"
            )
            plan_parts.append(f"- Current Score: {criterion.final_score}/5")
            plan_parts.append(f"- Action: {criterion.remediation}")

    if medium_scores:
        plan_parts.append("\n## Priority 2: Improvements Needed (Score 3)\n")
        for criterion in medium_scores:
            plan_parts.append(
                f"\n### {criterion.dimension_name} ({criterion.dimension_id})"
            )
            plan_parts.append(f"- Current Score: {criterion.final_score}/5")
            plan_parts.append(f"- Action: {criterion.remediation}")

    if not low_scores and not medium_scores:
        plan_parts.append("\n## Status: All Criteria Meet Quality Standards\n")
        plan_parts.append(
            "No remediation required. The codebase meets all evaluated criteria."
        )

    return "\n".join(plan_parts)
