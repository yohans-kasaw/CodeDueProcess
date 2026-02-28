"""Typed trace events and workflow metadata."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class AuditLayer(Enum):
    """High-level execution stages for rendering."""

    INGESTION = 0
    DETECTIVES = 1
    JUDGES = 2
    CHIEF = 3


@dataclass(frozen=True)
class LayerMeta:
    """Visual metadata for a workflow layer."""

    icon: str
    title: str


@dataclass(frozen=True)
class AgentMeta:
    """Metadata used to render per-agent lines."""

    layer: AuditLayer
    display_name: str


class EventKind(Enum):
    """Semantic kind of a trace line."""

    PROGRESS = "progress"
    SUCCESS = "success"
    FAILURE = "failure"


class EventBranch(Enum):
    """Tree branch style for event rendering."""

    MID = "mid"
    END = "end"


@dataclass(frozen=True)
class TraceEvent:
    """Event payload consumed by terminal renderers."""

    layer: AuditLayer
    agent: str
    message: str
    kind: EventKind
    branch: EventBranch


LAYER_META: dict[AuditLayer, LayerMeta] = {
    AuditLayer.INGESTION: LayerMeta(icon="📦", title="INGESTION"),
    AuditLayer.DETECTIVES: LayerMeta(icon="🕵️", title="DETECTIVES"),
    AuditLayer.JUDGES: LayerMeta(icon="⚖️", title="JUDGES (Git Forensic Analysis)"),
    AuditLayer.CHIEF: LayerMeta(icon="📊", title="CHIEF JUSTICE SYNTHESIS"),
}


AGENT_META: dict[str, AgentMeta] = {
    "repo_investigator": AgentMeta(
        layer=AuditLayer.DETECTIVES, display_name="RepoInvestigator"
    ),
    "doc_analyst": AgentMeta(layer=AuditLayer.DETECTIVES, display_name="DocAnalyst"),
    "prosecutor": AgentMeta(layer=AuditLayer.JUDGES, display_name="Prosecutor"),
    "defense": AgentMeta(layer=AuditLayer.JUDGES, display_name="Defense"),
    "tech_lead": AgentMeta(layer=AuditLayer.JUDGES, display_name="Tech Lead"),
    "chief_justice": AgentMeta(layer=AuditLayer.CHIEF, display_name="Chief Justice"),
}
