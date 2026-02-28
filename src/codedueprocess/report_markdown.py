"""Markdown rendering helpers for final audit reports."""

from __future__ import annotations

from codedueprocess.schemas.models import AuditReport


def render_report_markdown(report: AuditReport) -> str:
    """Render an AuditReport as human-readable markdown."""
    lines: list[str] = [
        "# Audit Report",
        "",
        f"- Repository: `{report.repo_url}`",
        f"- Overall score: **{report.overall_score:.1f}/5**",
        "",
        "## Executive Summary",
        "",
        report.executive_summary,
        "",
        "## Dimension Scores",
        "",
        "| Dimension ID | Name | Final Score |",
        "| --- | --- | ---: |",
    ]

    for criterion in report.criteria:
        lines.append(
            f"| `{criterion.dimension_id}` | {criterion.dimension_name} "
            f"| {criterion.final_score}/5 |"
        )

    lines.extend(["", "## Criteria Details", ""])

    for criterion in report.criteria:
        lines.extend(
            [
                f"### {criterion.dimension_name} (`{criterion.dimension_id}`)",
                "",
                f"- Final score: **{criterion.final_score}/5**",
                f"- Remediation: {criterion.remediation}",
            ]
        )

        if criterion.dissent_summary:
            lines.append(f"- Dissent summary: {criterion.dissent_summary}")

        lines.extend(["", "Judge opinions:"])
        for opinion in criterion.judge_opinions:
            cited = ", ".join(opinion.cited_evidence)
            lines.append(
                f"- **{opinion.judge}** ({opinion.score}/5): {opinion.argument} "
                f"[cited: {cited}]"
            )
        lines.append("")

    lines.extend(["## Remediation Plan", "", report.remediation_plan, ""])
    return "\n".join(lines)
