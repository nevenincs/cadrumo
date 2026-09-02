"""Focused command-surface tests for generated export-tree publication."""

from __future__ import annotations

from typer.testing import CliRunner

from ..pipeline.cli import app


def test_pipeline_cli_registers_the_separate_check_and_publish_verbs() -> None:
    """The developer-only lifecycle surface exposes both authority modes."""
    result = CliRunner().invoke(app, ["--help"])

    assert result.exit_code == 0, result.output
    assert "check" in result.output
    assert "publish" in result.output


def test_pipeline_cli_refuses_an_undeclared_record_design_source_before_staging() -> None:
    """An explicit source selector is checked against the revision, never guessed."""
    result = CliRunner().invoke(
        app,
        ["check", "200", "2024", "not-a-declared-source", "2024", "0A"],
    )

    assert result.exit_code == 1
    assert "does not declare record-design source" in result.output
