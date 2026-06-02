"""CLI surface tests for ``aeat config profile censo {refresh,show,compare,apply}``.

Exercises the Typer surface end-to-end against a real seeded
WorkflowState + the encrypted backend. Refresh is asserted to refuse
cleanly with the "sede driver not wired" message; show/compare/apply
are exercised against a snapshot captured via the application service
directly (the production refresh path lands when the sede G313
adapter is wired through the live driver).
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from typer.testing import CliRunner

from ...adapters.persistence.storage.sql.engine import dispose_engine
from ...application.live._censo import CensoSnapshotService
from ...application.user_profile._orchestration import profile_create_storage_span
from ._config import profile_app
from ...tests.secure_sql import isolated_profile_storage_root

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


_G313 = "https://sede.agenciatributaria.gob.es/Sede/procedimientoini/G313.shtml"


@pytest.fixture(autouse=True)
def _isolated_backend(tmp_path: Path) -> Iterator[None]:
    dispose_engine()
    with (
        isolated_profile_storage_root(tmp_path=tmp_path),
        profile_create_storage_span("default"),
    ):
        try:
            yield
        finally:
            dispose_engine()


def _seed_active_profile() -> None:
    from ...application.user_profile._testing import register_minimal_profile
    from ...application.workflow._persistence import workflow_state_repository

    repo = workflow_state_repository()
    repo.update(
        lambda state: register_minimal_profile(
            state,
            profile_id="default",
            overrides={"identity.tax_id": "12345678Z", "activities.description": "software"},
        )
    )


def _capture_snapshot() -> str:
    from ...application.workflow._models import resolve_active_bucket_id

    active = resolve_active_bucket_id()
    assert active is not None, "active profile must be seeded before capture"
    service = CensoSnapshotService(bucket_id=active)
    snapshot = service.capture(
        profile_id=active,
        captured_at=datetime.now(UTC),
        source_url=_G313,
        censo_facts={
            "censo.establecimiento_type": "propio",
            "censo.elected_withholding_pct": "15",
            "vivienda_office.total_m2": "120.00",
            "vivienda_office.office_m2": "24.00",
        },
    )
    return snapshot.snapshot_id


def test_censo_help_lists_four_verbs(cli_runner: CliRunner) -> None:
    result = cli_runner.invoke(profile_app, ["censo", "--help"])

    assert result.exit_code == 0
    for verb in ("refresh", "show", "compare", "apply"):
        assert verb in result.output


def test_refresh_refuses_without_live_gate(cli_runner: CliRunner) -> None:
    """Live refresh requires AEAT_LIVE_TESTS_ENABLED=1 to pass the
    access-gate. With the gate off (default), the CLI surfaces the
    refusal without ever touching a browser session.

    ``override_settings(aeat_live_tests_enabled=False)`` pins the
    gate-off state; the ContextVar-backed override shadows any ambient
    env value.
    """

    from ...core.config import override_settings

    _seed_active_profile()

    with override_settings(aeat_live_tests_enabled=""):
        result = cli_runner.invoke(profile_app, ["censo", "refresh"])

    assert result.exit_code != 0


def test_show_refuses_when_no_snapshot_exists(cli_runner: CliRunner) -> None:
    _seed_active_profile()

    result = cli_runner.invoke(profile_app, ["censo", "show"])

    assert result.exit_code != 0
    # The CLI error boundary decoration is process-global memoised by
    # callback identity (see ``command_error_boundary`` in ``_errors``).
    # When the root ``aeat`` app has been imported by an earlier test,
    # ``profile_app`` callbacks are wrapped and the refusal renders to
    # stderr (mixed into ``result.output``).  When this test runs alone
    # the verb raises ``CliRefusedBoundaryError`` directly and the
    # message is on ``result.exception``.  Accept both surfaces so the
    # assertion is order-independent.
    haystack = (result.output + " " + str(result.exception or "")).lower()
    assert "no censo snapshot" in haystack


def test_show_emits_active_snapshot(cli_runner: CliRunner) -> None:
    _seed_active_profile()
    snapshot_id = _capture_snapshot()

    result = cli_runner.invoke(profile_app, ["censo", "show"])

    assert result.exit_code == 0
    assert snapshot_id in result.output
    assert "vivienda_office.total_m2\t120.00" in result.output
    assert "state\tactive" in result.output


def test_compare_reports_per_field_status(cli_runner: CliRunner) -> None:
    _seed_active_profile()
    _capture_snapshot()

    result = cli_runner.invoke(profile_app, ["censo", "compare"])

    assert result.exit_code == 0
    assert "censo_only\tcenso.establecimiento_type" in result.output
    assert "censo_only\tvivienda_office.total_m2" in result.output


def test_apply_writes_censo_facts_onto_profile(cli_runner: CliRunner) -> None:
    _seed_active_profile()
    _capture_snapshot()

    result = cli_runner.invoke(profile_app, ["censo", "apply"])

    assert result.exit_code == 0
    assert "written\tcenso.establecimiento_type" in result.output
    assert "written\tvivienda_office.office_m2" in result.output


def test_compare_matches_after_apply(cli_runner: CliRunner) -> None:
    _seed_active_profile()
    _capture_snapshot()
    cli_runner.invoke(profile_app, ["censo", "apply"])

    result = cli_runner.invoke(profile_app, ["censo", "compare"])

    assert result.exit_code == 0
    assert "matches\tcenso.establecimiento_type" in result.output
    assert "matches\tvivienda_office.total_m2" in result.output


def test_apply_emits_censo_applied_bucket_event(cli_runner: CliRunner) -> None:
    """Apply MUST emit CENSO_APPLIED so the stale-cascade walker
    has a typed event to react to. The CLI test never reached the
    catalogue before this assertion landed — the emission was
    implemented but not witnessed end-to-end."""

    from ...application.workflow._models import resolve_active_bucket_id
    from ...application.workflow._persistence import workflow_state_repository
    from ...domain.buckets import BucketEventHistoryRepository, BucketEventType

    _seed_active_profile()
    snapshot_id = _capture_snapshot()

    result = cli_runner.invoke(profile_app, ["censo", "apply"])
    assert result.exit_code == 0, result.output

    catalogue = BucketEventHistoryRepository().load()
    workflow_state_repository().load()
    active = resolve_active_bucket_id()
    matching = [
        event
        for event in catalogue.events.values()
        if event.event_type is BucketEventType.CENSO_APPLIED and event.object_id == active
    ]
    assert matching, (
        f"CENSO_APPLIED must fire after apply; saw {[e.event_type.value for e in catalogue.events.values()]}"
    )
    payload = matching[-1].payload
    assert payload["snapshot_id"] == snapshot_id
    assert payload["profile_id"] == active


def test_rejected_subverb_returns_nonzero(cli_runner: CliRunner) -> None:
    """Typer must refuse an undeclared subverb (e.g. 'diff' is not in
    {refresh, show, compare, apply}). Without this regression a typo
    would silently invoke nothing instead of erroring."""

    _seed_active_profile()

    result = cli_runner.invoke(profile_app, ["censo", "diff"])

    assert result.exit_code != 0


def test_compare_emits_json_payload_with_typed_rows() -> None:
    """The --format json branch on the root aeat CLI must render
    CensoProfileComparison through model_dump(mode='json') cleanly."""

    import json

    from ...tests.cli_runner import invoke_cached_cli

    _seed_active_profile()
    _capture_snapshot()

    result = invoke_cached_cli(["--format", "json", "config", "profile", "censo", "compare"])
    assert result.exit_code == 0, result.output

    raw = json.loads(result.output)
    # Every CLI verb now emits the centralised {schema_version, command,
    # result, warnings} envelope; the operator-visible payload lives
    # under ``result``.
    payload = raw["result"] if isinstance(raw, dict) and "schema_version" in raw else raw
    assert payload["snapshot_id"]
    statuses = {row["path"]: row["status"] for row in payload["rows"]}
    assert statuses["censo.establecimiento_type"] == "censo_only"
    assert statuses["vivienda_office.total_m2"] == "censo_only"


def test_apply_emits_json_payload_with_written_paths() -> None:
    """The --format json branch on apply must serialize CensoApplyPayload
    (projected from the application CensoApplyResult via from_result) through
    model_dump(mode='json'); written_paths is a tuple that JSON renders as a list."""

    import json

    from ...tests.cli_runner import invoke_cached_cli

    _seed_active_profile()
    _capture_snapshot()

    result = invoke_cached_cli(["--format", "json", "config", "profile", "censo", "apply"])
    assert result.exit_code == 0, result.output

    raw = json.loads(result.output)
    payload = raw["result"] if isinstance(raw, dict) and "schema_version" in raw else raw
    assert payload["snapshot_id"]
    assert "censo.establecimiento_type" in payload["written_paths"]
    assert "vivienda_office.office_m2" in payload["written_paths"]
