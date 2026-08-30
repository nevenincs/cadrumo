"""Tests for the committed Modelo 309 (IVA no periódica) registry foundation."""

from __future__ import annotations

from datetime import date
from functools import cache

import pytest

from .....core import IvaDeductionFactKind
from .....core.resources import bundled_path
from ....iva.schema import IvaLedgerObservationRole
from .._validate import RegistryValidator
from ..loader import _load_shared_catalogue_files, load_modelo_directory
from ..schema import ModeloDefinition, RegistryCatalogues
from ..snapshot import build_snapshot
from ._ledger_iva_aggregation_support import _deduction_provenance

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


@cache
def _load_modelo_309() -> tuple[ModeloDefinition, RegistryCatalogues]:
    """Load M309 with every shared catalogue, without unrelated modelos."""
    return (
        load_modelo_directory(bundled_path("registry", "aeat", "modelos", "309")),
        _load_shared_catalogue_files(bundled_path("registry", "aeat", "legal")),
    )


def test_modelo_309_validator_accepts_committed_definition() -> None:
    modelo, catalogues = _load_modelo_309()
    assert modelo.id == "309"
    assert modelo.revisions, "309 must declare at least one revision"
    assert any(rev.casillas for rev in modelo.revisions.values()), "309 must declare casillas"
    RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(modelo)


def test_modelo_309_metadata_matches_orden_hac_3625_2003() -> None:
    modelo, catalogues = _load_modelo_309()
    assert modelo.tax_domain == "iva"
    assert modelo.cadence == "ad_hoc"
    assert "orden-hac-3625-2003:apartado-1" in modelo.legal_refs
    assert "orden-hac-3625-2003:apartado-3" in modelo.legal_refs
    assert "orden-hfp-1245-2022:art-unico" in modelo.legal_refs
    assert {"aeat-dr-309-2004", "aeat-dr-309-2016", "aeat-dr-309-2018", "aeat-dr-309-2023"}.issubset(modelo.source_refs)
    assert "aeat-dr-309-2023" in modelo.source_refs
    assert catalogues.sources["aeat-modelo-309-procedure"].evidence_tier == "official_source_guidance"
    assert catalogues.sources["boe-modelo-309-2003-form"].evidence_tier == "layout_authority"


def test_modelo_309_revision_uses_ad_hoc_period_selector() -> None:
    modelo, _ = _load_modelo_309()
    revision = modelo.revisions["2023-y-siguientes"]
    assert revision.period_selector.year_from == 2023
    assert revision.period_selector.periods == ("AD-HOC",)
    assert revision.orden_aplicabilidad == ("orden-hfp-1245-2022:art-unico",)


def test_modelo_309_snapshot_builds_for_ad_hoc_period() -> None:
    modelo, catalogues = _load_modelo_309()
    snapshot = build_snapshot(modelo, catalogues, source_root=bundled_path(), filing_year=2025, period="AD-HOC")
    assert snapshot.revision.id == "2023-y-siguientes"
    assert snapshot.revision.orden_aplicabilidad == ("orden-hfp-1245-2022:art-unico",)
    assert "orden-hfp-1245-2022:art-unico" in snapshot.legal
    assert "orden-hac-3625-2003:apartado-1" in snapshot.legal
    assert "orden-hac-3625-2003:apartado-3" in snapshot.legal
    assert "aeat-modelo-309-procedure" in snapshot.sources
    assert "boe-modelo-309-2003-form" in snapshot.sources


def test_modelo_309_filing_schedule_is_ad_hoc() -> None:
    modelo, _ = _load_modelo_309()
    revision = modelo.revisions["2023-y-siguientes"]
    schedule = next(s for s in revision.filing_schedules if s.id == "modelo-309-ad-hoc")
    assert schedule.period_kind == "ad_hoc"
    assert schedule.periods == ("AD-HOC",)


def test_modelo_309_live_cross_references_forbid_writes() -> None:
    modelo, _ = _load_modelo_309()
    revision = modelo.revisions["2023-y-siguientes"]
    cross_refs = {ref.id: ref for ref in revision.live_cross_references}
    filed_ref = cross_refs["modelo-309-filed-declarations-read"]
    assert filed_ref.requires_authentication is True
    assert filed_ref.requires_aeat_authorization is True
    assert {"presentation", "signing", "amendment", "payment"}.issubset(set(filed_ref.forbidden_actions))


def test_modelo_309_construct_links_workbook_parity() -> None:
    modelo, _ = _load_modelo_309()
    revision = modelo.revisions["2023-y-siguientes"]
    construct = next(c for c in revision.constructs if c.id == "modelo-309-iva-no-periodica")
    assert "modelo-309-dr-2023" in construct.workbook_parity_refs
    assert construct.filing_schedules == ("modelo-309-ad-hoc",)


def test_modelo_309_declares_autorepercutido_and_recargo_soportado_bindings() -> None:
    """Modelo 309 covers triggered non-periodic IVA — primarily
    intra-community acquisition reverse charge (medios de transporte
    nuevos) and recargo de equivalencia retailers' devoluciones."""
    modelo, _ = _load_modelo_309()
    revision = modelo.revisions["2023-y-siguientes"]
    iva_binding_ids = {binding.id for binding in revision.bindings if binding.source == "ledger_iva_aggregation"}
    assert iva_binding_ids == {
        "modelo-309-iva-autorepercutido-intracomunitaria-cuota",
        "modelo-309-iva-soportado-recargo-equivalencia-cuota",
    }


def test_modelo_309_autorepercutido_binding_resolves_against_substrate() -> None:
    from decimal import Decimal

    from ....iva.flow import IvaFlowDirection
    from ....iva.schema import IvaCategory, IvaRateKind
    from ..ledger_bindings import IvaLedgerObservation, resolve_ledger_iva_aggregation_binding_values

    modelo, _ = _load_modelo_309()
    revision = modelo.revisions["2023-y-siguientes"]
    observations = [
        IvaLedgerObservation(
            ledger_id="vehicle-acquisition",
            transaction_date=date(2025, 6, 1),
            category=IvaCategory.INTRA_COMMUNITY_ACQUISITION_REVERSE_CHARGE,
            rate_kind=IvaRateKind.GENERAL,
            flow_direction=IvaFlowDirection.INVERSION_SUJETO_PASIVO,
            base_amount=Decimal("25000"),
            iva_amount=Decimal("5250"),
            deduction_fact_kind=IvaDeductionFactKind.INTRA_EU_CURRENT,
            deduction_provenance=_deduction_provenance(
                IvaDeductionFactKind.INTRA_EU_CURRENT,
                source_locator="self-assessment:vehicle-acquisition",
            ),
            observation_role=IvaLedgerObservationRole.SETTLEMENT,
        ),
        IvaLedgerObservation(
            ledger_id="recargo-devolucion",
            transaction_date=date(2025, 6, 5),
            category=IvaCategory.RECARGO_EQUIVALENCIA,
            rate_kind=IvaRateKind.GENERAL,
            flow_direction=IvaFlowDirection.SOPORTADO,
            base_amount=Decimal("100"),
            iva_amount=Decimal("21"),
            observation_role=IvaLedgerObservationRole.SETTLEMENT,
        ),
    ]
    result = resolve_ledger_iva_aggregation_binding_values(revision, observations)
    assert result["modelo-309-iva-autorepercutido-intracomunitaria-cuota"] == Decimal("5250")
    assert result["modelo-309-iva-soportado-recargo-equivalencia-cuota"] == Decimal("21")
