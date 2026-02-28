"""High-level tracing facade used by orchestration code."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from time import perf_counter
from typing import Any

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
    render_trace_event,
)
from codedueprocess.schemas.models import JudicialOpinion


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
            evidences = _extract_evidence_count(update)
            self.success(
                meta.layer,
                meta.display_name,
                f"Collected {evidences} evidences {duration_msg}",
            )
            return

        if node_name in {"prosecutor", "defense", "tech_lead"}:
            opinions = update.get("opinions", [])
            if isinstance(opinions, list) and opinions:
                opinion = opinions[-1]
                if isinstance(opinion, JudicialOpinion):
                    branch = (
                        EventBranch.END if node_name == "tech_lead" else EventBranch.MID
                    )
                    self.success(
                        meta.layer,
                        opinion.judge,
                        (
                            f"Score {opinion.score}/5 - "
                            f'"{opinion.argument}" {duration_msg}'
                        ),
                        branch=branch,
                    )
                else:
                    self.success(
                        meta.layer,
                        meta.display_name,
                        f"Opinion submitted {duration_msg}",
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
    evidences = update.get("evidences", {})
    if not isinstance(evidences, dict):
        return 0
    total = 0
    for value in evidences.values():
        if isinstance(value, list):
            total += len(value)
    return total
