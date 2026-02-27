"""CLI entrypoint for running the audit graph."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Iterator, Sequence
from itertools import cycle
from typing import Any, cast

from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda
from langchain_litellm import ChatLiteLLM

from src.codedueprocess.graph import AuditGraphModels, run_audit
from src.codedueprocess.schemas.models import AuditReport, Dimension
from src.codedueprocess.state import AgentState


class StructuredGenericFakeChatModel(GenericFakeChatModel):
    """Generic fake chat model with deterministic structured output parsing."""

    def with_structured_output(
        self, schema: Any, **_kwargs: Any
    ) -> RunnableLambda[Any, Any]:
        """Return a runnable that validates JSON payloads against a schema."""

        def _invoke(prompt_input: Any) -> Any:
            raw_message = self.invoke(prompt_input)
            if isinstance(raw_message.content, str):
                payload = raw_message.content
            else:
                payload = json.dumps(raw_message.content)
            return schema.model_validate_json(payload)

        return RunnableLambda(_invoke)


def _repeat_message(payload: str, count: int = 8) -> Iterator[AIMessage]:
    """Provide multiple deterministic responses for graph retries/replays."""
    del count
    return cycle([AIMessage(content=payload)])


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="codedueprocess",
        description="Run the Digital Courtroom audit graph.",
    )
    parser.add_argument("--repo-url", required=True, help="Repository URL under audit")
    parser.add_argument("--repo-path", default=".", help="Local repository path")
    parser.add_argument("--docs-path", default="docs", help="Local docs path")
    parser.add_argument("--pdf-path", default="", help="Optional external report path")
    parser.add_argument(
        "--mode",
        choices=("mock", "real"),
        default="mock",
        help="Use deterministic mock mode or real provider-backed LLM mode",
    )
    parser.add_argument(
        "--model",
        default="openai/gpt-4.1-mini",
        help="LiteLLM model id for real mode",
    )
    parser.add_argument("--thread-id", default="cli-thread", help="Trace thread id")
    parser.add_argument(
        "--active-model-profile",
        default="mock-profile",
        help="Runtime model profile metadata",
    )
    return parser


def _default_dimension() -> Dimension:
    return Dimension(
        id="git_history",
        name="Git History",
        target_artifact="github_repo",
        forensic_instruction="Evaluate commit quality and traceability.",
        success_pattern="Frequent meaningful commits with clear rationale.",
        failure_pattern="Sparse noisy commits with weak traceability.",
    )


def _initial_state(args: argparse.Namespace) -> AgentState:
    return cast(
        AgentState,
        {
            "repo_url": args.repo_url,
            "repo_path": args.repo_path,
            "docs_path": args.docs_path,
            "pdf_path": args.pdf_path,
            "rubric_dimensions": [_default_dimension()],
            "evidences": {},
            "opinions": [],
        },
    )


def _mock_models() -> AuditGraphModels:
    repo_payload = (
        '{"evidences":[{"goal":"Track commit quality","found":true,'
        '"content":"12 commits with meaningful messages",'
        '"location":".git/logs","rationale":"History is descriptive",'
        '"confidence":0.92}]}'
    )
    doc_payload = (
        '{"evidences":[{"goal":"Validate architecture claim","found":true,'
        '"content":"Architecture describes layered DAG",'
        '"location":"docs/architecture.md:16",'
        '"rationale":"Claim is explicit in documentation",'
        '"confidence":0.88}]}'
    )
    prosecutor_payload = (
        '{"judge":"Prosecutor","criterion_id":"git_history","score":4,'
        '"argument":"Commit history shows deliberate progress.",'
        '"cited_evidence":["repo:commits", "docs:milestones"]}'
    )
    defense_payload = (
        '{"judge":"Defense","criterion_id":"git_history","score":3,'
        '"argument":"Repository demonstrates partial requirement coverage.",'
        '"cited_evidence":["repo:modules", "docs:claims"]}'
    )
    techlead_payload = (
        '{"judge":"TechLead","criterion_id":"git_history","score":4,'
        '"argument":"Architecture is maintainable with minor caveats.",'
        '"cited_evidence":["repo:tree", "doc:architecture"]}'
    )
    report_payload = (
        '{"repo_url":"https://github.com/example/repo",'
        '"executive_summary":"Overall implementation is on track.",'
        '"overall_score":4.1,'
        '"criteria":[{"dimension_id":"git_history",'
        '"dimension_name":"Git History",'
        '"final_score":4,'
        '"judge_opinions":[{"judge":"TechLead","criterion_id":"git_history",'
        '"score":4,"argument":"Consistent progress.",'
        '"cited_evidence":["repo:.git/logs"]}],'
        '"dissent_summary":null,'
        '"remediation":"Keep commit messages descriptive."}],'
        '"remediation_plan":"Address medium-priority findings in next sprint."}'
    )

    return AuditGraphModels(
        repo_investigator=StructuredGenericFakeChatModel(
            messages=_repeat_message(repo_payload)
        ),
        doc_analyst=StructuredGenericFakeChatModel(
            messages=_repeat_message(doc_payload)
        ),
        prosecutor=StructuredGenericFakeChatModel(
            messages=_repeat_message(prosecutor_payload)
        ),
        defense=StructuredGenericFakeChatModel(
            messages=_repeat_message(defense_payload)
        ),
        tech_lead=StructuredGenericFakeChatModel(
            messages=_repeat_message(techlead_payload)
        ),
        chief_justice=StructuredGenericFakeChatModel(
            messages=_repeat_message(report_payload)
        ),
    )


def _real_models(model_name: str) -> AuditGraphModels:
    llm = ChatLiteLLM(model=model_name, temperature=0)
    return AuditGraphModels.from_single(llm)


def run(argv: Sequence[str] | None = None) -> int:
    """Run CLI and return process exit code."""
    parser = _build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)

    models = _mock_models() if args.mode == "mock" else _real_models(args.model)
    state = _initial_state(args)

    try:
        result = run_audit(
            models=models,
            state=state,
            context={
                "thread_id": args.thread_id,
                "active_model_profile": args.active_model_profile,
            },
        )
    except Exception as exc:  # noqa: BLE001
        print(f"Audit failed: {exc}", file=sys.stderr)
        return 1

    final_report = cast(AuditReport, result["final_report"])
    print("Audit completed.")
    print(f"Overall score: {final_report.overall_score}")
    print("Final report JSON:")
    print(final_report.model_dump_json(indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
