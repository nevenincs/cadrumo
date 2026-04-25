"""Regression test: ``aeat workflow run --help`` never advertises live flags.

Issue ``#393`` excised ``--no-dry-run`` and ``--i-understand-this-is-real``
from the default workflow CLI so Kent cannot accidentally discover a
live-write surface from the first-contact ``--help`` output. This test pins
the absence of those literals.

The assertions are restricted to ASCII-safe substrings to avoid the
Windows ``cp1252`` precedent documented in PR ``#389``: the rendered Rich
help output can contain non-ASCII glyphs that break full-text equality
checks on Windows terminals.
"""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from .. import app as root_app

pytestmark = [pytest.mark.unit, pytest.mark.domain_submission]


def test_run_help_omits_no_dry_run_flag() -> None:
    """``aeat workflow run --help`` must not list ``--no-dry-run``."""
    runner = CliRunner()
    result = runner.invoke(root_app, ["workflow", "run", "--help"])
    assert result.exit_code == 0, result.output
    assert "--no-dry-run" not in result.output


def test_run_help_omits_i_understand_flag() -> None:
    """``aeat workflow run --help`` must not list ``--i-understand-this-is-real``."""
    runner = CliRunner()
    result = runner.invoke(root_app, ["workflow", "run", "--help"])
    assert result.exit_code == 0, result.output
    assert "--i-understand-this-is-real" not in result.output
