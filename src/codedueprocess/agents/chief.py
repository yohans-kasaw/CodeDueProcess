"""Chief justice node factory."""

from __future__ import annotations

from langchain_core.language_models.chat_models import BaseChatModel

from src.codedueprocess.agents.types import StateNode
from src.codedueprocess.schemas.models import AuditReport
from src.codedueprocess.state import AgentState


def make_chief_justice_node(
    llm: BaseChatModel,
) -> StateNode:
    """Create the chief justice node using a typed structured-output chain."""
    chain = llm.with_structured_output(AuditReport)

    def chief_justice_node(state: AgentState) -> dict[str, object]:
        repo_url = state.get("repo_url", "")
        evidences = state.get("evidences", {})
        if not evidences:
            raise ValueError(
                "evidences is required before chief_justice synthesis; "
                "run detective nodes first"
            )

        opinions_count = len(state.get("opinions", []))
        if opinions_count == 0:
            raise ValueError(
                "opinions is empty; run judge nodes before chief_justice synthesis"
            )

        prompt = (
            "Synthesize judicial opinions into a final audit report. "
            f"Repository URL: {repo_url}. Opinions count: {opinions_count}."
        )
        report = AuditReport.model_validate(chain.invoke(prompt))
        return {"final_report": report}

    return chief_justice_node
