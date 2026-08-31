"""CLI surface tests for `aeat app ledger ratios {list, set, unset, eligible, validate}`."""

from __future__ import annotations

from collections.abc import Sequence

import pytest
from click.testing import Result

from ....core.i18n.render import tr
from ....tests.cli_runner import invoke_cached_cli
from ....tests.profile_capsule import set_active_test_profile_facts
from ._strict_cli_fixture_support import inventory_isolated_backend

__all__ = ["inventory_isolated_backend"]

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def _invoke_ratios(args: Sequence[str]) -> Result:
    return invoke_cached_cli(["app", "ledger", "ratios", *args])


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

    from ....adapters.persistence.profile.buckets import BucketEventHistoryRepository
    from ....domain.buckets.event import BucketEventType

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

    from ....adapters.persistence.profile.buckets import BucketEventHistoryRepository
    from ....domain.buckets.event import BucketEventType

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
    """Declare the active profile's ``vivienda_office`` m² facts.

    The live censo scrape was retired; censal facts are operator-supplied
    through ``config profile edit``. Writing the m² facts through the
    real profile-edit path gives the ratios_set handler a bound raw
    afectación ratio (``office_m2 / total_m2``) to compare the
    operator-supplied override against.
    """
    from decimal import Decimal

    from ....domain.user_profile.values import UserProfileFact

    facts = (
        UserProfileFact(path="vivienda_office.total_m2", value=Decimal(total_m2)),
        UserProfileFact(path="vivienda_office.office_m2", value=Decimal(office_m2)),
    )
    set_active_test_profile_facts(facts)


def test_ratios_set_emits_censo_override_warning_when_suministros_diverges() -> None:
    """Setting a HOME_OFFICE suministros ratio at a value different from
    raw_afectacion * 0.30 (LIRPF Art. 30.2 rule 5) emits the warning
    event. The set itself still lands — the operator may legitimately
    model a planned change — but the divergence is recorded."""

    from ....adapters.persistence.profile.buckets import BucketEventHistoryRepository
    from ....domain.buckets.event import BucketEventType

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

    from ....adapters.persistence.profile.buckets import BucketEventHistoryRepository
    from ....domain.buckets.event import BucketEventType

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


def test_ratios_list_refuses_a_censo_mismatch_with_typed_no_recovery() -> None:
    """A legally binding censo mismatch cannot fall back to stale rows."""

    _capture_censo_with_vivienda_office(office_m2="20", total_m2="100")
    set_result = _invoke_ratios(["set", "suministros_home_office_luz", "0.5"])
    assert set_result.exit_code == 0, set_result.output

    list_result = _invoke_ratios(["list"])

    assert list_result.exit_code != 0
    assert 'action.failed_condition_id: "cli.ledger.censo_ratio.consistent"' in list_result.output
    assert "action.action: null" in list_result.output
    assert 'action.no_recovery_outcome: "operator_decision"' in list_result.output
    assert "suministros_home_office_luz\t0.5" not in list_result.output


def test_ratios_set_silent_for_non_home_office_category() -> None:
    """The override-warning event is HOME_OFFICE-scoped:
    other categories don't carry the censo-binding contract."""

    from ....adapters.persistence.profile.buckets import BucketEventHistoryRepository
    from ....domain.buckets.event import BucketEventType

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
