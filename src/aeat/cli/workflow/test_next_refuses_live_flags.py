"""Regression test: ``aeat workflow next`` exits non-zero on live-flag input.

Symmetric to ``test_run_refuses_live_flags.py``. See that module's
docstring for the rationale and the controlling ADR reference.
"""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from .. import app as root_app

pytestmark = [pytest.mark.unit, pytest.mark.domain_submission]


def test_next_rejects_no_dry_run_flag() -> None:
    """Passing ``--no-dry-run`` must produce a typer "no such option" exit."""
    runner = CliRunner()
    result = runner.invoke(root_app, ["workflow", "next", "--no-dry-run"])
    assert result.exit_code != 0
    assert "No such option" in result.output


def test_next_rejects_i_understand_flag() -> None:
    """Passing ``--i-understand-this-is-real`` must produce a typer "no such option" exit."""
    runner = CliRunner()
    result = runner.invoke(
        root_app,
        ["workflow", "next", "--i-understand-this-is-real"],
    )
    assert result.exit_code != 0
    assert "No such option" in result.output


def test_next_rejects_both_live_flags() -> None:
    """Passing both flags together must still produce a typer "no such option" exit."""
    runner = CliRunner()
    result = runner.invoke(
        root_app,
        ["workflow", "next", "--no-dry-run", "--i-understand-this-is-real"],
    )
    assert result.exit_code != 0
    assert "No such option" in result.output
