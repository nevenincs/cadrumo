"""Smoke tests for :mod:`aeat.entrypoints.cli.llm`.

Asserts that the registered Typer sub-app exposes the expected
top-level verbs (``complete``, ``translate``, ``cache``, ``usage``).
"""

import pytest
from typer.testing import CliRunner

from . import app

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


def test_llm_cli_has_expected_subcommands() -> None:
    """The ``aeat llm`` subtree exposes the four required verbs in ``--help``."""

    runner = CliRunner()
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "complete" in result.stdout
    assert "translate" in result.stdout
    assert "cache" in result.stdout
    assert "usage" in result.stdout
