"""State management for CodeDueProcess agents."""

import operator
from typing import Annotated

from typing_extensions import TypedDict

from src.codedueprocess.schemas.models import (
    AuditReport,
    Dimension,
    Evidence,
    JudicialOpinion,
)


def merge_evidences(
    existing: dict[str, list[Evidence]], new_data: dict[str, list[Evidence]]
) -> dict[str, list[Evidence]]:
    """Custom reducer for evidence dictionary."""
    if not existing:
        return new_data
    merged = existing.copy()
    for key, val in new_data.items():
        if key in merged:
            merged[key] = merged[key] + val
        else:
            merged[key] = val
    return merged


class AgentState(TypedDict):
    """State for the CodeDueProcess agent workflow."""

    repo_url: str
    repo_path: str
    doc_path: str
    # The Rubric dimensions to be evaluated
    rubric_dimensions: list[Dimension]

    # Evidence collected by Detectives
    # Key is dimension_id, Value is list of Evidence objects
    evidences: Annotated[dict[str, list[Evidence]], merge_evidences]

    # Opinions rendered by Judges
    opinions: Annotated[list[JudicialOpinion], operator.add]

    # Final generated report
    final_report: AuditReport
