"""Smoke tests for the llm CLI subtree."""

import pytest
from typer.testing import CliRunner

from . import app


@pytest.mark.unit
def test_llm_cli_has_expected_subcommands() -> None:
    """The llm subtree should expose the required verbs."""

    runner = CliRunner()
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "complete" in result.stdout
    assert "translate" in result.stdout
    assert "cache" in result.stdout
    assert "usage" in result.stdout
