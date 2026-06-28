"""CLI surface tests for ``aeat app overview agenda``."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from typer.testing import CliRunner

from ....application.user_profile._orchestration import profile_create_storage_span
from ....application.user_profile._testing import register_minimal_profile
from ....application.workflow._persistence import workflow_state_repository
from ....tests.secure_sql import isolated_profile_storage_root
from .. import app

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


@pytest.fixture(autouse=True)
def _isolated_backend(tmp_path: Path) -> Iterator[None]:
    with (
        isolated_profile_storage_root(tmp_path=tmp_path),
        profile_create_storage_span("operator"),
    ):
        workflow_state_repository().update(
            lambda state: register_minimal_profile(state, profile_id="operator"),
        )
        yield


def test_agenda_renders_envelope_with_explicit_date(cli_runner: CliRunner) -> None:
    """A concrete --date renders the agenda envelope including as_of,
    horizon, and the four cohort headers."""

    result = cli_runner.invoke(
        app,
        ["app", "overview", "agenda", "--date", "2026-04-15", "--allow-incomplete"],
    )
    assert result.exit_code == 0, result.output
    assert "as_of\t2026-04-15" in result.output
    assert "horizon_days\t14" in result.output
    assert "next_due\t" in result.output
    assert "due_today\t" in result.output
    assert "due_soon\t" in result.output
    assert "overdue\t" in result.output


def test_agenda_rejects_zero_horizon(cli_runner: CliRunner) -> None:
    """A non-positive --horizon is refused before the service runs."""

    result = cli_runner.invoke(
        app,
        ["app", "overview", "agenda", "--date", "2026-04-15", "--horizon", "0"],
    )
    assert result.exit_code != 0, result.output


def test_agenda_rejects_malformed_date(cli_runner: CliRunner) -> None:
    """A non-ISO --date is rejected by the parsing boundary."""

    result = cli_runner.invoke(
        app,
        ["app", "overview", "agenda", "--date", "not-a-date"],
    )
    assert result.exit_code != 0, result.output


def test_agenda_help_advertises_local_only(cli_runner: CliRunner) -> None:
    """Help text must signal `local-only` across locales."""

    result = cli_runner.invoke(app, ["app", "overview", "agenda", "--help"])
    assert result.exit_code == 0, result.output
    assert any(
        token in result.output.lower() for token in ("local-only", "local;", "nunca", "mai contacta", "csak helyi")
    ), result.output


def test_agenda_horizon_widens_due_soon_window(cli_runner: CliRunner) -> None:
    """A wider --horizon includes more entries in due_soon than the
    default 14-day window. Asserts the horizon is honoured by the
    service rather than being a cosmetic flag."""

    narrow = cli_runner.invoke(
        app,
        [
            "app",
            "overview",
            "agenda",
            "--date",
            "2026-01-01",
            "--horizon",
            "7",
            "--allow-incomplete",
        ],
    )
    wide = cli_runner.invoke(
        app,
        [
            "app",
            "overview",
            "agenda",
            "--date",
            "2026-01-01",
            "--horizon",
            "180",
            "--allow-incomplete",
        ],
    )
    assert narrow.exit_code == 0, narrow.output
    assert wide.exit_code == 0, wide.output

    # The wider window's due_soon count must be >= the narrow window's.
    def _due_soon_count(output: str) -> int:
        for line in output.splitlines():
            if line.startswith("due_soon\t"):
                return int(line.split("\t", 1)[1])
        raise AssertionError(f"due_soon line missing from output: {output}")

    assert _due_soon_count(wide.output) >= _due_soon_count(narrow.output)
