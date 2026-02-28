"""LangGraph wiring for the Digital Courtroom flow."""

from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import Any, NotRequired, cast

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.runnables import RunnableLambda
from langgraph.graph import END, START, StateGraph
from typing_extensions import TypedDict

from codedueprocess.agents import (
    make_chief_justice_node,
    make_defense_node,
    make_doc_analyst_node,
    make_prosecutor_node,
    make_repo_investigator_node,
    make_tech_lead_node,
)
from codedueprocess.agents.types import StateNode
from codedueprocess.printing.tracer import AuditTracer
from codedueprocess.state import AgentState


@dataclass(frozen=True)
class AuditGraphModels:
    """Model dependencies for each graph node."""

    repo_investigator: BaseChatModel
    doc_analyst: BaseChatModel
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


def build_audit_graph(
    models: AuditGraphModels, tracer: AuditTracer | None = None
) -> Any:
    """Build the parallel detective -> judge -> chief justice topology."""
    builder = StateGraph(AgentState, context_schema=AuditRuntimeContext)

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
    builder.add_node(
        "chief_justice",
        _as_graph_node(
            "chief_justice",
            make_chief_justice_node(models.chief_justice),
            tracer,
        ),
    )

    builder.add_edge(START, "repo_investigator")
    builder.add_edge(START, "doc_analyst")

    builder.add_edge("repo_investigator", "prosecutor")
    builder.add_edge("repo_investigator", "defense")
    builder.add_edge("repo_investigator", "tech_lead")
    builder.add_edge("doc_analyst", "prosecutor")
    builder.add_edge("doc_analyst", "defense")
    builder.add_edge("doc_analyst", "tech_lead")

    builder.add_edge("prosecutor", "chief_justice")
    builder.add_edge("defense", "chief_justice")
    builder.add_edge("tech_lead", "chief_justice")

    builder.add_edge("chief_justice", END)
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
