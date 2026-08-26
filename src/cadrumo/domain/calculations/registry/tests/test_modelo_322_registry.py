"""Tests for the committed Modelo 322 (IVA grupos individual) registry foundation."""

from __future__ import annotations

from datetime import date

import pytest

from .....core import IvaDeductionFactKind
from .....core.resources import bundled_path
from ....iva import IvaLedgerObservationRole
from .._validate import RegistryValidator
from ..authority import bundled_authority
from ..deadline_coordinate import deadline_semantic_coordinate
from ..schema import ModeloDefinition, RegistryCatalogues
from ..snapshot import build_snapshot
from ..temporal import select_revision
from ._ledger_iva_aggregation_support import _deduction_provenance
from ._registry_schema_support import _committed_modelo

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _load_modelo_322() -> tuple[ModeloDefinition, RegistryCatalogues]:
    return _committed_modelo("322")


def test_modelo_322_validator_accepts_committed_definition() -> None:
    modelo, catalogues = _load_modelo_322()
    assert modelo.id == "322"
    assert modelo.revisions, "322 must declare at least one revision"
    assert any(rev.casillas for rev in modelo.revisions.values()), "322 must declare casillas"
    RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(modelo)


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


def test_modelo_322_2022_revision_is_monthly() -> None:
    modelo, _ = _load_modelo_322()
    revision = modelo.revisions["2008-2022"]
    assert revision.valid_from == date(2022, 1, 1)
    assert revision.period_selector.years == (2022,)
    assert len(revision.period_selector.periods) == 12
    assert revision.orden_aplicabilidad == ("orden-eha-3434-2007:art-1",)


def test_modelo_322_snapshot_builds_for_each_month() -> None:
    modelo, catalogues = _load_modelo_322()
    for period in [f"{m:02d}" for m in range(1, 13)]:
        snapshot = build_snapshot(
            modelo,
            catalogues,
            source_root=bundled_path(),
            filing_year=2025,
            period=period,
        )
        assert snapshot.revision.id == "2024-2025"
        assert snapshot.revision.orden_aplicabilidad == ("orden-eha-3434-2007:art-1",)


def test_modelo_322_january_period_uses_official_calendar_shift() -> None:
    """January 2026 closes on 2026-03-02 in the AEAT 2026 calendar."""
    modelo, _ = _load_modelo_322()
    # Each window is read from the revision that OWNS it. The former single span
    # was split at ejercicio 2026, so the 2026 January window belongs to
    # `2026-y-siguientes` while the 2025 one belongs to `2024-2025`; taking both
    # from one revision only worked while there was only one.
    windows = {w.id: w for w in modelo.revisions["2024-2025"].deadline_windows}
    later_windows = {w.id: w for w in modelo.revisions["2026-y-siguientes"].deadline_windows}

    jan_2025 = windows["modelo-322-2025-01"]
    assert jan_2025.opens_on == date(2025, 2, 1)
    assert jan_2025.closes_on == date(2025, 2, 28)

    jan_2026 = later_windows["modelo-322-2026-01"]
    assert jan_2026.opens_on == date(2026, 2, 1)
    assert jan_2026.closes_on == date(2026, 3, 2)
    assert "aeat-modelo-322-procedure" in jan_2026.source_refs
    assert "aeat-calendario-contribuyente-2026-hasta-2-marzo" in jan_2026.source_refs


def test_modelo_322_other_months_close_within_30_days_of_following_month() -> None:
    modelo, _ = _load_modelo_322()
    revision = modelo.revisions["2024-2025"]
    windows = {w.id: w for w in revision.deadline_windows}

    jun_2025 = windows["modelo-322-2025-06"]
    assert jun_2025.opens_on == date(2025, 7, 1)
    assert jun_2025.closes_on == date(2025, 7, 30)

    dec_2025 = windows["modelo-322-2025-12"]
    assert dec_2025.opens_on == date(2026, 1, 1)
    assert dec_2025.closes_on == date(2026, 1, 30)


def test_modelo_322_2022_deadlines_exactly_match_official_aeat_calendars() -> None:
    """Every selected 2022 month is a separately cited presentation fact."""
    modelo, _ = _load_modelo_322()
    revision = modelo.revisions["2008-2022"]
    windows_by_period = {window.period.registry_token: window for window in revision.deadline_windows}
    expected = {
        "01": (date(2022, 2, 1), date(2022, 2, 28), "aeat-calendario-contribuyente-2022"),
        "02": (date(2022, 3, 1), date(2022, 3, 30), "aeat-calendario-contribuyente-2022"),
        "03": (date(2022, 4, 1), date(2022, 5, 2), "aeat-calendario-contribuyente-2022"),
        "04": (date(2022, 5, 1), date(2022, 5, 30), "aeat-calendario-contribuyente-2022"),
        "05": (date(2022, 6, 1), date(2022, 6, 30), "aeat-calendario-contribuyente-2022"),
        "06": (date(2022, 7, 1), date(2022, 8, 1), "aeat-calendario-contribuyente-2022"),
        "07": (date(2022, 8, 1), date(2022, 8, 30), "aeat-calendario-contribuyente-2022"),
        "08": (date(2022, 9, 1), date(2022, 9, 30), "aeat-calendario-contribuyente-2022"),
        "09": (date(2022, 10, 1), date(2022, 10, 31), "aeat-calendario-contribuyente-2022"),
        "10": (date(2022, 11, 1), date(2022, 11, 30), "aeat-calendario-contribuyente-2022"),
        "11": (date(2022, 12, 1), date(2022, 12, 30), "aeat-calendario-contribuyente-2022"),
        "12": (date(2023, 1, 1), date(2023, 1, 30), "aeat-calendario-contribuyente-2023"),
    }

    assert len(revision.deadline_windows) == len(expected) == 12
    assert set(windows_by_period) == set(expected) == set(revision.period_selector.periods)
    for period, (opens_on, closes_on, calendar_source) in expected.items():
        window = windows_by_period[period]
        assert window.id == f"modelo-322-2022-{period}"
        assert window.filing_year == window.period.filing_year == 2022
        assert window.period_kind == "monthly"
        assert (window.opens_on, window.closes_on, window.payment_cutoff_on) == (opens_on, closes_on, None)
        assert set(window.legal_refs) == {"orden-eha-3434-2007:art-8", "rd-1624-1992:art-71"}
        assert set(window.source_refs) == {
            "boe-modelo-322-2007-form",
            "aeat-modelo-322-procedure",
            calendar_source,
        }


def test_modelo_322_2022_deadlines_have_one_canonical_owner_and_projection() -> None:
    modelo, _ = _load_modelo_322()
    expected_periods = tuple(f"{month:02d}" for month in range(1, 13))

    for period in expected_periods:
        selected = select_revision(modelo, filing_year=2022, period=period)
        owners = [
            revision.id
            for revision in modelo.revisions.values()
            if any(
                window.filing_year == 2022 and window.period.registry_token == period
                for window in revision.deadline_windows
            )
        ]
        assert selected.id == "2008-2022"
        assert owners == [selected.id]

    projected = bundled_authority().deadline_windows(2022, modelos=("322",))
    assert len(projected) == 12
    assert tuple(window.period.registry_token for _, _, window in projected) == expected_periods
    assert {revision.id for _, revision, _ in projected} == {"2008-2022"}


def test_modelo_322_supported_deadlines_are_exact_complete_and_canonically_owned() -> None:
    modelo, _ = _load_modelo_322()
    expected_rows = (
        (2023, "01", "2023-02-01", "2023-02-28", 2023),
        (2023, "02", "2023-03-01", "2023-03-30", 2023),
        (2023, "03", "2023-04-01", "2023-05-02", 2023),
        (2023, "04", "2023-05-01", "2023-05-30", 2023),
        (2023, "05", "2023-06-01", "2023-06-30", 2023),
        (2023, "06", "2023-07-01", "2023-07-31", 2023),
        (2023, "07", "2023-08-01", "2023-08-30", 2023),
        (2023, "08", "2023-09-01", "2023-10-02", 2023),
        (2023, "09", "2023-10-01", "2023-10-30", 2023),
        (2023, "10", "2023-11-01", "2023-11-30", 2023),
        (2023, "11", "2023-12-01", "2024-01-02", 2023),
        (2023, "12", "2024-01-01", "2024-01-30", 2024),
        (2024, "01", "2024-02-01", "2024-02-29", 2024),
        (2024, "02", "2024-03-01", "2024-04-01", 2024),
        (2024, "03", "2024-04-01", "2024-04-30", 2024),
        (2024, "04", "2024-05-01", "2024-05-30", 2024),
        (2024, "05", "2024-06-01", "2024-07-01", 2024),
        (2024, "06", "2024-07-01", "2024-07-30", 2024),
        (2024, "07", "2024-08-01", "2024-08-30", 2024),
        (2024, "08", "2024-09-01", "2024-09-30", 2024),
        (2024, "09", "2024-10-01", "2024-10-30", 2024),
        (2024, "10", "2024-11-01", "2024-12-02", 2024),
        (2024, "11", "2024-12-01", "2024-12-30", 2024),
        (2024, "12", "2025-01-01", "2025-01-30", 2025),
        (2025, "01", "2025-02-01", "2025-02-28", 2025),
        (2025, "02", "2025-03-01", "2025-03-31", 2025),
        (2025, "03", "2025-04-01", "2025-04-30", 2025),
        (2025, "04", "2025-05-01", "2025-05-30", 2025),
        (2025, "05", "2025-06-01", "2025-06-30", 2025),
        (2025, "06", "2025-07-01", "2025-07-30", 2025),
        (2025, "07", "2025-08-01", "2025-09-01", 2025),
        (2025, "08", "2025-09-01", "2025-09-30", 2025),
        (2025, "09", "2025-10-01", "2025-10-30", 2025),
        (2025, "10", "2025-11-01", "2025-12-01", 2025),
        (2025, "11", "2025-12-01", "2025-12-30", 2025),
        (2025, "12", "2026-01-01", "2026-01-30", 2026),
        (2026, "01", "2026-02-01", "2026-03-02", 2026),
        (2026, "02", "2026-03-01", "2026-03-30", 2026),
        (2026, "03", "2026-04-01", "2026-04-30", 2026),
        (2026, "04", "2026-05-01", "2026-06-01", 2026),
        (2026, "05", "2026-06-01", "2026-06-30", 2026),
        (2026, "06", "2026-07-01", "2026-07-30", 2026),
        (2026, "07", "2026-08-01", "2026-08-31", 2026),
        (2026, "08", "2026-09-01", "2026-09-30", 2026),
        (2026, "09", "2026-10-01", "2026-10-30", 2026),
        (2026, "10", "2026-11-01", "2026-11-30", 2026),
        (2026, "11", "2026-12-01", "2026-12-30", 2026),
        (2026, "12", "2027-01-01", "2027-02-01", 2027),
    )
    expected = {
        (year, period): (date.fromisoformat(opens), date.fromisoformat(closes), source_year)
        for year, period, opens, closes, source_year in expected_rows
    }
    authored = {
        (window.filing_year, window.period.registry_token): (revision, window)
        for revision in modelo.revisions.values()
        for window in revision.deadline_windows
        if 2023 <= window.filing_year <= 2026
    }

    assert set(authored) == set(expected)
    for coordinate, (opens_on, closes_on, source_year) in expected.items():
        revision, window = authored[coordinate]
        year, period = coordinate
        assert window.id == f"modelo-322-{year}-{period}"
        assert window.filing_year == window.period.filing_year == year
        assert window.period_kind == "monthly"
        expected_payment = date(2027, 1, 27) if coordinate == (2026, "12") else None
        assert (window.opens_on, window.closes_on, window.payment_cutoff_on) == (
            opens_on,
            closes_on,
            expected_payment,
        )
        expected_source = (
            "aeat-modelo-303-procedure" if source_year == 2027 else f"aeat-calendario-contribuyente-{source_year}"
        )
        assert expected_source in window.source_refs
        assert select_revision(modelo, filing_year=year, period=period) is revision

    for year in range(2023, 2027):
        projected = bundled_authority().deadline_windows(year, modelos=("322",))
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
        if revision.valid_from.year < 2023:
            continue
        construct = next(item for item in revision.constructs if item.id == "modelo-322-iva-grupo-individual")
        assert set(construct.deadline_windows) == {window.id for window in revision.deadline_windows}
        assert {source_ref for window in revision.deadline_windows for source_ref in window.source_refs}.issubset(
            set(construct.source_refs)
        )


def test_modelo_322_live_cross_references_forbid_writes() -> None:
    modelo, _ = _load_modelo_322()
    revision = modelo.revisions["2008-2022"]
    cross_refs = {ref.id: ref for ref in revision.live_cross_references}

    filed_ref = cross_refs["modelo-322-filed-declarations-read"]
    assert filed_ref.requires_authentication is True
    assert filed_ref.requires_aeat_authorization is True
    assert {"presentation", "signing", "amendment", "payment"}.issubset(set(filed_ref.forbidden_actions))


def test_modelo_322_filing_schedule_is_monthly() -> None:
    modelo, _ = _load_modelo_322()
    revision = modelo.revisions["2008-2022"]
    schedule = next(s for s in revision.filing_schedules if s.id == "modelo-322-mensual")
    assert schedule.period_kind == "monthly"
    assert len(schedule.periods) == 12


def test_modelo_322_construct_links_workbook_parity() -> None:
    modelo, _ = _load_modelo_322()
    revision = modelo.revisions["2008-2022"]
    construct = next(c for c in revision.constructs if c.id == "modelo-322-iva-grupo-individual")
    assert "modelo-322-dr-2026" in construct.workbook_parity_refs
    assert construct.filing_schedules == ("modelo-322-mensual",)


def test_modelo_322_declares_iva_aggregation_bindings_for_all_three_flow_directions() -> None:
    """Modelo 322 declares the same IVA flow-direction binding pattern as
    Modelo 303, scoped to the individual group entity."""
    modelo, _ = _load_modelo_322()
    revision = modelo.revisions["2008-2022"]
    iva_bindings = {binding.id: binding for binding in revision.bindings if binding.source == "ledger_iva_aggregation"}
    assert "modelo-322-iva-repercutido-general-cuota" in iva_bindings
    assert "modelo-322-iva-repercutido-reducido-cuota" in iva_bindings
    assert "modelo-322-iva-repercutido-super-reducido-cuota" in iva_bindings
    assert "modelo-322-iva-soportado-interiores-cuota" in iva_bindings
    assert "modelo-322-iva-autorepercutido-intracomunitaria-cuota" in iva_bindings


def test_modelo_322_iva_bindings_resolve_against_ledger_observations() -> None:
    from decimal import Decimal

    from ....iva import (
        IvaCategory,
        IvaFlowDirection,
        IvaRateKind,
    )
    from ..ledger_bindings import (
        IvaLedgerObservation,
        resolve_ledger_iva_aggregation_binding_values,
    )

    modelo, _ = _load_modelo_322()
    revision = modelo.revisions["2008-2022"]
    observations = [
        IvaLedgerObservation(
            ledger_id="rep-1",
            transaction_date=date(2025, 6, 1),
            category=IvaCategory.DOMESTIC_GENERAL,
            rate_kind=IvaRateKind.GENERAL,
            flow_direction=IvaFlowDirection.REPERCUTIDO,
            base_amount=Decimal("5000"),
            iva_amount=Decimal("1050"),
            observation_role=IvaLedgerObservationRole.SETTLEMENT,
        ),
        IvaLedgerObservation(
            ledger_id="sop-1",
            transaction_date=date(2025, 6, 5),
            category=IvaCategory.DOMESTIC_GENERAL,
            rate_kind=IvaRateKind.GENERAL,
            flow_direction=IvaFlowDirection.SOPORTADO,
            base_amount=Decimal("2000"),
            iva_amount=Decimal("420"),
            deduction_fact_kind=IvaDeductionFactKind.DOMESTIC_CURRENT,
            deduction_provenance=_deduction_provenance(
                IvaDeductionFactKind.DOMESTIC_CURRENT,
                source_locator="invoice:sop-1",
            ),
            observation_role=IvaLedgerObservationRole.SETTLEMENT,
        ),
    ]
    result = resolve_ledger_iva_aggregation_binding_values(revision, observations)
    assert result["modelo-322-iva-repercutido-general-cuota"] == Decimal("1050")
    assert result["modelo-322-iva-soportado-interiores-cuota"] == Decimal("420")
    assert result["modelo-322-iva-autorepercutido-intracomunitaria-cuota"] == Decimal("0")
