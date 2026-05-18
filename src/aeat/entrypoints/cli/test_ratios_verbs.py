"""CLI surface tests for `aeat app ledger ratios {list, set, unset, eligible, validate}`."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from typer.testing import CliRunner

from aeat.application.user_profile._testing import register_minimal_profile
from aeat.application.workflow._models import resolve_active_bucket_id
from aeat.application.workflow._persistence import workflow_state_repository
from aeat.entrypoints.cli._ledger import ratios_app

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


@pytest.fixture(autouse=True)
def _isolated_backend(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    from aeat.adapters.persistence.storage.sql.engine import dispose_engine

    monkeypatch.setenv("AEAT_DATABASE_URL", f"sqlite:///{(tmp_path / 'ratios-verbs.db').as_posix()}")
    monkeypatch.setenv("AEAT_SECRET_STORE_BACKEND", "unsecured")
    monkeypatch.setenv("AEAT_ALLOW_UNENCRYPTED", "1")
    dispose_engine()
    try:
        workflow_state_repository().update(lambda state: register_minimal_profile(state, profile_id="default"))
        yield
    finally:
        dispose_engine()


@pytest.fixture
def cli_runner() -> CliRunner:
    return CliRunner()


def test_ratios_list_starts_empty(cli_runner: CliRunner) -> None:
    result = cli_runner.invoke(ratios_app, ["list"])
    assert result.exit_code == 0, result.output
    assert "count\t0" in result.output


def test_ratios_set_persists_and_list_reflects(cli_runner: CliRunner) -> None:
    set_result = cli_runner.invoke(ratios_app, ["set", "vehiculo_combustible", "0.5"])
    assert set_result.exit_code == 0, set_result.output
    assert "vehiculo_combustible\t0.5" in set_result.output

    list_result = cli_runner.invoke(ratios_app, ["list"])
    assert list_result.exit_code == 0, list_result.output
    assert "count\t1" in list_result.output
    assert "vehiculo_combustible\t0.5" in list_result.output


def test_ratios_unset_clears(cli_runner: CliRunner) -> None:
    cli_runner.invoke(ratios_app, ["set", "vehiculo_combustible", "0.5"])
    result = cli_runner.invoke(ratios_app, ["unset", "vehiculo_combustible"])
    assert result.exit_code == 0, result.output
    assert "vehiculo_combustible\t<unset>" in result.output

    list_result = cli_runner.invoke(ratios_app, ["list"])
    assert "count\t0" in list_result.output


def test_ratios_unset_refuses_unknown_override(cli_runner: CliRunner) -> None:
    result = cli_runner.invoke(ratios_app, ["unset", "vehiculo_combustible"])
    assert result.exit_code != 0


def test_ratios_set_refuses_unknown_category(cli_runner: CliRunner) -> None:
    result = cli_runner.invoke(ratios_app, ["set", "NOT_A_CATEGORY", "0.5"])
    assert result.exit_code != 0


def test_ratios_set_refuses_out_of_bounds(cli_runner: CliRunner) -> None:
    result = cli_runner.invoke(ratios_app, ["set", "vehiculo_combustible", "1.5"])
    assert result.exit_code != 0


def test_ratios_eligible_lists_categories(cli_runner: CliRunner) -> None:
    result = cli_runner.invoke(ratios_app, ["eligible"])
    assert result.exit_code == 0, result.output
    assert "vehiculo_" in result.output or "telefonia_" in result.output


def test_ratios_validate_reports_clean_when_empty(cli_runner: CliRunner) -> None:
    result = cli_runner.invoke(ratios_app, ["validate"])
    assert result.exit_code == 0, result.output
    assert "profile_present\tFalse" in result.output


def test_ratios_set_emits_ledger_ratios_set_event(cli_runner: CliRunner) -> None:
    """`ratios set` records a typed LEDGER_RATIOS_SET event in the bucket
    history so downstream auditors can replay the override sequence."""

    from aeat.domain.buckets import BucketEventHistoryRepository, BucketEventType

    set_result = cli_runner.invoke(ratios_app, ["set", "vehiculo_combustible", "0.5"])
    assert set_result.exit_code == 0, set_result.output

    catalogue = BucketEventHistoryRepository().load()
    matching = [
        event
        for event in catalogue.events.values()
        if event.event_type is BucketEventType.LEDGER_RATIOS_SET
        and event.object_id == "vehiculo_combustible"
    ]
    assert matching, [event.event_type for event in catalogue.events.values()]
    assert matching[-1].payload["new"] == "0.5"
    assert matching[-1].payload["prior"] == ""


def test_ratios_unset_emits_ledger_ratios_unset_event(cli_runner: CliRunner) -> None:
    """`ratios unset` records a typed LEDGER_RATIOS_UNSET event with the
    prior ratio value so the operator-visible mutation cannot be replayed
    only from the secure-object snapshot."""

    from aeat.domain.buckets import BucketEventHistoryRepository, BucketEventType

    cli_runner.invoke(ratios_app, ["set", "vehiculo_combustible", "0.5"])
    unset_result = cli_runner.invoke(ratios_app, ["unset", "vehiculo_combustible"])
    assert unset_result.exit_code == 0, unset_result.output

    catalogue = BucketEventHistoryRepository().load()
    matching = [
        event
        for event in catalogue.events.values()
        if event.event_type is BucketEventType.LEDGER_RATIOS_UNSET
        and event.object_id == "vehiculo_combustible"
    ]
    assert matching
    assert matching[-1].payload["prior"] == "0.5"
    assert matching[-1].payload["new"] == ""


def _capture_census_with_vivienda_office(office_m2: str, total_m2: str) -> None:
    """Capture a census snapshot for the active profile with the supplied m².

    Used by census-override-warning tests so the ratios_set handler has
    a bound raw afectación ratio to compare the operator-supplied value
    against.
    """

    from datetime import UTC, datetime

    from aeat.application.live._census import CensusSnapshotService

    state = workflow_state_repository().load()
    bucket_id = state.profiles[resolve_active_bucket_id(state) or ""].bucket_id
    service = CensusSnapshotService(bucket_id=bucket_id)
    service.capture(
        profile_id=resolve_active_bucket_id(state),
        captured_at=datetime.now(UTC),
        source_url="https://sede.agenciatributaria.gob.es/Sede/procedimientoini/G313.shtml",
        census_facts={
            "vivienda_office.total_m2": total_m2,
            "vivienda_office.office_m2": office_m2,
        },
    )


def test_ratios_set_emits_census_override_warning_when_suministros_diverges(
    cli_runner: CliRunner,
) -> None:
    """Setting a HOME_OFFICE suministros ratio at a value different from
    raw_afectacion * 0.30 (LIRPF Art. 30.2 rule 5) emits the warning
    event. The set itself still lands — the operator may legitimately
    model a planned change — but the divergence is recorded."""

    from aeat.domain.buckets import BucketEventHistoryRepository, BucketEventType

    _capture_census_with_vivienda_office(office_m2="20", total_m2="100")

    set_result = cli_runner.invoke(ratios_app, ["set", "suministros_home_office_luz", "0.5"])
    assert set_result.exit_code == 0, set_result.output

    catalogue = BucketEventHistoryRepository().load()
    warnings = [
        event
        for event in catalogue.events.values()
        if event.event_type is BucketEventType.LEDGER_RATIOS_CENSUS_OVERRIDE_WARNING
        and event.object_id == "suministros_home_office_luz"
    ]
    assert warnings, (
        "LEDGER_RATIOS_CENSUS_OVERRIDE_WARNING must fire when the operator "
        "overrides a suministros ratio away from the LIRPF Art. 30.2 rule 5 value"
    )
    payload = warnings[-1].payload
    assert payload["override_ratio"] == "0.5"
    assert payload["census_derived_ratio"] == "0.060"
    assert payload["raw_afectacion_ratio"] == "0.2"


def test_ratios_set_silent_when_suministros_override_matches_30pct_of_raw(
    cli_runner: CliRunner,
) -> None:
    """When the operator sets the legally-correct value (raw * 0.30),
    no warning fires. Witnesses that the warning isn't spuriously
    emitted on every HOME_OFFICE set."""

    from aeat.domain.buckets import BucketEventHistoryRepository, BucketEventType

    _capture_census_with_vivienda_office(office_m2="20", total_m2="100")

    set_result = cli_runner.invoke(ratios_app, ["set", "suministros_home_office_luz", "0.06"])
    assert set_result.exit_code == 0, set_result.output

    catalogue = BucketEventHistoryRepository().load()
    warnings = [
        event
        for event in catalogue.events.values()
        if event.event_type is BucketEventType.LEDGER_RATIOS_CENSUS_OVERRIDE_WARNING
    ]
    assert not warnings, (
        "no warning should fire when the override exactly matches the "
        "census-derived value"
    )


def test_ratios_list_surfaces_census_mismatch_without_hiding_rows(
    cli_runner: CliRunner,
) -> None:
    """list now routes through load_usage_ratios_with_census_guard. If
    the persisted HOME_OFFICE override disagrees with the bound census,
    a typed census_mismatch warning row is emitted alongside the regular
    rows — operators see both the persisted value AND the divergence
    against AEAT, never one without the other."""

    _capture_census_with_vivienda_office(office_m2="20", total_m2="100")
    set_result = cli_runner.invoke(ratios_app, ["set", "suministros_home_office_luz", "0.5"])
    assert set_result.exit_code == 0, set_result.output

    list_result = cli_runner.invoke(ratios_app, ["list"])

    assert list_result.exit_code == 0, list_result.output
    assert "suministros_home_office_luz\t0.5" in list_result.output
    assert "census_mismatch" in list_result.output
    assert "suministros_home_office_luz" in list_result.output


def test_ratios_set_silent_for_non_home_office_category(cli_runner: CliRunner) -> None:
    """The override-warning event is HOME_OFFICE-scoped per the ADR:
    other categories don't carry the census-binding contract."""

    from aeat.domain.buckets import BucketEventHistoryRepository, BucketEventType

    _capture_census_with_vivienda_office(office_m2="20", total_m2="100")

    set_result = cli_runner.invoke(ratios_app, ["set", "vehiculo_combustible", "0.9"])
    assert set_result.exit_code == 0, set_result.output

    catalogue = BucketEventHistoryRepository().load()
    warnings = [
        event
        for event in catalogue.events.values()
        if event.event_type is BucketEventType.LEDGER_RATIOS_CENSUS_OVERRIDE_WARNING
    ]
    assert not warnings
