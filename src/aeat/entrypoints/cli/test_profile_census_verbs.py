"""CLI surface tests for ``aeat config profile census {refresh,show,compare,apply}``.

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

from aeat.adapters.persistence.storage import (
    EncryptedBlobStore,
    EphemeralMasterKeyProvider,
    SecretStore,
    override_secret_store,
)
from aeat.adapters.persistence.storage.sql.engine import dispose_engine
from aeat.application.live._censo import CensoSnapshotService
from aeat.entrypoints.cli._config import profile_app

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


_G313 = "https://sede.agenciatributaria.gob.es/Sede/procedimientoini/G313.shtml"


@pytest.fixture
def cli_runner() -> CliRunner:
    return CliRunner()


@pytest.fixture(autouse=True)
def _isolated_backend(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    dispose_engine()
    monkeypatch.setenv("AEAT_DATABASE_URL", f"sqlite:///{(tmp_path / 'aeat.db').as_posix()}")
    monkeypatch.setenv("AEAT_PROFILE_BUCKET_ROOT", str(tmp_path / "buckets"))
    provider = EphemeralMasterKeyProvider()
    with provider:
        blob_store = EncryptedBlobStore(
            root_dir=tmp_path / "blobs-secret",
            master_key_provider=provider,
        )
        secret_store = SecretStore(
            store_dir=tmp_path / "secrets",
            blob_store=blob_store,
            master_key_provider=provider,
        )
        override_secret_store(secret_store)
        try:
            yield
        finally:
            dispose_engine()
            override_secret_store(None)


def _seed_active_profile() -> None:
    from aeat.application.user_profile._testing import register_minimal_profile
    from aeat.application.workflow._persistence import workflow_state_repository

    repo = workflow_state_repository()
    repo.update(
        lambda state: register_minimal_profile(
            state,
            profile_id="default",
            overrides={"identity.tax_id": "12345678Z", "activities.description": "software"},
        )
    )


def _capture_snapshot() -> str:
    from aeat.application.workflow._models import resolve_active_bucket_id

    active = resolve_active_bucket_id()
    assert active is not None, "active profile must be seeded before capture"
    service = CensoSnapshotService(bucket_id=active)
    snapshot = service.capture(
        profile_id=active,
        captured_at=datetime.now(UTC),
        source_url=_G313,
        censo_facts={
            "census.establecimiento_type": "propio",
            "census.elected_withholding_pct": "15",
            "vivienda_office.total_m2": "120.00",
            "vivienda_office.office_m2": "24.00",
        },
    )
    return snapshot.snapshot_id


def test_census_help_lists_four_verbs(cli_runner: CliRunner) -> None:
    result = cli_runner.invoke(profile_app, ["census", "--help"])

    assert result.exit_code == 0
    for verb in ("refresh", "show", "compare", "apply"):
        assert verb in result.output


def test_refresh_refuses_without_live_gate(
    cli_runner: CliRunner, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Live refresh requires AEAT_LIVE_TESTS_ENABLED=1 to pass the
    access-gate. With the gate off (default), the CLI surfaces the
    refusal without ever touching a browser session."""

    _seed_active_profile()
    monkeypatch.delenv("AEAT_LIVE_TESTS_ENABLED", raising=False)

    result = cli_runner.invoke(profile_app, ["census", "refresh"])

    assert result.exit_code != 0


def test_show_refuses_when_no_snapshot_exists(cli_runner: CliRunner) -> None:
    _seed_active_profile()

    result = cli_runner.invoke(profile_app, ["census", "show"])

    assert result.exit_code != 0
    assert "no census snapshot" in result.output.lower()


def test_show_emits_active_snapshot(cli_runner: CliRunner) -> None:
    _seed_active_profile()
    snapshot_id = _capture_snapshot()

    result = cli_runner.invoke(profile_app, ["census", "show"])

    assert result.exit_code == 0
    assert snapshot_id in result.output
    assert "vivienda_office.total_m2\t120.00" in result.output
    assert "state\tactive" in result.output


def test_compare_reports_per_field_status(cli_runner: CliRunner) -> None:
    _seed_active_profile()
    _capture_snapshot()

    result = cli_runner.invoke(profile_app, ["census", "compare"])

    assert result.exit_code == 0
    assert "census_only\tcensus.establecimiento_type" in result.output
    assert "census_only\tvivienda_office.total_m2" in result.output


def test_apply_writes_censo_facts_onto_profile(cli_runner: CliRunner) -> None:
    _seed_active_profile()
    _capture_snapshot()

    result = cli_runner.invoke(profile_app, ["census", "apply"])

    assert result.exit_code == 0
    assert "written\tcensus.establecimiento_type" in result.output
    assert "written\tvivienda_office.office_m2" in result.output


def test_compare_matches_after_apply(cli_runner: CliRunner) -> None:
    _seed_active_profile()
    _capture_snapshot()
    cli_runner.invoke(profile_app, ["census", "apply"])

    result = cli_runner.invoke(profile_app, ["census", "compare"])

    assert result.exit_code == 0
    assert "matches\tcensus.establecimiento_type" in result.output
    assert "matches\tvivienda_office.total_m2" in result.output


def test_apply_emits_census_applied_bucket_event(cli_runner: CliRunner) -> None:
    """Apply MUST emit CENSUS_APPLIED so the stale-cascade walker
    has a typed event to react to. The CLI test never reached the
    catalogue before this assertion landed — the emission was
    implemented but not witnessed end-to-end."""

    from aeat.application.workflow._models import resolve_active_bucket_id
    from aeat.application.workflow._persistence import workflow_state_repository
    from aeat.domain.buckets import BucketEventHistoryRepository, BucketEventType

    _seed_active_profile()
    snapshot_id = _capture_snapshot()

    result = cli_runner.invoke(profile_app, ["census", "apply"])
    assert result.exit_code == 0, result.output

    catalogue = BucketEventHistoryRepository().load()
    workflow_state_repository().load()
    active = resolve_active_bucket_id()
    matching = [
        event
        for event in catalogue.events.values()
        if event.event_type is BucketEventType.CENSUS_APPLIED
        and event.object_id == active
    ]
    assert matching, (
        f"CENSUS_APPLIED must fire after apply; "
        f"saw {[e.event_type.value for e in catalogue.events.values()]}"
    )
    payload = matching[-1].payload
    assert payload["snapshot_id"] == snapshot_id
    assert payload["profile_id"] == active


def test_rejected_subverb_returns_nonzero(cli_runner: CliRunner) -> None:
    """Typer must refuse an undeclared subverb (e.g. 'diff' is not in
    {refresh, show, compare, apply}). Without this regression a typo
    would silently invoke nothing instead of erroring."""

    _seed_active_profile()

    result = cli_runner.invoke(profile_app, ["census", "diff"])

    assert result.exit_code != 0


def test_compare_emits_json_payload_with_typed_rows() -> None:
    """The --format json branch on the root aeat CLI must render
    CensoProfileComparison through model_dump(mode='json') cleanly."""

    import json

    from aeat.tests.cli_runner import invoke_cached_cli

    _seed_active_profile()
    _capture_snapshot()

    result = invoke_cached_cli(["--format", "json", "config", "profile", "census", "compare"])
    assert result.exit_code == 0, result.output

    payload = json.loads(result.output)
    assert payload["snapshot_id"]
    statuses = {row["path"]: row["status"] for row in payload["rows"]}
    assert statuses["census.establecimiento_type"] == "census_only"
    assert statuses["vivienda_office.total_m2"] == "census_only"


def test_apply_emits_json_payload_with_written_paths() -> None:
    """The --format json branch on apply must serialize CensoApplyResult
    through model_dump(mode='json'); written_paths is a tuple that
    JSON renders as a list."""

    import json

    from aeat.tests.cli_runner import invoke_cached_cli

    _seed_active_profile()
    _capture_snapshot()

    result = invoke_cached_cli(["--format", "json", "config", "profile", "census", "apply"])
    assert result.exit_code == 0, result.output

    payload = json.loads(result.output)
    assert payload["snapshot_id"]
    assert "census.establecimiento_type" in payload["written_paths"]
    assert "vivienda_office.office_m2" in payload["written_paths"]
