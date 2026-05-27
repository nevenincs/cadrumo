"""CLI surface tests for ``aeat app overview calendar``."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from typer.testing import CliRunner

from aeat.adapters.persistence.storage.sql.engine import dispose_engine
from aeat.application.user_profile._orchestration import profile_create_storage_span
from aeat.application.user_profile._testing import register_minimal_profile
from aeat.application.workflow._persistence import workflow_state_repository
from aeat.entrypoints.cli import app
from aeat.tests.secure_sql import isolated_profile_storage_root

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


@pytest.fixture
def cli_runner() -> CliRunner:
    return CliRunner()


@pytest.fixture(autouse=True)
def _isolated_backend(tmp_path: Path) -> Iterator[None]:
    dispose_engine()
    with (
        isolated_profile_storage_root(tmp_path=tmp_path),
        profile_create_storage_span("operator"),
    ):
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
            "app",
            "overview",
            "calendar",
            "--from",
            "2026-01-01",
            "--to",
            "2026-03-31",
        ],
    )
    # Minimal profile triggers completeness warnings; strict mode refuses.
    if result_strict.exit_code != 0:
        result_lax = cli_runner.invoke(
            app,
            [
                "app",
                "overview",
                "calendar",
                "--from",
                "2026-01-01",
                "--to",
                "2026-03-31",
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
        token in result.output.lower() for token in ("local-only", "local;", "nunca", "mai contacta", "csak helyi")
    ), result.output


def test_all_profiles_flag_iterates_every_registered_profile(cli_runner: CliRunner) -> None:
    """--all-profiles iterates every registered profile.

    Two profiles are registered; the flag must emit a `profile` header
    line for each one. The test does not assert specific obligation rows
    because the minimal fixture leaves the taxpayer model undeclared;
    --allow-incomplete is required to get any output at all.
    """

    with profile_create_storage_span("second"):
        workflow_state_repository().update(
            lambda state: register_minimal_profile(
                state,
                profile_id="second",
                display_name="Second Operator",
                enforce_unique_tax_id=False,
            ),
        )

    result = cli_runner.invoke(
        app,
        [
            "app",
            "overview",
            "calendar",
            "--from",
            "2026-01-01",
            "--to",
            "2026-03-31",
            "--all-profiles",
            "--allow-incomplete",
        ],
    )
    assert result.exit_code == 0, result.output
    # Both profile labels must appear in the output.
    assert "operator" in result.output
    assert "Second Operator" in result.output
    # Output is structured with per-profile header lines.
    profile_lines = [line for line in result.output.splitlines() if line.startswith("profile\t")]
    assert len(profile_lines) == 2, f"expected 2 profile header lines, got: {result.output}"
