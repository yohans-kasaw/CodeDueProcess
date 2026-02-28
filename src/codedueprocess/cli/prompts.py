"""Interactive prompt helpers for CLI execution."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from rich.panel import Panel
from rich.prompt import Confirm, Prompt

from codedueprocess.printing.console import console


@dataclass(frozen=True)
class RunInputs:
    """Input values collected from an interactive terminal session."""

    provider: str
    repo_url: str | None
    repo_path: str | None
    model: str | None
    report_path: str | None
    rubric_path: str


def prompt_for_run_inputs(default_rubric_path: str) -> RunInputs:
    """Collect run configuration from user prompts."""
    console.print(
        Panel.fit(
            "Configure your audit run",
            title="CodeDueProcess",
            border_style="layer",
        )
    )

    provider = Prompt.ask(
        "Select provider",
        choices=["openai", "gemini"],
        default="gemini",
    )

    source_mode = Prompt.ask(
        "Repository source",
        choices=["url", "path"],
        default="path",
    )

    repo_url: str | None = None
    repo_path: str | None = None
    if source_mode == "url":
        repo_url = _prompt_github_url()
    else:
        repo_path = _prompt_local_repo_path()

    model: str | None = None
    if Confirm.ask("Use a custom model name?", default=False):
        model_value = Prompt.ask("Model name", default="").strip()
        model = model_value or None

    report_path: str | None = None
    if Confirm.ask("Provide a report path inside the repo?", default=False):
        report_value = Prompt.ask("Report path", default="").strip()
        report_path = report_value or None

    rubric = Prompt.ask("Rubric path", default=default_rubric_path).strip()
    rubric_path = rubric or default_rubric_path

    return RunInputs(
        provider=provider,
        repo_url=repo_url,
        repo_path=repo_path,
        model=model,
        report_path=report_path,
        rubric_path=rubric_path,
    )


def _prompt_github_url() -> str:
    while True:
        value = Prompt.ask("GitHub repository URL").strip()
        if _is_github_url(value):
            return value
        console.print(
            "[error]Please enter a valid GitHub URL, for example: "
            "https://github.com/user/repo[/error]"
        )


def _prompt_local_repo_path() -> str:
    while True:
        value = Prompt.ask("Local repository path").strip()
        if not value:
            console.print("[error]Path cannot be empty[/error]")
            continue

        path = Path(value).expanduser().resolve()
        if path.exists() and path.is_dir():
            return str(path)

        console.print(
            f"[error]Directory not found: {path}. Enter a valid local path.[/error]"
        )


def _is_github_url(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return False
    if parsed.netloc.lower() not in {"github.com", "www.github.com"}:
        return False
    path_parts = [part for part in parsed.path.split("/") if part]
    return len(path_parts) >= 2
