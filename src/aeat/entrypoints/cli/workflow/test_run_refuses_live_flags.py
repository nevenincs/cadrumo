"""Regression test: ``aeat workflow run`` exits non-zero on live-flag input.

If a script in the wild still passes ``--no-dry-run`` or
``--i-understand-this-is-real``, the CLI must fail loudly with typer's
"no such option" error rather than silently strip the flags and let the
caller assume a remote AEAT write was triggered. Live AEAT submission is
permanently forbidden; preserving the failure-fast contract is part of
the live-write safety charter.
"""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from .. import app as root_app

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


def test_run_rejects_no_dry_run_flag() -> None:
    """Passing ``--no-dry-run`` must produce a typer "no such option" exit."""
    runner = CliRunner()
    result = runner.invoke(
        root_app,
        ["workflow", "run", "--modelo", "130", "--period", "2026Q1", "--no-dry-run"],
    )
    assert result.exit_code == 2
    assert "no such option" in result.output.lower()


def test_run_rejects_i_understand_flag() -> None:
    """Passing ``--i-understand-this-is-real`` must produce a typer "no such option" exit."""
    runner = CliRunner()
    result = runner.invoke(
        root_app,
        [
            "workflow",
            "run",
            "--modelo",
            "130",
            "--period",
            "2026Q1",
            "--i-understand-this-is-real",
        ],
    )
    assert result.exit_code == 2
    assert "no such option" in result.output.lower()


def test_run_rejects_both_live_flags() -> None:
    """Passing both flags together must still produce a typer "no such option" exit."""
    runner = CliRunner()
    result = runner.invoke(
        root_app,
        [
            "workflow",
            "run",
            "--modelo",
            "130",
            "--period",
            "2026Q1",
            "--no-dry-run",
            "--i-understand-this-is-real",
        ],
    )
    assert result.exit_code == 2
    assert "no such option" in result.output.lower()
