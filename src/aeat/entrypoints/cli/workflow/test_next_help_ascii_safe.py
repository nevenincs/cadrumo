"""Regression test: ``aeat workflow next --help`` never advertises live flags.

Symmetric to :mod:`aeat.entrypoints.cli.workflow.test_run_help_ascii_safe` —
see that module for the live-write safety rationale. Assertions are
restricted to ASCII-safe substrings to avoid the Windows ``cp1252``
encoding mismatch on Rich-rendered help output.
"""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from .. import app as root_app

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


def test_next_help_omits_no_dry_run_flag() -> None:
    """``aeat workflow next --help`` must not list ``--no-dry-run``."""
    runner = CliRunner()
    result = runner.invoke(root_app, ["workflow", "next", "--help"])
    assert result.exit_code == 0, result.output
    assert "--no-dry-run" not in result.output


def test_next_help_omits_i_understand_flag() -> None:
    """``aeat workflow next --help`` must not list ``--i-understand-this-is-real``."""
    runner = CliRunner()
    result = runner.invoke(root_app, ["workflow", "next", "--help"])
    assert result.exit_code == 0, result.output
    assert "--i-understand-this-is-real" not in result.output
