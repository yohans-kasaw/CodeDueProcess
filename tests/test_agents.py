"""Step 1 contract tests for LLM abstraction and mock verification."""

from __future__ import annotations

from typing import cast, get_type_hints

import pytest
from langchain_core.language_models.chat_models import BaseChatModel
from pydantic import ValidationError

from src.codedueprocess.agents.chief import make_chief_justice_node
from src.codedueprocess.agents.detectives import (
    make_doc_analyst_node,
    make_repo_investigator_node,
)
from src.codedueprocess.agents.judges import (
    build_judicial_opinion_chain,
    make_defense_node,
    make_judge_node,
    make_prosecutor_node,
    make_tech_lead_node,
)
from src.codedueprocess.schemas.models import Dimension, JudicialOpinion
from src.codedueprocess.state import AgentState


def _base_state() -> AgentState:
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


def test_agent_factories_accept_base_chat_model_annotation() -> None:
    """All agent factories should declare `BaseChatModel` dependency injection."""
    factories = [
        make_repo_investigator_node,
        make_doc_analyst_node,
        make_judge_node,
        make_chief_justice_node,
    ]
    for factory in factories:
        llm_annotation = get_type_hints(factory)["llm"]
        assert llm_annotation is BaseChatModel


def test_contract_structured_output_with_judicial_opinion(
    mockllm_judicial_opinion,
) -> None:
    """Configured mock model supports structured output for JudicialOpinion schema."""
    chain = build_judicial_opinion_chain(mockllm_judicial_opinion)
    opinion = chain.invoke("Provide a judicial opinion")

    assert isinstance(opinion, JudicialOpinion)
    assert opinion.judge == "Prosecutor"
    assert opinion.criterion_id == "git_history"


def test_malformed_structured_output_raises_validation_error(
    mockllm_malformed_judicial_opinion,
) -> None:
    """Malformed fake responses should fail schema validation."""
    chain = build_judicial_opinion_chain(mockllm_malformed_judicial_opinion)

    with pytest.raises(ValidationError):
        chain.invoke("Provide a judicial opinion")


def test_judge_node_appends_opinion(mockllm_judicial_opinion) -> None:
    """Judge node returns reducer-friendly opinion updates."""
    node = make_judge_node(mockllm_judicial_opinion, "Prosecutor")

    update = node(_base_state())

    assert "opinions" in update
    assert len(update["opinions"]) == 1
    assert update["opinions"][0].judge == "Prosecutor"


def test_parameterized_judge_factories_emit_expected_roles(
    mockllm_judicial_opinion,
    mockllm_defense_opinion,
    mockllm_techlead_opinion,
) -> None:
    """Role-specific judge factories should produce deterministic role outputs."""
    state = _base_state()

    prosecutor_update = make_prosecutor_node(mockllm_judicial_opinion)(state)
    defense_update = make_defense_node(mockllm_defense_opinion)(state)
    techlead_update = make_tech_lead_node(mockllm_techlead_opinion)(state)

    assert prosecutor_update["opinions"][0].judge == "Prosecutor"
    assert defense_update["opinions"][0].judge == "Defense"
    assert techlead_update["opinions"][0].judge == "TechLead"


def test_detective_nodes_return_partial_state_updates(
    mockllm_repo_evidence,
    mockllm_doc_evidence,
) -> None:
    """Detective nodes should only emit `evidences` updates."""
    repo_node = make_repo_investigator_node(mockllm_repo_evidence)
    doc_node = make_doc_analyst_node(mockllm_doc_evidence)
    state = _base_state()

    repo_update = repo_node(state)
    doc_update = doc_node(state)

    assert set(repo_update.keys()) == {"evidences"}
    assert set(doc_update.keys()) == {"evidences"}
    assert "repository_facts" in repo_update["evidences"]
    assert "claim_set" in doc_update["evidences"]


def test_chief_node_returns_final_report_partial_update(mockllm_audit_report) -> None:
    """Chief justice node should only emit `final_report` update."""
    node = make_chief_justice_node(mockllm_audit_report)
    state = _base_state()
    state["evidences"] = {
        "repository_facts": [],
        "claim_set": [],
    }
    state["opinions"] = [
        JudicialOpinion(
            judge="TechLead",
            criterion_id="git_history",
            score=4,
            argument="Sufficient for synthesis.",
            cited_evidence=["repo:commits"],
        )
    ]

    update = node(state)

    assert set(update.keys()) == {"final_report"}
    assert update["final_report"].overall_score == 4.1


def test_judge_node_fails_with_actionable_message_on_empty_rubric(
    mockllm_judicial_opinion,
) -> None:
    """Judge node should fail fast when rubric dimensions are missing."""
    node = make_prosecutor_node(mockllm_judicial_opinion)
    state = _base_state()
    state["rubric_dimensions"] = []

    with pytest.raises(ValueError, match="rubric_dimensions is required"):
        node(state)


def test_chief_node_fails_with_actionable_message_on_missing_evidence(
    mockllm_audit_report,
) -> None:
    """Chief node should fail fast when no detective evidence is present."""
    node = make_chief_justice_node(mockllm_audit_report)
    state = _base_state()
    state["evidences"] = {}
    state["opinions"] = []

    with pytest.raises(ValueError, match="evidences is required"):
        node(state)
