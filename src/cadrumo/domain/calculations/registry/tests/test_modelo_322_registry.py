"""Tests for the committed Modelo 322 (IVA grupos individual) registry foundation."""

from __future__ import annotations

from datetime import date

import pytest

from .....core import IvaDeductionFactKind
from .....core.resources import bundled_path
from ....iva import IvaLedgerObservationRole
from .. import ModeloDefinition, RegistryCatalogues, RegistryValidator, build_snapshot
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


def test_modelo_322_revision_starts_at_2008() -> None:
    modelo, _ = _load_modelo_322()
    revision = modelo.revisions["2008-2025"]
    assert revision.valid_from == date(2008, 1, 1)
    assert revision.period_selector.year_from == 2008
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
        assert snapshot.revision.id == "2008-2025"
        assert snapshot.revision.orden_aplicabilidad == ("orden-eha-3434-2007:art-1",)


def test_modelo_322_january_period_uses_official_calendar_shift() -> None:
    """January 2026 closes on 2026-03-02 in the AEAT 2026 calendar."""
    modelo, _ = _load_modelo_322()
    # Each window is read from the revision that OWNS it. The former single span
    # was split at ejercicio 2026, so the 2026 January window belongs to
    # `2026-y-siguientes` while the 2025 one belongs to `2008-2025`; taking both
    # from one revision only worked while there was only one.
    windows = {w.id: w for w in modelo.revisions["2008-2025"].deadline_windows}
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
    revision = modelo.revisions["2008-2025"]
    windows = {w.id: w for w in revision.deadline_windows}

    jun_2025 = windows["modelo-322-2025-06"]
    assert jun_2025.opens_on == date(2025, 7, 1)
    assert jun_2025.closes_on == date(2025, 7, 30)

    dec_2025 = windows["modelo-322-2025-12"]
    assert dec_2025.opens_on == date(2026, 1, 1)
    assert dec_2025.closes_on == date(2026, 1, 30)


def test_modelo_322_live_cross_references_forbid_writes() -> None:
    modelo, _ = _load_modelo_322()
    revision = modelo.revisions["2008-2025"]
    cross_refs = {ref.id: ref for ref in revision.live_cross_references}

    filed_ref = cross_refs["modelo-322-filed-declarations-read"]
    assert filed_ref.requires_authentication is True
    assert filed_ref.requires_aeat_authorization is True
    assert {"presentation", "signing", "amendment", "payment"}.issubset(set(filed_ref.forbidden_actions))


def test_modelo_322_filing_schedule_is_monthly() -> None:
    modelo, _ = _load_modelo_322()
    revision = modelo.revisions["2008-2025"]
    schedule = next(s for s in revision.filing_schedules if s.id == "modelo-322-mensual")
    assert schedule.period_kind == "monthly"
    assert len(schedule.periods) == 12


def test_modelo_322_construct_links_workbook_parity() -> None:
    modelo, _ = _load_modelo_322()
    revision = modelo.revisions["2008-2025"]
    construct = next(c for c in revision.constructs if c.id == "modelo-322-iva-grupo-individual")
    assert "modelo-322-dr-2026" in construct.workbook_parity_refs
    assert construct.filing_schedules == ("modelo-322-mensual",)


def test_modelo_322_declares_iva_aggregation_bindings_for_all_three_flow_directions() -> None:
    """Modelo 322 declares the same IVA flow-direction binding pattern as
    Modelo 303, scoped to the individual group entity."""
    modelo, _ = _load_modelo_322()
    revision = modelo.revisions["2008-2025"]
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
    from .. import (
        IvaLedgerObservation,
        resolve_ledger_iva_aggregation_binding_values,
    )

    modelo, _ = _load_modelo_322()
    revision = modelo.revisions["2008-2025"]
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
