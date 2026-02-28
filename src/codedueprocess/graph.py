"""LangGraph wiring for the Digital Courtroom flow with aggregation and error handling."""

from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import Any, NotRequired, cast

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.runnables import RunnableConfig, RunnableLambda
from langchain_litellm import ChatLiteLLM
from langgraph.graph import END, START, StateGraph
from typing_extensions import TypedDict

from codedueprocess.agents import (
    make_chief_justice_node,
    make_defense_node,
    make_doc_analyst_node,
    make_prosecutor_node,
    make_repo_investigator_node,
    make_tech_lead_node,
    make_vision_inspector_node,
)
from codedueprocess.agents.types import StateNode
from codedueprocess.printing.tracer import AuditTracer
from codedueprocess.state import AgentState

DEFAULT_MODEL_NAME = "gemini/gemini-2.5-flash"


@dataclass(frozen=True)
class AuditGraphModels:
    """Model dependencies for each graph node."""

    repo_investigator: BaseChatModel
    doc_analyst: BaseChatModel
    vision_inspector: BaseChatModel
    prosecutor: BaseChatModel
    defense: BaseChatModel
    tech_lead: BaseChatModel
    chief_justice: BaseChatModel

    @classmethod
    def from_single(cls, llm: BaseChatModel) -> AuditGraphModels:
        """Use one model instance for all nodes."""
        return cls(
            repo_investigator=llm,
            doc_analyst=llm,
            vision_inspector=llm,
            prosecutor=llm,
            defense=llm,
            tech_lead=llm,
            chief_justice=llm,
        )


class AuditRuntimeContext(TypedDict):
    """Runtime context schema for optional invocation metadata."""

    active_model_profile: NotRequired[str]
    thread_id: NotRequired[str]
    trace_id: NotRequired[str]


def aggregate_evidence_node(state: AgentState) -> dict[str, object]:
    """Aggregation node that syncs all evidence before judging.

    This node ensures all detectives have completed and aggregates
    their evidence into a unified catalog for the judges.
    """
    evidences = state.get("evidences", {})

    # Count evidence from each detective
    repo_facts = evidences.get("repository_facts", [])
    claim_set = evidences.get("claim_set", [])
    visual_artifacts = evidences.get("visual_artifacts", [])

    total_evidence = len(repo_facts) + len(claim_set) + len(visual_artifacts)

    if total_evidence == 0:
        return {
            "error": "No evidence collected. All detective nodes failed.",
            "aggregation_status": "failed",
        }

    return {
        "aggregation_status": "success",
        "total_evidence": total_evidence,
        "evidence_breakdown": {
            "repository_facts": len(repo_facts),
            "claim_set": len(claim_set),
            "visual_artifacts": len(visual_artifacts),
        },
    }


def check_detective_failure(state: AgentState) -> str:
    """Conditional edge router to check if detective phase failed."""
    status = state.get("aggregation_status", "")
    if status == "failed":
        return "error"
    return "continue"


def check_chief_failure(state: AgentState) -> str:
    """Conditional edge router to check if chief justice synthesis failed."""
    final_report = state.get("final_report")
    if final_report is None:
        return "error"
    return "end"


def error_node(state: AgentState) -> dict[str, object]:
    """Error handling node that provides diagnostic information."""
    error_msg = state.get("error", "Unknown error occurred")
    return {"error": error_msg, "final_report": None}


def build_audit_graph(
    models: AuditGraphModels, tracer: AuditTracer | None = None
) -> Any:
    """Build the parallel detective -> aggregation -> judge -> chief justice topology.

    Flow: START -> Detectives (Parallel) -> Aggregation -> Judges (Parallel) -> Chief Justice -> END
    """
    builder = StateGraph(AgentState, context_schema=AuditRuntimeContext)

    # Detective nodes - parallel fan-out
    builder.add_node(
        "repo_investigator",
        _as_graph_node(
            "repo_investigator",
            make_repo_investigator_node(models.repo_investigator, tracer=tracer),
            tracer,
        ),
    )
    builder.add_node(
        "doc_analyst",
        _as_graph_node(
            "doc_analyst",
            make_doc_analyst_node(models.doc_analyst, tracer=tracer),
            tracer,
        ),
    )
    builder.add_node(
        "vision_inspector",
        _as_graph_node(
            "vision_inspector",
            make_vision_inspector_node(models.vision_inspector, tracer=tracer),
            tracer,
        ),
    )

    # Aggregation node - synchronizes evidence before judging
    builder.add_node(
        "aggregate_evidence",
        _as_graph_node("aggregate_evidence", aggregate_evidence_node, tracer),
    )

    # Judge nodes - parallel fan-out
    builder.add_node(
        "prosecutor",
        _as_graph_node("prosecutor", make_prosecutor_node(models.prosecutor), tracer),
    )
    builder.add_node(
        "defense", _as_graph_node("defense", make_defense_node(models.defense), tracer)
    )
    builder.add_node(
        "tech_lead",
        _as_graph_node("tech_lead", make_tech_lead_node(models.tech_lead), tracer),
    )

    # Chief Justice and Error nodes
    builder.add_node(
        "chief_justice",
        _as_graph_node(
            "chief_justice",
            make_chief_justice_node(models.chief_justice),
            tracer,
        ),
    )
    builder.add_node(
        "error_handler",
        _as_graph_node("error_handler", error_node, tracer),
    )

    # Phase 1: Parallel detectives from START
    builder.add_edge(START, "repo_investigator")
    builder.add_edge(START, "doc_analyst")
    builder.add_edge(START, "vision_inspector")

    # Phase 2: All detectives feed into aggregation
    builder.add_edge("repo_investigator", "aggregate_evidence")
    builder.add_edge("doc_analyst", "aggregate_evidence")
    builder.add_edge("vision_inspector", "aggregate_evidence")

    # Phase 3: Conditional routing from aggregation
    builder.add_conditional_edges(
        "aggregate_evidence",
        check_detective_failure,
        {
            "continue": "prosecutor",
            "error": "error_handler",
        },
    )

    # Phase 4: Parallel judges from aggregation (on success)
    builder.add_edge("aggregate_evidence", "prosecutor")
    builder.add_edge("aggregate_evidence", "defense")
    builder.add_edge("aggregate_evidence", "tech_lead")

    # Phase 5: All judges feed into chief justice
    builder.add_edge("prosecutor", "chief_justice")
    builder.add_edge("defense", "chief_justice")
    builder.add_edge("tech_lead", "chief_justice")

    # Phase 6: Error handling and END
    builder.add_conditional_edges(
        "chief_justice",
        check_chief_failure,
        {
            "end": END,
            "error": "error_handler",
        },
    )
    builder.add_edge("error_handler", END)

    return builder.compile()


def _as_graph_node(
    node_name: str,
    node: StateNode,
    tracer: AuditTracer | None,
) -> RunnableLambda[AgentState, dict[str, object]]:
    """Adapt agent node callables to LangGraph's node protocol typing."""

    def wrapped(state: AgentState) -> dict[str, object]:
        start = perf_counter()
        if tracer is not None:
            start = tracer.begin_node(node_name)
        try:
            result = cast(dict[str, object], node(state))
            if tracer is not None:
                tracer.end_node(node_name, result, start)
            return result
        except Exception as exc:
            if tracer is not None:
                tracer.fail_node(node_name, exc)
            raise

    return RunnableLambda(wrapped)


def run_audit(
    models: AuditGraphModels,
    state: AgentState,
    context: AuditRuntimeContext | None = None,
) -> AgentState:
    """Execute the audit graph and return the final graph state."""
    tracer = AuditTracer()
    graph = build_audit_graph(models, tracer=tracer)
    if context is None:
        return cast(AgentState, graph.invoke(state))
    return cast(AgentState, graph.invoke(state, context=context))


def make_graph(config: RunnableConfig) -> Any:
    """Build a deployable graph instance for LangGraph server runtimes."""
    configurable = config.get("configurable", {})
    model_name = DEFAULT_MODEL_NAME
    if isinstance(configurable, dict):
        configured_model = configurable.get("model")
        if isinstance(configured_model, str) and configured_model.strip():
            model_name = configured_model

    llm = ChatLiteLLM(model=model_name, temperature=0)
    models = AuditGraphModels.from_single(llm)
    return build_audit_graph(models, tracer=AuditTracer())
