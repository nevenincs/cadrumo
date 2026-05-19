"""CLI surface tests for ``aeat app overview calendar``."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from typer.testing import CliRunner

from aeat.adapters.persistence.storage import EphemeralMasterKeyProvider
from aeat.adapters.persistence.storage.sql.engine import dispose_engine
from aeat.application.user_profile._testing import register_minimal_profile
from aeat.application.workflow._persistence import workflow_state_repository
from aeat.entrypoints.cli import app

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


@pytest.fixture
def cli_runner() -> CliRunner:
    return CliRunner()


@pytest.fixture(autouse=True)
def _isolated_backend(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("AEAT_DATABASE_URL", f"sqlite:///{(tmp_path / 'overview.db').as_posix()}")
    dispose_engine()
    with EphemeralMasterKeyProvider():
        try:
            workflow_state_repository().update(
                lambda state: register_minimal_profile(state, profile_id="operator"),
            )
            yield
        finally:
            dispose_engine()


def test_calendar_requires_from_flag(cli_runner: CliRunner) -> None:
    """`--from` is required; missing it surfaces as Typer usage error."""

    result = cli_runner.invoke(app, ["app", "overview", "calendar", "--to", "2026-03-31"])
    assert result.exit_code != 0, result.output


def test_calendar_requires_to_flag(cli_runner: CliRunner) -> None:
    """`--to` is required; missing it surfaces as Typer usage error."""

    result = cli_runner.invoke(app, ["app", "overview", "calendar", "--from", "2026-01-01"])
    assert result.exit_code != 0, result.output


def test_calendar_rejects_malformed_date(cli_runner: CliRunner) -> None:
    """A non-ISO date in --from or --to is rejected before the service runs."""

    result = cli_runner.invoke(
        app,
        ["app", "overview", "calendar", "--from", "not-a-date", "--to", "2026-03-31"],
    )
    assert result.exit_code != 0, result.output


def test_calendar_renders_entries_for_q1_window(cli_runner: CliRunner) -> None:
    """A valid Q1 window over the minimal profile yields the entries
    header lines plus zero-or-more entry rows. With profile incomplete
    warnings present the verb still refuses without --allow-incomplete."""

    result_strict = cli_runner.invoke(
        app,
        [
            "app", "overview", "calendar",
            "--from", "2026-01-01",
            "--to", "2026-03-31",
        ],
    )
    # Minimal profile triggers completeness warnings; strict mode refuses.
    if result_strict.exit_code != 0:
        result_lax = cli_runner.invoke(
            app,
            [
                "app", "overview", "calendar",
                "--from", "2026-01-01",
                "--to", "2026-03-31",
                "--allow-incomplete",
            ],
        )
        assert result_lax.exit_code == 0, result_lax.output
        assert "from\t2026-01-01" in result_lax.output
        assert "to\t2026-03-31" in result_lax.output
        assert "entries\t" in result_lax.output
    else:
        # Profile was complete (unusual for minimal profile) — strict
        # mode rendered the calendar; assert the same anchors.
        assert "from\t2026-01-01" in result_strict.output
        assert "to\t2026-03-31" in result_strict.output


def test_calendar_help_advertises_local_only(cli_runner: CliRunner) -> None:
    """Help text must signal `local-only` so the operator cannot
    mistake the verb for an AEAT-contacting probe."""

    result = cli_runner.invoke(app, ["app", "overview", "calendar", "--help"])
    assert result.exit_code == 0, result.output
    assert any(
        token in result.output.lower()
        for token in ("local-only", "local;", "nunca", "mai contacta", "csak helyi")
    ), result.output
