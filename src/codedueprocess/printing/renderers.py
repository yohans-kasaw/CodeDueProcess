"""Rendering helpers for audit tracing output."""

from __future__ import annotations

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from codedueprocess.printing.console import now_timestamp
from codedueprocess.printing.events import (
    AuditLayer,
    EventBranch,
    EventKind,
    LayerMeta,
    TraceEvent,
)
from codedueprocess.schemas.models import (
    AuditReport,
    Dimension,
    JudicialOpinion,
    RubricMetadata,
    SynthesisRules,
)


def render_audit_start(console: Console, repo_url: str) -> None:
    """Render a top-level audit start panel."""
    title = Text(f"🔍 AUDIT STARTED: {repo_url}", style="bold")
    panel = Panel.fit(
        title,
        border_style="layer",
        box=box.DOUBLE,
        padding=(0, 2),
    )
    console.print(panel)


def render_layer_header(console: Console, layer: AuditLayer, meta: LayerMeta) -> None:
    """Render a layer title row with timestamp."""
    console.print(
        f"[dimmed][{now_timestamp()}][/dimmed] "
        f"[layer]{meta.icon} LAYER {layer.value}: {meta.title}[/layer]"
    )


def render_trace_event(console: Console, event: TraceEvent) -> None:
    """Render one structured trace event line."""
    branch = "├─" if event.branch is EventBranch.MID else "└─"
    prefix = f"           {branch} [agent]{event.agent}[/agent]: "

    if event.kind is EventKind.PROGRESS:
        console.print(f"{prefix}{event.message}")
        return

    if event.kind is EventKind.SUCCESS:
        console.print(f"{prefix}[ok]✓[/] {event.message}")
        return

    console.print(f"{prefix}[error]✗[/] {event.message}")


def render_judge_opinion(console: Console, opinion: JudicialOpinion) -> None:
    """Render a judge score line."""
    console.print(
        "           └─ "
        f"[agent]{opinion.judge}[/agent]: "
        f'Score [metric]{opinion.score}/5[/metric] - "{opinion.argument}"'
    )


def render_chief_summary(
    console: Console, report: AuditReport, output_path: str
) -> None:
    """Render a compact final synthesis summary."""
    max_variance = _max_score_variance(report)
    variance_note = (
        "within tolerance" if max_variance <= 2 else "re-evaluation recommended"
    )

    table = Table(show_header=False, box=box.SIMPLE, pad_edge=False)
    table.add_column("k", style="agent")
    table.add_column("v")
    table.add_row("Score variance", f"{max_variance} point(s) ({variance_note})")
    table.add_row("Final Score", f"[metric]{report.overall_score:.1f}/5[/metric]")
    table.add_row("Criteria", str(len(report.criteria)))
    table.add_row("Output", output_path)

    panel = Panel(
        table,
        title="Chief Justice Synthesis",
        border_style="layer",
        box=box.ROUNDED,
    )
    console.print(panel)

    dimension_table = Table(title="Dimension Scores", box=box.SIMPLE_HEAVY)
    dimension_table.add_column("Dimension ID", style="agent")
    dimension_table.add_column("Name")
    dimension_table.add_column("Final Score", justify="right", style="metric")
    for criterion in report.criteria:
        dimension_table.add_row(
            criterion.dimension_id,
            criterion.dimension_name,
            str(criterion.final_score),
        )
    console.print(dimension_table)


def render_rubric_details(
    console: Console,
    metadata: RubricMetadata,
    dimensions: list[Dimension],
    synthesis_rules: SynthesisRules,
) -> None:
    """Render detailed rubric metadata and dimension requirements."""
    meta_table = Table(show_header=False, box=box.SIMPLE, pad_edge=False)
    meta_table.add_column("k", style="agent")
    meta_table.add_column("v")
    meta_table.add_row("Rubric", metadata.rubric_name)
    meta_table.add_row("Version", metadata.version)
    meta_table.add_row("Grading target", metadata.grading_target)

    rules_table = Table(show_header=False, box=box.SIMPLE, pad_edge=False)
    rules_table.add_column("rule", style="agent")
    rules_table.add_column("instruction")
    rules_table.add_row("security_override", synthesis_rules.security_override)
    rules_table.add_row("fact_supremacy", synthesis_rules.fact_supremacy)
    rules_table.add_row("functionality_weight", synthesis_rules.functionality_weight)
    rules_table.add_row("dissent_requirement", synthesis_rules.dissent_requirement)
    rules_table.add_row(
        "variance_re_evaluation", synthesis_rules.variance_re_evaluation
    )

    dim_table = Table(title="Rubric Dimensions", box=box.SIMPLE_HEAVY)
    dim_table.add_column("ID", style="agent")
    dim_table.add_column("Name")
    dim_table.add_column("Target")
    dim_table.add_column("Forensic Instruction")
    dim_table.add_column("Success Pattern")
    dim_table.add_column("Failure Pattern")
    for dimension in dimensions:
        dim_table.add_row(
            dimension.id,
            dimension.name,
            dimension.target_artifact,
            dimension.forensic_instruction,
            dimension.success_pattern,
            dimension.failure_pattern,
        )

    console.print(
        Panel(
            meta_table, title="Rubric Metadata", border_style="layer", box=box.ROUNDED
        )
    )
    console.print(
        Panel(
            rules_table, title="Synthesis Rules", border_style="layer", box=box.ROUNDED
        )
    )
    console.print(dim_table)


def _max_score_variance(report: AuditReport) -> int:
    max_variance = 0
    for criterion in report.criteria:
        scores = [opinion.score for opinion in criterion.judge_opinions]
        if not scores:
            continue
        variance = max(scores) - min(scores)
        max_variance = max(max_variance, variance)
    return max_variance
