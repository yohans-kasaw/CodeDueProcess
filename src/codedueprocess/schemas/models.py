"""Pydantic models for CodeDueProcess."""

from typing import Literal

from pydantic import BaseModel, Field

# --- Evidence ---


class Evidence(BaseModel):
    """Evidence collected by detectives during investigation."""

    goal: str = Field(description="The specific goal or claim being investigated")
    found: bool = Field(description="Whether the artifact exists")
    content: str | None = Field(
        default=None, description="The content or summary of the finding"
    )
    location: str = Field(description="File path, commit hash, or document section")
    rationale: str = Field(description="Rationale for confidence in this evidence")
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence score 0.0-1.0")


# --- Rubric ---


class Dimension(BaseModel):
    """A rubric dimension for evaluating code quality."""

    id: str = Field(description="Unique identifier for the dimension")
    name: str = Field(description="Human-readable name")
    target_artifact: Literal["github_repo", "docs"] = Field(
        description="Which artifact to analyze"
    )
    forensic_instruction: str = Field(description="Instructions for the Detective")
    success_pattern: str = Field(description="Description of a score 5")
    failure_pattern: str = Field(description="Description of a score 0 or 1")


class SynthesisRules(BaseModel):
    """Rules for synthesizing judge opinions into final scores."""

    security_override: str
    fact_supremacy: str
    functionality_weight: str
    dissent_requirement: str
    variance_re_evaluation: str


class RubricMetadata(BaseModel):
    """Metadata about a rubric."""

    rubric_name: str
    grading_target: str
    version: str


class Rubric(BaseModel):
    """A complete rubric for code quality evaluation."""

    rubric_metadata: RubricMetadata
    dimensions: list[Dimension]
    synthesis_rules: SynthesisRules


# --- Judge Output ---


class JudicialOpinion(BaseModel):
    """A judge's opinion on a specific criterion."""

    judge: Literal["Prosecutor", "Defense", "TechLead"]
    criterion_id: str
    score: int = Field(ge=1, le=5)
    argument: str
    cited_evidence: list[str]


# --- Chief Justice Output ---


class CriterionResult(BaseModel):
    """Result for a single criterion after synthesizing judge opinions."""

    dimension_id: str
    dimension_name: str
    final_score: int = Field(ge=1, le=5)
    judge_opinions: list[JudicialOpinion]
    dissent_summary: str | None = Field(
        default=None,
        description="Required when score variance > 2",
    )
    remediation: str = Field(
        description="Specific file-level instructions for improvement",
    )


class AuditReport(BaseModel):
    """Final audit report summarizing the evaluation."""

    repo_url: str
    executive_summary: str
    overall_score: float
    criteria: list[CriterionResult]
    remediation_plan: str
