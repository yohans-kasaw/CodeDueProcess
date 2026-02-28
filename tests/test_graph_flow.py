"""Integration tests for LangGraph orchestration flow."""

from __future__ import annotations

from typing import cast

import pytest
from langsmith import testing as t
from pydantic import ValidationError

from src.codedueprocess.graph import AuditGraphModels, build_audit_graph, run_audit
from src.codedueprocess.schemas.models import AuditReport, Dimension
from src.codedueprocess.state import AgentState


def _graph_state() -> AgentState:
    return cast(
        AgentState,
        {
            "repo_url": "https://github.com/example/repo",
            "pdf_path": "docs/report.pdf",
            "repo_path": "/tmp/repos/example-repo",
            "docs_path": "/tmp/repos/example-repo/docs",
            "rubric_dimensions": [
                Dimension(
                    id="git_history",
                    name="Git History",
                    target_artifact="github_repo",
                    forensic_instruction="Analyze commit quality",
                    success_pattern="Frequent meaningful commits",
                    failure_pattern="Sparse noisy commits",
                )
            ],
            "evidences": {},
            "opinions": [],
        },
    )


@pytest.mark.langsmith
def test_graph_flow_produces_final_report_and_aggregates_parallel_outputs(
    mockllm_repo_evidence,
    mockllm_doc_evidence,
    mockllm_judicial_opinion,
    mockllm_defense_opinion,
    mockllm_techlead_opinion,
    mockllm_audit_report,
) -> None:
    """Graph should fan out/fan in and preserve reducer-backed updates."""
    graph = build_audit_graph(
        AuditGraphModels(
            repo_investigator=mockllm_repo_evidence,
            doc_analyst=mockllm_doc_evidence,
            prosecutor=mockllm_judicial_opinion,
            defense=mockllm_defense_opinion,
            tech_lead=mockllm_techlead_opinion,
            chief_justice=mockllm_audit_report,
        )
    )

    state = _graph_state()
    t.log_inputs(
        {
            "repo_url": state["repo_url"],
            "dimensions": [d.id for d in state["rubric_dimensions"]],
        }
    )
    result = graph.invoke(state)
    final_report = cast(AuditReport, result["final_report"])
    t.log_outputs(
        {
            "overall_score": final_report.overall_score,
            "opinions_count": len(result["opinions"]),
        }
    )
    t.log_reference_outputs({"opinions_count": 3})

    assert final_report.overall_score == 4.1
    assert "repository_facts" in result["evidences"]
    assert "claim_set" in result["evidences"]
    assert len(result["opinions"]) == 3
    assert {opinion.judge for opinion in result["opinions"]} == {
        "Prosecutor",
        "Defense",
        "TechLead",
    }


@pytest.mark.langsmith
def test_run_audit_boundary_is_invocable(
    mockllm_repo_evidence,
    mockllm_doc_evidence,
    mockllm_judicial_opinion,
    mockllm_defense_opinion,
    mockllm_techlead_opinion,
    mockllm_audit_report,
) -> None:
    """Top-level orchestration boundary should run with traceable wrapper."""
    models = AuditGraphModels(
        repo_investigator=mockllm_repo_evidence,
        doc_analyst=mockllm_doc_evidence,
        prosecutor=mockllm_judicial_opinion,
        defense=mockllm_defense_opinion,
        tech_lead=mockllm_techlead_opinion,
        chief_justice=mockllm_audit_report,
    )
    result = run_audit(models=models, state=_graph_state())
    final_report = cast(AuditReport, result["final_report"])
    t.log_outputs({"boundary_score": final_report.overall_score})

    assert final_report.overall_score == 4.1


def test_compiled_node_invocation_for_repo_investigator(mockllm_repo_evidence) -> None:
    """Compiled node invocation works for isolated node semantics."""
    graph = build_audit_graph(
        AuditGraphModels.from_single(mockllm_repo_evidence),
    )

    update = graph.nodes["repo_investigator"].invoke(_graph_state())

    assert set(update.keys()) == {"evidences"}
    assert "repository_facts" in update["evidences"]


def test_graph_surfaces_invalid_structured_output_error(
    mockllm_repo_evidence,
    mockllm_doc_evidence,
    mockllm_malformed_judicial_opinion,
    mockllm_defense_opinion,
    mockllm_techlead_opinion,
    mockllm_audit_report,
) -> None:
    """Graph should raise when a judge returns invalid structured output."""
    graph = build_audit_graph(
        AuditGraphModels(
            repo_investigator=mockllm_repo_evidence,
            doc_analyst=mockllm_doc_evidence,
            prosecutor=mockllm_malformed_judicial_opinion,
            defense=mockllm_defense_opinion,
            tech_lead=mockllm_techlead_opinion,
            chief_justice=mockllm_audit_report,
        )
    )

    with pytest.raises(ValidationError):
        graph.invoke(_graph_state())
