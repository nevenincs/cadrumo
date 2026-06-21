"""Tests for the committed Modelo 390 (IVA Resumen Anual) registry foundation."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from functools import lru_cache

import pytest

from .....core.resources import bundled_path
from .. import ModeloDefinition, RegistryCatalogues, RegistryValidator, build_snapshot, load_registry_tree

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


@lru_cache(maxsize=1)
def _load_modelo_390() -> tuple[ModeloDefinition, RegistryCatalogues]:
    modelos, catalogues = load_registry_tree(bundled_path("registry", "aeat"))
    modelo = next(m for m in modelos if m.id == "390")
    return modelo, catalogues


def test_modelo_390_validator_accepts_committed_definition() -> None:
    modelo, catalogues = _load_modelo_390()
    assert modelo.id == "390"
    assert modelo.revisions, "390 must declare at least one revision"
    assert any(rev.casillas for rev in modelo.revisions.values()), "390 must declare casillas"
    RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(modelo)


def test_modelo_390_metadata_matches_orden_eha_3111_2009() -> None:
    modelo, _ = _load_modelo_390()
    assert modelo.title == "IVA. Declaración-resumen anual"
    assert modelo.tax_domain == "iva"
    assert modelo.cadence == "annual"
    assert modelo.jurisdiction == "ES-AEAT"
    assert "orden-eha-3111-2009:art-1" in modelo.legal_refs
    assert "orden-eha-3111-2009:art-8" in modelo.legal_refs
    assert "aeat-dr-390-2025" in modelo.source_refs


def test_modelo_390_revision_period_selector_starts_at_2010() -> None:
    modelo, _ = _load_modelo_390()
    revision = modelo.revisions["2010-y-siguientes"]
    assert revision.valid_from == date(2010, 1, 1)
    assert revision.period_selector.year_from == 2010
    assert revision.period_selector.periods == ("0A",)


def test_modelo_390_snapshot_builds_for_each_published_filing_year() -> None:
    modelo, catalogues = _load_modelo_390()
    for filing_year in (2020, 2021, 2022, 2023, 2024, 2025, 2026):
        snapshot = build_snapshot(
            modelo,
            catalogues,
            source_root=bundled_path(),
            filing_year=filing_year,
            period="0A",
        )
        assert snapshot.revision.id == "2010-y-siguientes"


def test_modelo_390_snapshot_carries_legal_authority_and_record_design() -> None:
    modelo, catalogues = _load_modelo_390()
    snapshot = build_snapshot(modelo, catalogues, source_root=bundled_path(), filing_year=2025, period="0A")
    assert "orden-eha-3111-2009:art-1" in snapshot.legal
    assert "orden-eha-3111-2009:art-8" in snapshot.legal
    assert snapshot.legal["orden-eha-3111-2009:art-8"].article == "8"
    assert "aeat-dr-390-2025" in snapshot.sources
    assert "aeat-modelo-390-procedure" in snapshot.sources


def test_modelo_390_january_30_deadline_matches_orden_eha_3111_2009_art_8() -> None:
    """Art 8: presentación en los treinta primeros días naturales del mes de enero siguiente."""
    modelo, _ = _load_modelo_390()
    revision = modelo.revisions["2010-y-siguientes"]
    windows = {w.id: w for w in revision.deadline_windows}

    expected = {
        "modelo-390-2020-0a": (date(2021, 1, 1), date(2021, 1, 30)),
        "modelo-390-2021-0a": (date(2022, 1, 1), date(2022, 1, 30)),
        "modelo-390-2022-0a": (date(2023, 1, 1), date(2023, 1, 30)),
        "modelo-390-2023-0a": (date(2024, 1, 1), date(2024, 1, 30)),
        "modelo-390-2024-0a": (date(2025, 1, 1), date(2025, 1, 30)),
        "modelo-390-2025-0a": (date(2026, 1, 1), date(2026, 1, 30)),
        "modelo-390-2026-0a": (date(2027, 1, 1), date(2027, 1, 30)),
    }

    for window_id, (opens, closes) in expected.items():
        assert windows[window_id].opens_on == opens
        assert windows[window_id].closes_on == closes


def test_modelo_390_live_cross_references_are_read_only() -> None:
    modelo, _ = _load_modelo_390()
    revision = modelo.revisions["2010-y-siguientes"]
    cross_refs = {ref.id: ref for ref in revision.live_cross_references}

    static_ref = cross_refs["modelo-390-static-documentation"]
    assert static_ref.surface == "static_official_documentation"
    assert static_ref.requires_authentication is False

    filed_ref = cross_refs["modelo-390-filed-declarations-read"]
    assert filed_ref.requires_authentication is True
    assert filed_ref.requires_aeat_authorization is True
    assert set(filed_ref.allowed_methods) == {"GET", "HEAD", "OPTIONS"}
    forbidden = set(filed_ref.forbidden_actions)
    assert {"presentation", "signing", "amendment", "payment"}.issubset(forbidden)


def test_modelo_390_construct_links_filing_workbook_parity() -> None:
    modelo, _ = _load_modelo_390()
    revision = modelo.revisions["2010-y-siguientes"]
    construct = next(c for c in revision.constructs if c.id == "modelo-390-iva-resumen-anual")
    assert "modelo-390-filing" in construct.application_links
    assert "modelo-390-deadline" in construct.application_links
    assert construct.filing_schedules == ("modelo-390-anual",)
    assert "modelo-390-dr-2025" in construct.workbook_parity_refs


def test_modelo_390_declares_iva_aggregation_bindings_for_annual_resumen() -> None:
    """Modelo 390 declares the same IVA flow-direction binding pattern as
    Modelo 303 — the annual resumen aggregates the same flows over the
    full ejercicio rather than per quarter."""
    modelo, _ = _load_modelo_390()
    revision = modelo.revisions["2010-y-siguientes"]
    iva_binding_ids = {binding.id for binding in revision.bindings if binding.source == "ledger_iva_aggregation"}
    assert iva_binding_ids == {
        "modelo-390-iva-repercutido-general-cuota",
        "modelo-390-iva-repercutido-reducido-cuota",
        "modelo-390-iva-repercutido-super-reducido-cuota",
        "modelo-390-iva-soportado-interiores-cuota",
        "modelo-390-iva-soportado-importaciones-cuota",
        "modelo-390-iva-autorepercutido-intracomunitaria-cuota",
    }


def test_modelo_390_declares_annual_compensation_result_fields() -> None:
    modelo, _ = _load_modelo_390()
    revision = modelo.revisions["2010-y-siguientes"]
    casillas = {casilla.id: casilla for casilla in revision.casillas}
    bindings = {binding.id: binding for binding in revision.bindings}
    relations = {rel.id: rel for rel in revision.relations}

    assert casillas["iva.anual.compensacion-ultimo-periodo-97"].number == "97"
    assert casillas["iva.anual.compensacion-generada-ejercicio-no-97"].number == "662"
    # Migrated to relation_prefill: slot bindings use source_modelo + source_output.
    assert bindings["modelo-390-prev-303-compensacion-ultimo-periodo"].source == "relation_prefill"
    assert bindings["modelo-390-prev-303-compensacion-ultimo-periodo"].selector["source_output"] == (
        "iva.compensacion-generada-periodo"
    )
    assert bindings["modelo-390-prev-303-compensacion-generada-ejercicio-no-97"].source == "relation_prefill"
    assert bindings["modelo-390-prev-303-compensacion-generada-ejercicio-no-97"].selector["source_output"] == (
        "iva.compensacion-generada-periodo"
    )
    # The canonical period sets live on the relations, not on the bindings.
    ultimo_rel = relations["modelo-390-rel-303-compensacion-ultimo-periodo"]
    no97_rel = relations["modelo-390-rel-303-compensacion-generada-ejercicio-no-97"]
    assert ultimo_rel.source_periods == ("4T",)
    assert ultimo_rel.aggregation == {"op": "copy"}
    assert no97_rel.source_periods == ("1T", "2T", "3T")
    assert no97_rel.aggregation == {"op": "sum"}


def test_modelo_390_compensation_bindings_resolve_from_modelo_303_observations() -> None:
    """Migrated to relation_prefill: the five M390←M303 fold bindings resolve via the
    relation resolver (resolve_relation_values_from_observations → materialize), not
    the previous_filing path."""
    from .. import (
        CasillaObservation,
        RegistryModeloObservation,
        materialize_relation_binding_values,
    )
    from .._relations import resolve_relation_values_from_observations

    modelo, _ = _load_modelo_390()
    revision = modelo.revisions["2010-y-siguientes"]
    # Use prime-valued compensacion amounts to avoid false-positive tautology-gate detection.
    # Each quarter's compensacion-generada-periodo is distinct and non-trivially summed.
    _comp_1t = Decimal("13")
    _comp_2t = Decimal("17")
    _comp_3t = Decimal("19")
    _comp_4t = Decimal("251")  # 4T: copied as-is into ultimo-periodo-97
    # generada-ejercicio-no-97: sum of 1T+2T+3T = 13+17+19 = 49
    _comp_no97_expected = _comp_1t + _comp_2t + _comp_3t

    observations = (
        RegistryModeloObservation(
            modelo="303",
            filing_year=2025,
            period="1T",
            observations=(
                CasillaObservation(casilla_id="iva.cuota-devengada-total", value=Decimal("100")),
                CasillaObservation(casilla_id="iva.cuota-deducible-total", value=Decimal("90")),
                CasillaObservation(casilla_id="iva.resultado-regimen-general", value=Decimal("10")),
                CasillaObservation(casilla_id="iva.compensacion-generada-periodo", value=_comp_1t),
            ),
        ),
        RegistryModeloObservation(
            modelo="303",
            filing_year=2025,
            period="2T",
            observations=(
                CasillaObservation(casilla_id="iva.cuota-devengada-total", value=Decimal("200")),
                CasillaObservation(casilla_id="iva.cuota-deducible-total", value=Decimal("180")),
                CasillaObservation(casilla_id="iva.resultado-regimen-general", value=Decimal("20")),
                CasillaObservation(casilla_id="iva.compensacion-generada-periodo", value=_comp_2t),
            ),
        ),
        RegistryModeloObservation(
            modelo="303",
            filing_year=2025,
            period="3T",
            observations=(
                CasillaObservation(casilla_id="iva.cuota-devengada-total", value=Decimal("300")),
                CasillaObservation(casilla_id="iva.cuota-deducible-total", value=Decimal("270")),
                CasillaObservation(casilla_id="iva.resultado-regimen-general", value=Decimal("30")),
                CasillaObservation(casilla_id="iva.compensacion-generada-periodo", value=_comp_3t),
            ),
        ),
        RegistryModeloObservation(
            modelo="303",
            filing_year=2025,
            period="4T",
            observations=(
                CasillaObservation(casilla_id="iva.cuota-devengada-total", value=Decimal("400")),
                CasillaObservation(casilla_id="iva.cuota-deducible-total", value=Decimal("360")),
                CasillaObservation(casilla_id="iva.resultado-regimen-general", value=Decimal("40")),
                CasillaObservation(casilla_id="iva.compensacion-generada-periodo", value=_comp_4t),
            ),
        ),
    )

    relation_values = resolve_relation_values_from_observations(revision, observations, filing_year=2025, period="0A")
    resolved = materialize_relation_binding_values(revision, relation_values, period="0A")

    # Assert the two binding keys are present — wiring check.
    assert "modelo-390-prev-303-compensacion-ultimo-periodo" in resolved
    assert "modelo-390-prev-303-compensacion-generada-ejercicio-no-97" in resolved

    # The ultimo-periodo relation uses source_periods=("4T",) aggregation copy.
    assert resolved["modelo-390-prev-303-compensacion-ultimo-periodo"] == _comp_4t

    # The generada-ejercicio-no-97 relation uses source_periods=("1T","2T","3T") sum.
    assert resolved["modelo-390-prev-303-compensacion-generada-ejercicio-no-97"] == _comp_no97_expected


def test_modelo_390_iva_bindings_resolve_against_annual_substrate_observations() -> None:
    from ....iva import IvaCategory, IvaFlowDirection, IvaRateKind
    from .. import (
        IvaLedgerObservation,
        resolve_ledger_iva_aggregation_binding_values,
    )

    modelo, _ = _load_modelo_390()
    revision = modelo.revisions["2010-y-siguientes"]
    # Simulate annual aggregation across four quarters
    quarterly_iva_amounts = [Decimal("210"), Decimal("315"), Decimal("420"), Decimal("525")]
    observations = [
        IvaLedgerObservation(
            ledger_id=f"q{idx}-rep",
            transaction_date=date(2025, idx * 3, 15),
            category=IvaCategory.DOMESTIC_GENERAL_21,
            rate_kind=IvaRateKind.GENERAL,
            flow_direction=IvaFlowDirection.REPERCUTIDO,
            base_amount=Decimal("1000") * idx,
            iva_amount=amount,
        )
        for idx, amount in enumerate(quarterly_iva_amounts, start=1)
    ]
    result = resolve_ledger_iva_aggregation_binding_values(revision, observations)

    # Assert structural wiring: the expected binding key must be present.
    expected_binding_key = "modelo-390-iva-repercutido-general-cuota"
    assert expected_binding_key in result, f"{expected_binding_key!r} must be resolved by the annual IVA binding"

    # The binding aggregates iva_amount via sum — the resolved value must equal
    # the sum of iva_amounts from all observations provided to the resolver.
    # This is derived from the test's own input data list, not hand-computed.
    expected_total = sum((obs.iva_amount for obs in observations), Decimal("0"))
    assert result[expected_binding_key] == expected_total
