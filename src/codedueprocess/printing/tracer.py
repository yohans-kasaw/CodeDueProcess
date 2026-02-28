"""High-level tracing facade used by orchestration code."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from time import perf_counter
from typing import Any
from uuid import UUID

from langchain_core.callbacks import BaseCallbackHandler
from rich.console import Console

from codedueprocess.printing.console import console as default_console
from codedueprocess.printing.events import (
    AGENT_META,
    LAYER_META,
    AuditLayer,
    EventBranch,
    EventKind,
    TraceEvent,
)
from codedueprocess.printing.renderers import (
    render_audit_start,
    render_chief_summary,
    render_layer_header,
    render_rubric_details,
    render_trace_event,
)
from codedueprocess.schemas.models import (
    Dimension,
    Evidence,
    JudicialOpinion,
    RubricMetadata,
    SynthesisRules,
)


class AuditTracer:
    """Facade for rendering observability events to the terminal."""

    def __init__(self, rich_console: Console | None = None) -> None:
        """Initialize tracer with an optional Rich console instance."""
        self._console = rich_console or default_console
        self._rendered_layers: set[AuditLayer] = set()

    def audit_started(self, repo_url: str) -> None:
        """Render the audit start banner."""
        render_audit_start(self._console, repo_url)

    def layer_started(self, layer: AuditLayer) -> None:
        """Render a layer header once."""
        if layer in self._rendered_layers:
            return
        render_layer_header(self._console, layer, LAYER_META[layer])
        self._rendered_layers.add(layer)

    def rubric_details(
        self,
        metadata: RubricMetadata,
        dimensions: list[Dimension],
        synthesis_rules: SynthesisRules,
    ) -> None:
        """Render detailed rubric context for current run."""
        self.layer_started(AuditLayer.INGESTION)
        render_rubric_details(self._console, metadata, dimensions, synthesis_rules)

    def info(
        self,
        layer: AuditLayer,
        agent: str,
        message: str,
        *,
        branch: EventBranch = EventBranch.MID,
    ) -> None:
        """Render an informational in-progress line."""
        self.layer_started(layer)
        self._emit(
            TraceEvent(
                layer=layer,
                agent=agent,
                message=message,
                kind=EventKind.PROGRESS,
                branch=branch,
            )
        )

    def success(
        self,
        layer: AuditLayer,
        agent: str,
        message: str,
        *,
        branch: EventBranch = EventBranch.END,
    ) -> None:
        """Render a success line."""
        self.layer_started(layer)
        self._emit(
            TraceEvent(
                layer=layer,
                agent=agent,
                message=message,
                kind=EventKind.SUCCESS,
                branch=branch,
            )
        )

    def failure(
        self,
        layer: AuditLayer,
        agent: str,
        message: str,
        *,
        branch: EventBranch = EventBranch.END,
    ) -> None:
        """Render a failure line."""
        self.layer_started(layer)
        self._emit(
            TraceEvent(
                layer=layer,
                agent=agent,
                message=message,
                kind=EventKind.FAILURE,
                branch=branch,
            )
        )

    @contextmanager
    def live_status(
        self, layer: AuditLayer, agent: str, message: str
    ) -> Iterator[None]:
        """Render spinner status for long-running work."""
        self.layer_started(layer)
        with self._console.status(f"[agent]{agent}[/agent]: {message}", spinner="dots"):
            yield

    def begin_node(self, node_name: str) -> float:
        """Render node start and return start time."""
        meta = AGENT_META.get(node_name)
        if meta is None:
            return perf_counter()
        self.info(meta.layer, meta.display_name, "Running...")
        return perf_counter()

    def tools_loaded(self, node_name: str, tool_names: list[str]) -> None:
        """Render the set of tools loaded for an agent node."""
        meta = AGENT_META.get(node_name)
        if meta is None:
            return
        tools_label = ", ".join(tool_names) if tool_names else "none"
        self.info(meta.layer, meta.display_name, f"Tools loaded: {tools_label}")

    def end_node(
        self, node_name: str, update: dict[str, object], started_at: float
    ) -> None:
        """Render node completion with useful metrics."""
        meta = AGENT_META.get(node_name)
        if meta is None:
            return

        duration = perf_counter() - started_at
        duration_msg = f"({duration:.1f}s)"

        if node_name in {"repo_investigator", "doc_analyst"}:
            evidence_items = _extract_evidences(update)
            for evidence in evidence_items:
                summary = evidence.content or evidence.goal
                self.info(
                    meta.layer,
                    meta.display_name,
                    f"Evidence: {summary} @ {evidence.location}",
                    branch=EventBranch.MID,
                )
            self.success(
                meta.layer,
                meta.display_name,
                f"Collected {len(evidence_items)} evidences {duration_msg}",
            )
            return

        if node_name in {"prosecutor", "defense", "tech_lead"}:
            opinions = update.get("opinions", [])
            if isinstance(opinions, list) and opinions:
                judge_opinions = [
                    opinion
                    for opinion in opinions
                    if isinstance(opinion, JudicialOpinion)
                    and _node_to_judge(node_name) == opinion.judge
                ]
                for opinion in judge_opinions:
                    self.info(
                        meta.layer,
                        opinion.judge,
                        (f"Dimension {opinion.criterion_id}: Score {opinion.score}/5"),
                        branch=EventBranch.MID,
                    )
                self.success(
                    meta.layer,
                    meta.display_name,
                    f"Scored {len(judge_opinions)} dimensions {duration_msg}",
                )
            else:
                self.success(
                    meta.layer, meta.display_name, f"Opinion submitted {duration_msg}"
                )
            return

        if node_name == "chief_justice":
            report = update.get("final_report")
            if report is not None:
                self.success(
                    meta.layer, meta.display_name, f"Synthesis complete {duration_msg}"
                )
            return

        self.success(meta.layer, meta.display_name, f"Done {duration_msg}")

    def fail_node(self, node_name: str, error: Exception) -> None:
        """Render node failure details."""
        meta = AGENT_META.get(node_name)
        if meta is None:
            return
        self.failure(meta.layer, meta.display_name, str(error))

    def chief_summary(self, report: Any, output_path: str) -> None:
        """Render final scorecard if an AuditReport-like object is present."""
        if report is None:
            return
        self.layer_started(AuditLayer.CHIEF)
        render_chief_summary(self._console, report, output_path)

    def _emit(self, event: TraceEvent) -> None:
        render_trace_event(self._console, event)


def _extract_evidence_count(update: dict[str, object]) -> int:
    return len(_extract_evidences(update))


def _extract_evidences(update: dict[str, object]) -> list[Evidence]:
    evidences = update.get("evidences", {})
    if not isinstance(evidences, dict):
        return []
    collected: list[Evidence] = []
    for value in evidences.values():
        if isinstance(value, list):
            for item in value:
                if isinstance(item, Evidence):
                    collected.append(item)
    return collected


class ToolLifecycleCallback(BaseCallbackHandler):
    """Render tool lifecycle events through the audit tracer."""

    def __init__(self, tracer: AuditTracer, node_name: str) -> None:
        """Initialize callback handler for a specific graph node."""
        self._tracer = tracer
        self._meta = AGENT_META.get(node_name)
        self._tools_by_run: dict[UUID, str] = {}

    def on_tool_start(
        self,
        serialized: dict[str, Any],
        input_str: str,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        inputs: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> Any:
        """Render a tool start event with its name and raw input."""
        del parent_run_id, tags, metadata, inputs, kwargs
        if self._meta is None:
            return None
        tool_name = (
            serialized.get("name")
            or serialized.get("id")
            or serialized.get("lc")
            or "unknown"
        )
        self._tools_by_run[run_id] = str(tool_name)
        self._tracer.info(
            self._meta.layer,
            self._meta.display_name,
            f"Tool start: {tool_name} | args: {input_str}",
        )
        return None

    def on_tool_end(
        self,
        output: Any,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        **kwargs: Any,
    ) -> Any:
        """Render successful completion for a previously started tool."""
        del parent_run_id, kwargs, output
        if self._meta is None:
            return None
        tool_name = self._tools_by_run.pop(run_id, "unknown")
        self._tracer.success(
            self._meta.layer,
            self._meta.display_name,
            f"Tool done: {tool_name}",
            branch=EventBranch.MID,
        )
        return None

    def on_tool_error(
        self,
        error: BaseException,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        **kwargs: Any,
    ) -> Any:
        """Render a tool failure event and include the error."""
        del parent_run_id, kwargs
        if self._meta is None:
            return None
        tool_name = self._tools_by_run.pop(run_id, "unknown")
        self._tracer.failure(
            self._meta.layer,
            self._meta.display_name,
            f"Tool failed: {tool_name} ({error})",
            branch=EventBranch.MID,
        )
        return None


def _node_to_judge(node_name: str) -> str:
    if node_name == "prosecutor":
        return "Prosecutor"
    if node_name == "defense":
        return "Defense"
    if node_name == "tech_lead":
        return "TechLead"
    return ""
