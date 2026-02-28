"""Agent node factories."""

from codedueprocess.agents.chief import make_chief_justice_node
from codedueprocess.agents.detectives import (
    make_doc_analyst_node,
    make_repo_investigator_node,
    make_vision_inspector_node,
)
from codedueprocess.agents.judges import (
    build_judicial_opinion_chain,
    make_defense_node,
    make_judge_node,
    make_prosecutor_node,
    make_tech_lead_node,
)
from codedueprocess.agents.types import StateNode, StateUpdate

__all__ = [
    "build_judicial_opinion_chain",
    "make_chief_justice_node",
    "make_doc_analyst_node",
    "make_defense_node",
    "make_judge_node",
    "make_prosecutor_node",
    "make_repo_investigator_node",
    "make_tech_lead_node",
    "make_vision_inspector_node",
    "StateNode",
    "StateUpdate",
]
