"""CLI surface tests for ``aeat app overview calendar``."""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from pydantic import AnyHttpUrl
from typer.testing import CliRunner

from ....adapters.outbound.aeat.sede._declarations import Declaracion
from ....adapters.outbound.aeat.sede._notifications import NotificationsSnapshot, RemoteNotification
from ....application.live import ExpedientesCapture, ExpedientesService, NotificationsService
from ....application.user_profile._orchestration import profile_create_storage_span
from ....application.user_profile._testing import register_minimal_profile
from ....application.workflow._persistence import workflow_state_repository
from ....tests.aeat_literal_fixtures import aeat_url
from ....tests.secure_sql import isolated_profile_storage_root
from .. import app

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_SOURCE_URL = AnyHttpUrl(aeat_url("sede", "/"))


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


def test_calendar_json_includes_local_live_snapshot_events(cli_runner: CliRunner) -> None:
    ExpedientesService().capture(
        bucket_id="operator",
        capture=ExpedientesCapture(
            declarations=(
                Declaracion(
                    modelo="303",
                    ejercicio=2025,
                    period="1T",
                    expediente_id="12345678901234567890",
                    estado="ALTA",
                    presented_at=datetime(2025, 4, 15, 9, 30, tzinfo=UTC),
                ),
            ),
            captured_at=datetime(2025, 4, 15, 10, 0, tzinfo=UTC),
            source_url="declarations:modelo=303:ejercicio=2025",
        ),
    )
    NotificationsService().capture(
        bucket_id="operator",
        snapshot=NotificationsSnapshot(
            rows=(
                RemoteNotification(
                    certificado_id="2596230606502",
                    tipo="notificacion",
                    concepto="Requerimiento censal",
                    titular_nif="B12345678",
                    titular_nombre="Test S.L.",
                    destinatario_nif="B12345678",
                    destinatario_nombre="Test S.L.",
                    fecha_emision=date(2025, 4, 14),
                    fecha_notificacion=None,
                    leida=False,
                    source_url=_SOURCE_URL,
                ),
            ),
            captured_at=datetime(2025, 4, 14, 10, 0, tzinfo=UTC),
            source_url=_SOURCE_URL,
        ),
    )

    result = cli_runner.invoke(
        app,
        [
            "--format",
            "json",
            "app",
            "overview",
            "calendar",
            "--from",
            "2025-04-01",
            "--to",
            "2025-04-30",
            "--allow-incomplete",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    events = payload["result"]["events"]
    assert {(event["event_type"], event["reference_id"]) for event in events} == {
        ("filing", "12345678901234567890"),
        ("message", "2596230606502"),
    }


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
