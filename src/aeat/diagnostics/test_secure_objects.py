"""Smoke tests for the engineer-only `python -m aeat.diagnostics` entrypoint.

The secure-objects subcommand re-homes the previous
`aeat config repair list NAMESPACE` operator verb. These tests
exercise the Typer CLI end-to-end against the real
`build_repair_list_report` application service so a future
regression that breaks the diagnostics surface surfaces here, not
in production.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from typer.testing import CliRunner

from aeat.diagnostics.__main__ import app
from aeat.tests.secure_sql import isolated_runtime_profile

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture(autouse=True)
def _isolated_storage(tmp_path: Path) -> Iterator[None]:
    """Wire the diagnostics CLI at a fresh runtime profile database."""

    with isolated_runtime_profile(tmp_path=tmp_path):
        yield


def test_secure_objects_list_namespace_argument_required(runner: CliRunner) -> None:
    """Calling `secure-objects list` with no namespace surfaces a usage error."""

    result = runner.invoke(app, ["secure-objects", "list"])

    assert result.exit_code != 0
    assert "namespace" in result.output.lower() or "missing" in result.output.lower()


def test_secure_objects_list_empty_namespace_emits_zero_count(runner: CliRunner) -> None:
    """An empty namespace surfaces a zero-row count without raising."""

    result = runner.invoke(app, ["secure-objects", "list", "aeat.test.empty"])

    assert result.exit_code == 0
    assert "namespace\taeat.test.empty" in result.output
    assert "count\t0" in result.output


def test_secure_objects_list_rejects_conflicting_flags(runner: CliRunner) -> None:
    """`--all` and `--unreadable` cannot be combined."""

    result = runner.invoke(
        app,
        ["secure-objects", "list", "aeat.test.empty", "--all", "--unreadable"],
    )

    assert result.exit_code != 0
    assert "all" in result.output.lower() and "unreadable" in result.output.lower()
