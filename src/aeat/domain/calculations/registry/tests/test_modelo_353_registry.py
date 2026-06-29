"""Tests for the committed Modelo 353 (IVA grupos agregado) registry foundation."""

from __future__ import annotations

from datetime import date
from functools import lru_cache

import pytest

from .....core.resources import bundled_path
from .. import ModeloDefinition, RegistryCatalogues, RegistryValidator, build_snapshot, load_registry_tree

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


@lru_cache(maxsize=1)
def _load_modelo_353() -> tuple[ModeloDefinition, RegistryCatalogues]:
    modelos, catalogues = load_registry_tree(bundled_path("registry", "aeat"))
    modelo = next(m for m in modelos if m.id == "353")
    return modelo, catalogues


def test_modelo_353_validator_accepts_committed_definition() -> None:
    modelo, catalogues = _load_modelo_353()
    assert modelo.id == "353"
    assert modelo.revisions, "353 must declare at least one revision"
    assert any(rev.casillas for rev in modelo.revisions.values()), "353 must declare casillas"
    RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(modelo)


def test_modelo_353_metadata_matches_orden_eha_3434_2007() -> None:
    modelo, _ = _load_modelo_353()
    assert modelo.tax_domain == "iva"
    assert modelo.cadence == "monthly"
    assert "orden-eha-3434-2007:art-2" in modelo.legal_refs
    assert "orden-eha-3434-2007:art-8" in modelo.legal_refs
    assert "aeat-dr-353-2026" in modelo.source_refs


def test_modelo_353_revision_is_monthly_from_2008() -> None:
    modelo, _ = _load_modelo_353()
    revision = modelo.revisions["2008-y-siguientes"]
    assert revision.valid_from == date(2008, 1, 1)
    assert len(revision.period_selector.periods) == 12


def test_modelo_353_january_deadline_uses_official_calendar_shift() -> None:
    modelo, _ = _load_modelo_353()
    revision = modelo.revisions["2008-y-siguientes"]
    windows = {w.id: w for w in revision.deadline_windows}
    jan_2025 = windows["modelo-353-2025-01"]
    assert jan_2025.opens_on == date(2025, 2, 1)
    assert jan_2025.closes_on == date(2025, 2, 28)

    jan_2026 = windows["modelo-353-2026-01"]
    assert jan_2026.opens_on == date(2026, 2, 1)
    assert jan_2026.closes_on == date(2026, 3, 2)
    assert jan_2026.payment_cutoff_on == date(2026, 2, 25)
    assert "aeat-calendario-contribuyente-2026-hasta-2-marzo" in jan_2026.source_refs
    assert "aeat-calendario-contribuyente-2026-domiciliacion" in jan_2026.source_refs


def test_modelo_353_other_months_close_at_30_days_following_month() -> None:
    modelo, _ = _load_modelo_353()
    revision = modelo.revisions["2008-y-siguientes"]
    windows = {w.id: w for w in revision.deadline_windows}
    jun = windows["modelo-353-2025-06"]
    assert jun.opens_on == date(2025, 7, 1)
    assert jun.closes_on == date(2025, 7, 30)


def test_modelo_353_snapshot_builds_per_month() -> None:
    modelo, catalogues = _load_modelo_353()
    snapshot = build_snapshot(modelo, catalogues, source_root=bundled_path(), filing_year=2025, period="06")
    assert snapshot.revision.id == "2008-y-siguientes"
    assert "orden-eha-3434-2007:art-2" in snapshot.legal


def test_modelo_353_live_cross_references_forbid_writes() -> None:
    modelo, _ = _load_modelo_353()
    revision = modelo.revisions["2008-y-siguientes"]
    cross_refs = {ref.id: ref for ref in revision.live_cross_references}
    filed_ref = cross_refs["modelo-353-filed-declarations-read"]
    assert filed_ref.requires_authentication is True
    assert filed_ref.requires_aeat_authorization is True


def test_modelo_353_construct_links_workbook_parity() -> None:
    modelo, _ = _load_modelo_353()
    revision = modelo.revisions["2008-y-siguientes"]
    construct = next(c for c in revision.constructs if c.id == "modelo-353-iva-grupo-agregado")
    assert "modelo-353-dr-2026" in construct.workbook_parity_refs


def test_modelo_353_declares_iva_aggregation_bindings() -> None:
    modelo, _ = _load_modelo_353()
    revision = modelo.revisions["2008-y-siguientes"]
    iva_binding_ids = {binding.id for binding in revision.bindings if binding.source == "ledger_iva_aggregation"}
    assert iva_binding_ids == {
        "modelo-353-iva-repercutido-general-cuota",
        "modelo-353-iva-repercutido-reducido-cuota",
        "modelo-353-iva-repercutido-super-reducido-cuota",
        "modelo-353-iva-soportado-interiores-cuota",
        "modelo-353-iva-autorepercutido-intracomunitaria-cuota",
    }


def test_modelo_353_iva_bindings_resolve_against_substrate_observations() -> None:
    from decimal import Decimal

    from ....iva import IvaCategory, IvaFlowDirection, IvaRateKind
    from .. import (
        IvaLedgerObservation,
        resolve_ledger_iva_aggregation_binding_values,
    )

    modelo, _ = _load_modelo_353()
    revision = modelo.revisions["2008-y-siguientes"]
    observations = [
        IvaLedgerObservation(
            ledger_id="agg-rep-1",
            transaction_date=date(2025, 6, 1),
            category=IvaCategory.DOMESTIC_GENERAL_21,
            rate_kind=IvaRateKind.GENERAL,
            flow_direction=IvaFlowDirection.REPERCUTIDO,
            base_amount=Decimal("8000"),
            iva_amount=Decimal("1680"),
        ),
        IvaLedgerObservation(
            ledger_id="agg-sop-1",
            transaction_date=date(2025, 6, 5),
            category=IvaCategory.DOMESTIC_GENERAL_21,
            rate_kind=IvaRateKind.GENERAL,
            flow_direction=IvaFlowDirection.SOPORTADO,
            base_amount=Decimal("3000"),
            iva_amount=Decimal("630"),
        ),
    ]
    result = resolve_ledger_iva_aggregation_binding_values(revision, observations)
    assert result["modelo-353-iva-repercutido-general-cuota"] == Decimal("1680")
    assert result["modelo-353-iva-soportado-interiores-cuota"] == Decimal("630")
