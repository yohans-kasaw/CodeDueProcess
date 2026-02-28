"""Chief justice node factory."""

from __future__ import annotations

from langchain_core.language_models.chat_models import BaseChatModel

from codedueprocess.agents.types import StateNode
from codedueprocess.schemas.models import AuditReport, Evidence, JudicialOpinion
from codedueprocess.state import AgentState


def make_chief_justice_node(
    llm: BaseChatModel,
) -> StateNode:
    """Create the chief justice node using a typed structured-output chain."""
    chain = llm.with_structured_output(AuditReport)

    def chief_justice_node(state: AgentState) -> dict[str, object]:
        repo_url = state.get("repo_url", "")
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

        evidence_catalog = "\n".join(
            _format_evidence_reference(reference, evidence)
            for reference, evidence in evidence_refs
        )
        opinion_catalog = "\n".join(_format_opinion(opinion) for opinion in opinions)

        prompt = (
            "Synthesize judicial opinions into a final audit report grounded "
            "in the evidence list and judge opinions below.\n"
            f"Repository URL: {repo_url}\n"
            f"Total evidence entries: {len(evidence_refs)}\n"
            f"Total opinions: {opinions_count}\n\n"
            f"Evidence list:\n{evidence_catalog}\n\n"
            f"Judge opinions:\n{opinion_catalog}"
        )
        report = AuditReport.model_validate(chain.invoke(prompt))
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
