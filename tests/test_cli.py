"""CLI tests for mock and argument behavior."""

from __future__ import annotations

from src.codedueprocess.main import run


def test_cli_mock_mode_runs_successfully(capsys) -> None:
    """CLI should execute graph in mock mode and print report."""
    exit_code = run(
        [
            "--repo-url",
            "https://github.com/example/repo",
            "--mode",
            "mock",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Audit completed." in captured.out
    assert "Overall score: 4.1" in captured.out
