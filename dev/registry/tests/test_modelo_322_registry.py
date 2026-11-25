"""Tests for the committed Modelo 322 (IVA grupos individual) registry foundation."""

from __future__ import annotations

from datetime import date

import pytest

from cadrumo.core.iva_deduction_fact import IvaDeductionFactKind
from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.deadline_coordinate import deadline_semantic_coordinate
from cadrumo.domain.calculations.registry.schema import ModeloDefinition
from cadrumo.domain.calculations.registry.schema_catalogues import RegistryCatalogues
from cadrumo.domain.calculations.registry.temporal import select_revision
from cadrumo.domain.calculations.registry.tests.authored_editions import (
    authored_revisions,
    filing_year_envelope,
    open_ended_revision,
)
from cadrumo.domain.calculations.registry.tests.snapshot_support import build_snapshot
from cadrumo.domain.iva.flow import IvaFlowDirection
from cadrumo.domain.iva.schema import IvaCategory, IvaLedgerObservationRole, IvaRateKind
from dev.registry.compiler.authority import compiled_bundled_authority

from ..conformance.registry_schema_support import committed_modelo
from .authored_edition_support import source_first_exercise, source_with_sha256
from .ledger_iva_aggregation_support import ledger_iva_aggregation_deduction_provenance
from .profile_schema_support import committed_registry_validator

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain, pytest.mark.usefixtures("governed_fact_scope")]

# The one exercise the monthly legacy revision still selects: the one whose AEAT
# calendar, found by its pinned bytes, is the cited evidence for every deadline day
# below. December is filed under the following exercise's calendar.
_CALENDAR_EXERCISE = source_first_exercise(
    source_with_sha256("8d84b3067cce798dd6bfb2c83de3cf68bcd6e199ad584802ab9ee09fb9e53a09")
)
_REVISIONS = authored_revisions("322")
_LEGACY_MONTHLY_REVISION = str(_REVISIONS[0].id)
# The two-exercise design and the open-ended one that follows it.
_MIDDLE_REVISION = _REVISIONS[2]
_MIDDLE_ID = str(_MIDDLE_REVISION.id)
_MIDDLE_LAST = _MIDDLE_REVISION.valid_to.year if _MIDDLE_REVISION.valid_to else _MIDDLE_REVISION.valid_from.year
_OPEN_ENDED_REVISION = open_ended_revision("322")
_OPEN_ENDED_ID = str(_OPEN_ENDED_REVISION.id)
_OPEN_ENDED_FIRST = _OPEN_ENDED_REVISION.valid_from.year
# Every exercise after the legacy monthly one, up to the newest the registry supports.
_LATER_EXERCISES = tuple(range(_CALENDAR_EXERCISE + 1, filing_year_envelope().horizon + 1))


def _load_modelo_322() -> tuple[ModeloDefinition, RegistryCatalogues]:
    return committed_modelo("322")


def test_modelo_322_validator_accepts_committed_definition() -> None:
    modelo, catalogues = _load_modelo_322()
    assert modelo.id == "322"
    assert modelo.revisions, "322 must declare at least one revision"
    assert any(rev.casillas for rev in modelo.revisions.values()), "322 must declare casillas"
    committed_registry_validator(catalogues).validate_modelo(modelo)


def test_modelo_322_metadata_matches_orden_eha_3434_2007() -> None:
    modelo, catalogues = _load_modelo_322()
    assert modelo.tax_domain == "iva"
    assert modelo.cadence == "monthly"
    assert modelo.jurisdiction == "ES-AEAT"
    assert "orden-eha-3434-2007:art-1" in modelo.legal_refs
    assert "orden-eha-3434-2007:art-8" in modelo.legal_refs
    assert "aeat-dr-322-2026" in modelo.source_refs
    assert catalogues.sources["aeat-modelo-322-procedure"].evidence_tier == "official_source_guidance"
    assert catalogues.sources["boe-modelo-322-2007-form"].evidence_tier == "layout_authority"


def test_modelo_322_legacy_revision_is_monthly() -> None:
    modelo, _ = _load_modelo_322()
    revision = modelo.revisions[_LEGACY_MONTHLY_REVISION]
    assert revision.valid_from == date(_CALENDAR_EXERCISE, 1, 1)
    assert revision.period_selector.years == (_CALENDAR_EXERCISE,)
    assert len(revision.period_selector.periods) == 12
    assert revision.orden_aplicabilidad == ("orden-eha-3434-2007:art-1",)


def test_modelo_322_snapshot_builds_for_each_month() -> None:
    modelo, catalogues = _load_modelo_322()
    for period in [f"{m:02d}" for m in range(1, 13)]:
        snapshot = build_snapshot(
            modelo,
            catalogues,
            source_root=bundled_path(),
            filing_year=_MIDDLE_LAST,
            period=period,
        )
        assert snapshot.revision.id == _MIDDLE_ID
        assert snapshot.revision.orden_aplicabilidad == ("orden-eha-3434-2007:art-1",)


def test_modelo_322_january_period_uses_official_calendar_shift() -> None:
    """January 2026 closes on 2026-03-02 in the AEAT 2026 calendar."""
    modelo, _ = _load_modelo_322()
    # Each window is read from the revision that OWNS it. The former single span
    # was split at ejercicio 2026, so the 2026 January window belongs to
    # `2026-y-siguientes` while the 2025 one belongs to `2024-2025`; taking both
    # from one revision only worked while there was only one.
    windows = {w.id: w for w in modelo.revisions[_MIDDLE_ID].deadline_windows}
    later_windows = {w.id: w for w in modelo.revisions[_OPEN_ENDED_ID].deadline_windows}

    jan_last_middle = windows[f"modelo-322-{_MIDDLE_LAST}-01"]
    assert jan_last_middle.opens_on == date(_MIDDLE_LAST, 2, 1)
    assert jan_last_middle.closes_on == date(_MIDDLE_LAST, 2, 28)

    jan_first_open = later_windows[f"modelo-322-{_OPEN_ENDED_FIRST}-01"]
    assert jan_first_open.opens_on == date(_OPEN_ENDED_FIRST, 2, 1)
    assert jan_first_open.closes_on == date(_OPEN_ENDED_FIRST, 3, 2)
    assert "aeat-modelo-322-procedure" in jan_first_open.source_refs
    assert f"aeat-calendario-contribuyente-{_OPEN_ENDED_FIRST}-hasta-2-marzo" in jan_first_open.source_refs


def test_modelo_322_other_months_close_within_30_days_of_following_month() -> None:
    modelo, _ = _load_modelo_322()
    revision = modelo.revisions[_MIDDLE_ID]
    windows = {w.id: w for w in revision.deadline_windows}

    jun_last_middle = windows[f"modelo-322-{_MIDDLE_LAST}-06"]
    assert jun_last_middle.opens_on == date(_MIDDLE_LAST, 7, 1)
    assert jun_last_middle.closes_on == date(_MIDDLE_LAST, 7, 30)

    dec_last_middle = windows[f"modelo-322-{_MIDDLE_LAST}-12"]
    assert dec_last_middle.opens_on == date(_MIDDLE_LAST + 1, 1, 1)
    assert dec_last_middle.closes_on == date(_MIDDLE_LAST + 1, 1, 30)


def test_modelo_322_calendar_exercise_deadlines_exactly_match_official_aeat_calendars() -> None:
    """Every selected month is a separately cited presentation fact."""
    year = _CALENDAR_EXERCISE
    calendar, next_calendar = f"aeat-calendario-contribuyente-{year}", f"aeat-calendario-contribuyente-{year + 1}"
    modelo, _ = _load_modelo_322()
    revision = modelo.revisions[_LEGACY_MONTHLY_REVISION]
    windows_by_period = {window.period.registry_token: window for window in revision.deadline_windows}
    expected = {
        "01": (date(year, 2, 1), date(year, 2, 28), calendar),
        "02": (date(year, 3, 1), date(year, 3, 30), calendar),
        "03": (date(year, 4, 1), date(year, 5, 2), calendar),
        "04": (date(year, 5, 1), date(year, 5, 30), calendar),
        "05": (date(year, 6, 1), date(year, 6, 30), calendar),
        "06": (date(year, 7, 1), date(year, 8, 1), calendar),
        "07": (date(year, 8, 1), date(year, 8, 30), calendar),
        "08": (date(year, 9, 1), date(year, 9, 30), calendar),
        "09": (date(year, 10, 1), date(year, 10, 31), calendar),
        "10": (date(year, 11, 1), date(year, 11, 30), calendar),
        "11": (date(year, 12, 1), date(year, 12, 30), calendar),
        "12": (date(year + 1, 1, 1), date(year + 1, 1, 30), next_calendar),
    }

    assert len(revision.deadline_windows) == len(expected) == 12
    assert set(windows_by_period) == set(expected) == set(revision.period_selector.periods)
    for period, (opens_on, closes_on, calendar_source) in expected.items():
        window = windows_by_period[period]
        assert window.id == f"modelo-322-{year}-{period}"
        assert window.filing_year == window.period.filing_year == year
        assert window.period_kind == "monthly"
        assert (window.opens_on, window.closes_on, window.payment_cutoff_on) == (opens_on, closes_on, None)
        assert set(window.legal_refs) == {"orden-eha-3434-2007:art-8", "rd-1624-1992:art-71"}
        assert set(window.source_refs) == {
            "boe-modelo-322-2007-form",
            "aeat-modelo-322-procedure",
            calendar_source,
        }


def test_modelo_322_calendar_exercise_deadlines_have_one_canonical_owner_and_projection() -> None:
    year = _CALENDAR_EXERCISE
    modelo, _ = _load_modelo_322()
    expected_periods = tuple(f"{month:02d}" for month in range(1, 13))

    for period in expected_periods:
        selected = select_revision(modelo, filing_year=year, period=period)
        owners = [
            revision.id
            for revision in modelo.revisions.values()
            if any(
                window.filing_year == year and window.period.registry_token == period
                for window in revision.deadline_windows
            )
        ]
        assert selected.id == _LEGACY_MONTHLY_REVISION
        assert owners == [selected.id]

    projected = compiled_bundled_authority().deadline_windows(year, modelos=("322",))
    assert len(projected) == 12
    assert tuple(window.period.registry_token for _, _, window in projected) == expected_periods
    assert {revision.id for _, revision, _ in projected} == {_LEGACY_MONTHLY_REVISION}


def test_modelo_322_supported_deadlines_are_exact_complete_and_canonically_owned() -> None:
    modelo, _ = _load_modelo_322()
    # Official presentation days of each exercise after the legacy monthly one, recorded in order of exercise:
    # (period, opens year offset, opens month and day, closes year offset, closes month and day, source year offset).
    expected_by_exercise = (
        (
            ("01", 0, 2, 1, 0, 2, 28, 0),
            ("02", 0, 3, 1, 0, 3, 30, 0),
            ("03", 0, 4, 1, 0, 5, 2, 0),
            ("04", 0, 5, 1, 0, 5, 30, 0),
            ("05", 0, 6, 1, 0, 6, 30, 0),
            ("06", 0, 7, 1, 0, 7, 31, 0),
            ("07", 0, 8, 1, 0, 8, 30, 0),
            ("08", 0, 9, 1, 0, 10, 2, 0),
            ("09", 0, 10, 1, 0, 10, 30, 0),
            ("10", 0, 11, 1, 0, 11, 30, 0),
            ("11", 0, 12, 1, 1, 1, 2, 0),
            ("12", 1, 1, 1, 1, 1, 30, 1),
        ),
        (
            ("01", 0, 2, 1, 0, 2, 29, 0),
            ("02", 0, 3, 1, 0, 4, 1, 0),
            ("03", 0, 4, 1, 0, 4, 30, 0),
            ("04", 0, 5, 1, 0, 5, 30, 0),
            ("05", 0, 6, 1, 0, 7, 1, 0),
            ("06", 0, 7, 1, 0, 7, 30, 0),
            ("07", 0, 8, 1, 0, 8, 30, 0),
            ("08", 0, 9, 1, 0, 9, 30, 0),
            ("09", 0, 10, 1, 0, 10, 30, 0),
            ("10", 0, 11, 1, 0, 12, 2, 0),
            ("11", 0, 12, 1, 0, 12, 30, 0),
            ("12", 1, 1, 1, 1, 1, 30, 1),
        ),
        (
            ("01", 0, 2, 1, 0, 2, 28, 0),
            ("02", 0, 3, 1, 0, 3, 31, 0),
            ("03", 0, 4, 1, 0, 4, 30, 0),
            ("04", 0, 5, 1, 0, 5, 30, 0),
            ("05", 0, 6, 1, 0, 6, 30, 0),
            ("06", 0, 7, 1, 0, 7, 30, 0),
            ("07", 0, 8, 1, 0, 9, 1, 0),
            ("08", 0, 9, 1, 0, 9, 30, 0),
            ("09", 0, 10, 1, 0, 10, 30, 0),
            ("10", 0, 11, 1, 0, 12, 1, 0),
            ("11", 0, 12, 1, 0, 12, 30, 0),
            ("12", 1, 1, 1, 1, 1, 30, 1),
        ),
        (
            ("01", 0, 2, 1, 0, 3, 2, 0),
            ("02", 0, 3, 1, 0, 3, 30, 0),
            ("03", 0, 4, 1, 0, 4, 30, 0),
            ("04", 0, 5, 1, 0, 6, 1, 0),
            ("05", 0, 6, 1, 0, 6, 30, 0),
            ("06", 0, 7, 1, 0, 7, 30, 0),
            ("07", 0, 8, 1, 0, 8, 31, 0),
            ("08", 0, 9, 1, 0, 9, 30, 0),
            ("09", 0, 10, 1, 0, 10, 30, 0),
            ("10", 0, 11, 1, 0, 11, 30, 0),
            ("11", 0, 12, 1, 0, 12, 30, 0),
            ("12", 1, 1, 1, 1, 2, 1, 1),
        ),
    )
    assert len(_LATER_EXERCISES) == len(expected_by_exercise)
    expected = {
        (year, period): (
            date(year + opens_offset, opens_month, opens_day),
            date(year + closes_offset, closes_month, closes_day),
            year + source_offset,
        )
        for year, rows in zip(_LATER_EXERCISES, expected_by_exercise, strict=True)
        for period, opens_offset, opens_month, opens_day, closes_offset, closes_month, closes_day, source_offset in rows
    }
    authored = {
        (window.filing_year, window.period.registry_token): (revision, window)
        for revision in modelo.revisions.values()
        for window in revision.deadline_windows
        if window.filing_year in _LATER_EXERCISES
    }

    assert set(authored) == set(expected)
    for coordinate, (opens_on, closes_on, source_year) in expected.items():
        revision, window = authored[coordinate]
        year, period = coordinate
        assert window.id == f"modelo-322-{year}-{period}"
        assert window.filing_year == window.period.filing_year == year
        assert window.period_kind == "monthly"
        expected_payment = date(_LATER_EXERCISES[-1] + 1, 1, 27) if coordinate == (_LATER_EXERCISES[-1], "12") else None
        assert (window.opens_on, window.closes_on, window.payment_cutoff_on) == (
            opens_on,
            closes_on,
            expected_payment,
        )
        expected_source = (
            "aeat-modelo-303-procedure"
            if source_year > _LATER_EXERCISES[-1]
            else f"aeat-calendario-contribuyente-{source_year}"
        )
        assert expected_source in window.source_refs
        assert select_revision(modelo, filing_year=year, period=period) is revision

    for year in _LATER_EXERCISES:
        projected = compiled_bundled_authority().deadline_windows(year, modelos=("322",))
        expected_count = 12
        assert len(projected) == expected_count
        assert (
            len(
                {deadline_semantic_coordinate("322", window.period, None, None) for _, _, window in projected},
            )
            == expected_count
        )


def test_modelo_322_deadline_sources_and_construct_links_are_closed() -> None:
    modelo, _ = _load_modelo_322()
    for revision in modelo.revisions.values():
        if revision.valid_from.year <= _CALENDAR_EXERCISE:
            continue
        construct = next(item for item in revision.constructs if item.id == "modelo-322-iva-grupo-individual")
        assert set(construct.deadline_windows) == {window.id for window in revision.deadline_windows}
        assert {source_ref for window in revision.deadline_windows for source_ref in window.source_refs}.issubset(
            set(construct.source_refs)
        )


def test_modelo_322_live_cross_references_forbid_writes() -> None:
    modelo, _ = _load_modelo_322()
    revision = modelo.revisions[_LEGACY_MONTHLY_REVISION]
    cross_refs = {ref.id: ref for ref in revision.live_cross_references}

    filed_ref = cross_refs["modelo-322-filed-declarations-read"]
    assert filed_ref.requires_authentication is True
    assert filed_ref.requires_aeat_authorization is True
    assert {"presentation", "signing", "amendment", "payment"}.issubset(set(filed_ref.forbidden_actions))


def test_modelo_322_filing_schedule_is_monthly() -> None:
    modelo, _ = _load_modelo_322()
    revision = modelo.revisions[_LEGACY_MONTHLY_REVISION]
    schedule = next(s for s in revision.filing_schedules if s.id == "modelo-322-mensual")
    assert schedule.period_kind == "monthly"
    assert len(schedule.periods) == 12


def test_modelo_322_construct_links_workbook_parity() -> None:
    modelo, _ = _load_modelo_322()
    revision = modelo.revisions[_LEGACY_MONTHLY_REVISION]
    construct = next(c for c in revision.constructs if c.id == "modelo-322-iva-grupo-individual")
    assert "modelo-322-dr" in construct.workbook_parity_refs
    assert construct.filing_schedules == ("modelo-322-mensual",)


def test_modelo_322_declares_iva_aggregation_bindings_for_all_three_flow_directions() -> None:
    """Modelo 322 declares the same IVA flow-direction binding pattern as
    Modelo 303, scoped to the individual group entity."""
    modelo, _ = _load_modelo_322()
    revision = modelo.revisions[_LEGACY_MONTHLY_REVISION]
    iva_bindings = {binding.id: binding for binding in revision.bindings if binding.source == "ledger_iva_aggregation"}
    assert "modelo-322-iva-repercutido-general-cuota" in iva_bindings
    assert "modelo-322-iva-repercutido-reducido-cuota" in iva_bindings
    assert "modelo-322-iva-repercutido-super-reducido-cuota" in iva_bindings
    assert "modelo-322-iva-soportado-interiores-cuota" in iva_bindings
    assert "modelo-322-iva-autorepercutido-intracomunitaria-cuota" in iva_bindings


def test_modelo_322_iva_bindings_resolve_against_ledger_observations() -> None:
    from decimal import Decimal

    from cadrumo.domain.calculations.registry.ledger_iva_bindings import (
        IvaLedgerObservation,
        resolve_ledger_iva_aggregation_binding_values,
    )

    modelo, _ = _load_modelo_322()
    revision = modelo.revisions[_LEGACY_MONTHLY_REVISION]
    observations = [
        IvaLedgerObservation(
            ledger_id="rep-1",
            transaction_date=date(_MIDDLE_LAST, 6, 1),
            category=IvaCategory("domestic_general"),
            rate_kind=IvaRateKind("general"),
            flow_direction=IvaFlowDirection.from_registry("repercutido"),
            base_amount=Decimal("5000"),
            iva_amount=Decimal("1050"),
            observation_role=IvaLedgerObservationRole.SETTLEMENT,
        ),
        IvaLedgerObservation(
            ledger_id="sop-1",
            transaction_date=date(_MIDDLE_LAST, 6, 5),
            category=IvaCategory("domestic_general"),
            rate_kind=IvaRateKind("general"),
            flow_direction=IvaFlowDirection.from_registry("soportado"),
            base_amount=Decimal("2000"),
            iva_amount=Decimal("420"),
            deduction_fact_kind=IvaDeductionFactKind.from_registry("domestic_current"),
            deduction_provenance=ledger_iva_aggregation_deduction_provenance(
                IvaDeductionFactKind.from_registry("domestic_current"),
                source_locator="invoice:sop-1",
            ),
            observation_role=IvaLedgerObservationRole.SETTLEMENT,
        ),
    ]
    result = resolve_ledger_iva_aggregation_binding_values(revision, observations)
    assert result["modelo-322-iva-repercutido-general-cuota"] == Decimal("1050")
    assert result["modelo-322-iva-soportado-interiores-cuota"] == Decimal("420")
    assert result["modelo-322-iva-autorepercutido-intracomunitaria-cuota"] == Decimal("0")
