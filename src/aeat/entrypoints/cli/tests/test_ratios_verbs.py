"""CLI surface tests for `aeat app ledger ratios {list, set, unset, eligible, validate}`."""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from pathlib import Path

import pytest
from click.testing import Result

from ....application.user_profile._orchestration import profile_create_storage_span
from ....application.user_profile._testing import register_minimal_profile
from ....application.workflow._persistence import workflow_state_repository
from ....core import resolve_active_bucket_id
from ....core.config import Settings
from ....core.i18n import tr
from ....tests.cli_runner import invoke_cached_cli
from ....tests.secure_sql import isolated_profile_storage_root

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]
_AEAT = Settings.external_constants().aeat
_G313_URL = f"{_AEAT.domains.sede}{_AEAT.sede_paths.censo_g313_launcher}"


def _invoke_ratios(args: Sequence[str]) -> Result:
    return invoke_cached_cli(["app", "ledger", "ratios", *args])


@pytest.fixture(autouse=True)
def _isolated_backend(tmp_path: Path) -> Iterator[None]:
    with (
        isolated_profile_storage_root(tmp_path=tmp_path),
        profile_create_storage_span("default"),
    ):
        workflow_state_repository().update(lambda state: register_minimal_profile(state, profile_id="default"))
        yield


def test_ratios_list_starts_empty() -> None:
    result = _invoke_ratios(["list"])
    assert result.exit_code == 0, result.output
    assert "count\t0" in result.output


def test_ratios_set_persists_and_list_reflects() -> None:
    set_result = _invoke_ratios(["set", "vehiculo_combustible", "0.5"])
    assert set_result.exit_code == 0, set_result.output
    assert "vehiculo_combustible\t0.5" in set_result.output

    list_result = _invoke_ratios(["list"])
    assert list_result.exit_code == 0, list_result.output
    assert "count\t1" in list_result.output
    assert "vehiculo_combustible\t0.5" in list_result.output


def test_ratios_unset_clears() -> None:
    _invoke_ratios(["set", "vehiculo_combustible", "0.5"])
    result = _invoke_ratios(["unset", "vehiculo_combustible"])
    assert result.exit_code == 0, result.output
    assert "vehiculo_combustible\t<unset>" in result.output

    list_result = _invoke_ratios(["list"])
    assert "count\t0" in list_result.output


def test_ratios_unset_refuses_unknown_override() -> None:
    result = _invoke_ratios(["unset", "vehiculo_combustible"])
    assert result.exit_code != 0


def test_ratios_set_refuses_unknown_category() -> None:
    result = _invoke_ratios(["set", "NOT_A_CATEGORY", "0.5"])
    assert result.exit_code != 0


def test_ratios_set_refuses_out_of_bounds() -> None:
    result = _invoke_ratios(["set", "vehiculo_combustible", "1.5"])
    assert result.exit_code != 0


def test_ratios_set_refuses_non_decimal_with_localized_message() -> None:
    result = _invoke_ratios(["set", "vehiculo_combustible", "not-decimal"])

    assert result.exit_code != 0
    # Click renders the refusal inside a wrapped error box, so the long message
    # (which now carries the expected-format hint) is split across box lines with
    # vertical-border glyphs inserted at the wrap points. Strip the box-drawing
    # glyphs and collapse whitespace on both sides before matching so the
    # localized label/raw/hint payload is asserted without depending on the wrap
    # column or the box rendering.
    box_glyphs = "│┌┐└┘─╔╗╚╝║═"
    expected = " ".join(tr("cli.ledger.errors.invalid_decimal", label="ratio", raw="not-decimal").split())
    rendered = " ".join(result.output.translate({ord(g): " " for g in box_glyphs}).split())
    assert expected in rendered


def test_ratios_eligible_lists_categories() -> None:
    result = _invoke_ratios(["eligible"])
    assert result.exit_code == 0, result.output
    assert "vehiculo_" in result.output or "telefonia_" in result.output


def test_ratios_validate_reports_clean_when_empty() -> None:
    result = _invoke_ratios(["validate"])
    assert result.exit_code == 0, result.output
    assert "profile_present\tFalse" in result.output


def test_ratios_set_emits_ledger_ratios_set_event() -> None:
    """`ratios set` records a typed LEDGER_RATIOS_SET event in the bucket
    history so downstream auditors can replay the override sequence."""

    from ....domain.buckets import BucketEventHistoryRepository, BucketEventType

    set_result = _invoke_ratios(["set", "vehiculo_combustible", "0.5"])
    assert set_result.exit_code == 0, set_result.output

    catalogue = BucketEventHistoryRepository().load()
    matching = [
        event
        for event in catalogue.events.values()
        if event.event_type is BucketEventType.LEDGER_RATIOS_SET and event.object_id == "vehiculo_combustible"
    ]
    assert matching, [event.event_type for event in catalogue.events.values()]
    assert matching[-1].payload["new"] == "0.5"
    assert matching[-1].payload["prior"] == ""


def test_ratios_unset_emits_ledger_ratios_unset_event() -> None:
    """`ratios unset` records a typed LEDGER_RATIOS_UNSET event with the
    prior ratio value so the operator-visible mutation cannot be replayed
    only from the secure-object snapshot."""

    from ....domain.buckets import BucketEventHistoryRepository, BucketEventType

    _invoke_ratios(["set", "vehiculo_combustible", "0.5"])
    unset_result = _invoke_ratios(["unset", "vehiculo_combustible"])
    assert unset_result.exit_code == 0, unset_result.output

    catalogue = BucketEventHistoryRepository().load()
    matching = [
        event
        for event in catalogue.events.values()
        if event.event_type is BucketEventType.LEDGER_RATIOS_UNSET and event.object_id == "vehiculo_combustible"
    ]
    assert matching
    assert matching[-1].payload["prior"] == "0.5"
    assert matching[-1].payload["new"] == ""


def _capture_censo_with_vivienda_office(office_m2: str, total_m2: str) -> None:
    """Capture a censo snapshot for the active profile with the supplied m².

    Used by censo-override-warning tests so the ratios_set handler has
    a bound raw afectación ratio to compare the operator-supplied value
    against.
    """

    from datetime import UTC, datetime

    from ....application.live._censo import CensoSnapshotService

    bucket_id = resolve_active_bucket_id() or ""
    service = CensoSnapshotService(bucket_id=bucket_id)
    service.capture(
        profile_id=bucket_id,
        captured_at=datetime.now(UTC),
        source_url=_G313_URL,
        censo_facts={
            "vivienda_office.total_m2": total_m2,
            "vivienda_office.office_m2": office_m2,
        },
    )


def test_ratios_set_emits_censo_override_warning_when_suministros_diverges() -> None:
    """Setting a HOME_OFFICE suministros ratio at a value different from
    raw_afectacion * 0.30 (LIRPF Art. 30.2 rule 5) emits the warning
    event. The set itself still lands — the operator may legitimately
    model a planned change — but the divergence is recorded."""

    from ....domain.buckets import BucketEventHistoryRepository, BucketEventType

    _capture_censo_with_vivienda_office(office_m2="20", total_m2="100")

    set_result = _invoke_ratios(["set", "suministros_home_office_luz", "0.5"])
    assert set_result.exit_code == 0, set_result.output

    catalogue = BucketEventHistoryRepository().load()
    warnings = [
        event
        for event in catalogue.events.values()
        if event.event_type is BucketEventType.LEDGER_RATIOS_CENSO_OVERRIDE_WARNING
        and event.object_id == "suministros_home_office_luz"
    ]
    assert warnings, (
        "LEDGER_RATIOS_CENSO_OVERRIDE_WARNING must fire when the operator "
        "overrides a suministros ratio away from the LIRPF Art. 30.2 rule 5 value"
    )
    payload = warnings[-1].payload
    assert payload["override_ratio"] == "0.5"
    assert payload["censo_derived_ratio"] == "0.060"
    assert payload["raw_afectacion_ratio"] == "0.2"


def test_ratios_set_silent_when_suministros_override_matches_30pct_of_raw() -> None:
    """When the operator sets the legally-correct value (raw * 0.30),
    no warning fires. Witnesses that the warning isn't spuriously
    emitted on every HOME_OFFICE set."""

    from ....domain.buckets import BucketEventHistoryRepository, BucketEventType

    _capture_censo_with_vivienda_office(office_m2="20", total_m2="100")

    set_result = _invoke_ratios(["set", "suministros_home_office_luz", "0.06"])
    assert set_result.exit_code == 0, set_result.output

    catalogue = BucketEventHistoryRepository().load()
    warnings = [
        event
        for event in catalogue.events.values()
        if event.event_type is BucketEventType.LEDGER_RATIOS_CENSO_OVERRIDE_WARNING
    ]
    assert not warnings, "no warning should fire when the override exactly matches the censo-derived value"


def test_ratios_list_surfaces_censo_mismatch_without_hiding_rows() -> None:
    """list now routes through load_usage_ratios_with_censo_guard. If
    the persisted HOME_OFFICE override disagrees with the bound censo,
    a typed censo_mismatch warning row is emitted alongside the regular
    rows — operators see both the persisted value AND the divergence
    against AEAT, never one without the other."""

    _capture_censo_with_vivienda_office(office_m2="20", total_m2="100")
    set_result = _invoke_ratios(["set", "suministros_home_office_luz", "0.5"])
    assert set_result.exit_code == 0, set_result.output

    list_result = _invoke_ratios(["list"])

    assert list_result.exit_code == 0, list_result.output
    assert "suministros_home_office_luz\t0.5" in list_result.output
    assert "censo_mismatch" in list_result.output
    assert "suministros_home_office_luz" in list_result.output


def test_ratios_set_silent_for_non_home_office_category() -> None:
    """The override-warning event is HOME_OFFICE-scoped:
    other categories don't carry the censo-binding contract."""

    from ....domain.buckets import BucketEventHistoryRepository, BucketEventType

    _capture_censo_with_vivienda_office(office_m2="20", total_m2="100")

    set_result = _invoke_ratios(["set", "vehiculo_combustible", "0.9"])
    assert set_result.exit_code == 0, set_result.output

    catalogue = BucketEventHistoryRepository().load()
    warnings = [
        event
        for event in catalogue.events.values()
        if event.event_type is BucketEventType.LEDGER_RATIOS_CENSO_OVERRIDE_WARNING
    ]
    assert not warnings
