import operator
from typing import Annotated, Literal

from pydantic import BaseModel, Field
from typing_extensions import TypedDict


# --- Detective Output ---
class Evidence(BaseModel):
    goal: str
    found: bool
    content: str | None = None
    location: str  # File path or commit hash
    rationale: str
    confidence: float


# --- Judge Output ---
class JudicialOpinion(BaseModel):
    judge: Literal["Prosecutor", "Defense", "TechLead"]
    criterion_id: str
    score: int = Field(ge=1, le=5)
    argument: str
    cited_evidence: list[str]


# --- Chief Justice Output ---
class CriterionResult(BaseModel):
    dimension_id: str
    dimension_name: str
    final_score: int = Field(ge=1, le=5)
    judge_opinions: list[JudicialOpinion]
    dissent_summary: str | None = None  # Required when score variance > 2
    remediation: str


class AuditReport(BaseModel):
    repo_url: str
    executive_summary: str
    overall_score: float
    criteria: list[CriterionResult]
    remediation_plan: str


# --- Graph State ---
class AgentState(TypedDict):
    repo_url: str
    pdf_path: str
    rubric_dimensions: list[dict]
    # Reducers prevent parallel agents from overwriting data
    evidences: Annotated[dict[str, list[Evidence]], operator.ior]
    opinions: Annotated[list[JudicialOpinion], operator.add]
    final_report: AuditReport
