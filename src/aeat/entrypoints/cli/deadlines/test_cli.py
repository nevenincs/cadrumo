"""Unit tests for the ``aeat deadlines`` CLI sub-app.

Verifies that ``list``, ``next``, and ``explain`` render correctly for
a representative :class:`aeat.domain.deadlines.AutonomoProfile`. The
fixtures seed an active ``WorkflowState`` profile so the CLI loads
the typed projection through the wizard descriptor.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from typer.testing import CliRunner

from . import app

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


@pytest.fixture(autouse=True)
def _seed_active_profile(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Point the workflow repository at an isolated SQLite store and seed a profile."""

    monkeypatch.setenv("AEAT_DATABASE_URL", f"sqlite:///{(tmp_path / 'workflow.db').as_posix()}")
    monkeypatch.setenv("AEAT_SECRET_STORE_BACKEND", "unsecured")
    monkeypatch.setenv("AEAT_ALLOW_UNENCRYPTED", "1")

    from ....adapters.persistence.storage.sql.engine import dispose_engine
    from ....application.profile._actions import set_active_profile, set_profile_values
    from ....application.workflow._persistence import workflow_state_repository

    dispose_engine()
    repository = workflow_state_repository()
    repository.update(
        lambda state: set_active_profile(
            set_profile_values(
                state,
                "operator",
                {
                    "tax.id": "X1234567L",
                    "activity": "design",
                    "iva.regime": "GENERAL",
                    "has_employees": "true",
                },
            ),
            "operator",
        )
    )
    try:
        yield
    finally:
        dispose_engine()


@pytest.fixture()
def runner() -> CliRunner:
    return CliRunner()


def test_list_renders_obligations(runner: CliRunner) -> None:
    result = runner.invoke(app, ["list", "--year", "2026"])
    assert result.exit_code == 0, result.output
    assert "111" in result.output
    assert "130" in result.output
    assert "2026Q1" in result.output


def test_next_renders_an_obligation(runner: CliRunner) -> None:
    result = runner.invoke(app, ["next", "--year", "2026"])
    assert result.exit_code == 0, result.output
    assert "111" in result.output


def test_explain_known_modelo(runner: CliRunner) -> None:
    result = runner.invoke(app, ["explain", "111"])
    assert result.exit_code == 0, result.output
    assert "111" in result.output
    assert "retencion" in result.output
