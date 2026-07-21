"""Tests for the committed Modelo 390 (IVA Resumen Anual) registry foundation."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

import pytest

from .....core.aggregation import BindingAggregationOp, BindingSourceKind
from .....core.resources import bundled_path
from .. import (
    CasillaId,
    InputKind,
    ModeloDefinition,
    ModeloRevision,
    RegistryCatalogues,
    RegistryValidationError,
    RegistryValidator,
    binding_aggregation_op,
    binding_source_casilla_ids,
    expression_casilla_refs,
    validated_casilla_id,
)
from .._binding_selector_utils import selector_as_dict
from .._bindings import binding_source_modelo
from ._registry_schema_support import _committed_modelo, _committed_snapshot

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _casilla_id(value: object) -> CasillaId:
    try:
        return validated_casilla_id(value, surface="test casilla id")
    except ValueError as exc:
        raise AssertionError(f"modelo 390 registry fixture casilla key {value!r} is not a CasillaId") from exc


_M303_CUOTA_DEVENGADA_TOTAL_CASILLA: CasillaId = _casilla_id("iva.cuota-devengada-total")
_M303_CUOTA_DEDUCIBLE_TOTAL_CASILLA: CasillaId = _casilla_id("iva.cuota-deducible-total")
_M303_RESULTADO_REGIMEN_GENERAL_CASILLA: CasillaId = _casilla_id("iva.resultado-regimen-general")
_M303_COMPENSACION_GENERADA_CASILLA: CasillaId = _casilla_id("iva.compensacion-generada-periodo")
_M303_COMPENSACION_APLICADA_CASILLA: CasillaId = _casilla_id("iva.compensacion-aplicada-periodo")
_M303_COMPENSACION_DISPONIBLE_CASILLA: CasillaId = _casilla_id("iva.compensacion-disponible-fin-periodo")
_M303_COMPENSACION_POSTERIOR_CASILLA: CasillaId = _casilla_id(
    "iva.compensacion-pendiente-periodos-posteriores",
)
_M303_PRORRATA_REGULARIZACION_SOURCE_CASILLAS: tuple[CasillaId, ...] = (
    _casilla_id("iva.cuota-deducible-total"),
    _casilla_id("iva.prorrata-volumen-con-derecho"),
    _casilla_id("iva.prorrata-volumen-total"),
    _casilla_id("iva.prorrata-porcentaje"),
)
_M303_PRORRATA_REGULARIZACION_SOURCE_PERIODS = ("1T", "2T", "3T", "4T")
_M390_CUOTA_DEVENGADA_TOTAL_CASILLA: CasillaId = _casilla_id("iva.anual.cuota-devengada-total")
_M390_CUOTA_DEDUCIBLE_TOTAL_CASILLA: CasillaId = _casilla_id("iva.anual.cuota-deducible-total")
_M390_RESULTADO_REGIMEN_GENERAL_CASILLA: CasillaId = _casilla_id("iva.anual.resultado-regimen-general")
_M390_PRORRATA_REGULARIZACION_CASILLA: CasillaId = _casilla_id(
    "iva.anual.regularizacion-prorrata-definitiva",
)
_M390_BIENES_INVERSION_REGULARIZACION_CASILLA: CasillaId = _casilla_id(
    "iva.anual.regularizacion-bienes-inversion",
)
_M390_RECONCILIACION_DEVENGADA_303_CASILLA: CasillaId = _casilla_id(
    "iva.anual.reconciliacion.devengada-303",
)
_M390_RECONCILIACION_DEDUCIBLE_303_CASILLA: CasillaId = _casilla_id(
    "iva.anual.reconciliacion.deducible-303",
)
_M390_RECONCILIACION_RESULTADO_303_CASILLA: CasillaId = _casilla_id(
    "iva.anual.reconciliacion.resultado-303",
)
_M390_COMPENSACION_ULTIMO_PERIODO_CASILLA: CasillaId = _casilla_id(
    "iva.anual.compensacion-ultimo-periodo-97",
)
_M390_COMPENSACION_GENERADA_EJERCICIO_NO_97_CASILLA: CasillaId = _casilla_id(
    "iva.anual.compensacion-generada-ejercicio-no-97",
)
_M390_CONSTRUCT_ID = "modelo-390-iva-resumen-anual"
_M390_RECONCILIATION_PREDICATES = (
    (
        "modelo-390-cuota-devengada-total-equals-reconciliacion-303",
        _M390_CUOTA_DEVENGADA_TOTAL_CASILLA,
        _M390_RECONCILIACION_DEVENGADA_303_CASILLA,
        'equals(["iva.anual.cuota-devengada-total", "iva.anual.reconciliacion.devengada-303"])',
        {
            "ley-37-1992:art-88",
            "ley-37-1992:art-90",
            "ley-37-1992:art-91",
            "rd-1624-1992:art-71",
            "orden-eha-3111-2009:art-1",
        },
    ),
    (
        "modelo-390-cuota-deducible-total-equals-reconciliacion-303",
        _M390_CUOTA_DEDUCIBLE_TOTAL_CASILLA,
        _M390_RECONCILIACION_DEDUCIBLE_303_CASILLA,
        'equals(["iva.anual.cuota-deducible-total", "iva.anual.reconciliacion.deducible-303"])',
        {
            "ley-37-1992:art-17",
            "ley-37-1992:art-84",
            "ley-37-1992:art-92",
            "rd-1624-1992:art-71",
            "orden-eha-3111-2009:art-1",
        },
    ),
    (
        "modelo-390-resultado-regimen-general-equals-reconciliacion-303",
        _M390_RESULTADO_REGIMEN_GENERAL_CASILLA,
        _M390_RECONCILIACION_RESULTADO_303_CASILLA,
        'equals(["iva.anual.resultado-regimen-general", "iva.anual.reconciliacion.resultado-303"])',
        {
            "ley-37-1992:art-88",
            "ley-37-1992:art-92",
            "rd-1624-1992:art-71",
            "orden-eha-3111-2009:art-1",
        },
    ),
)
_M390_EXTRACTION_PROFILE_TARGET_LEGAL_REFS = frozenset(
    {
        "ley-37-1992:art-84",
        "ley-37-1992:art-88",
        "ley-37-1992:art-92",
        "ley-37-1992:art-99",
        "ley-37-1992:art-115",
        "ley-37-1992:art-116",
        "orden-eha-3111-2009:art-1",
        "rd-1624-1992:art-29",
        "rd-1624-1992:art-30",
        "rd-1624-1992:art-71",
    }
)


def _load_modelo_390() -> tuple[ModeloDefinition, RegistryCatalogues]:
    return _committed_modelo("390")


def _replace_revision(modelo: ModeloDefinition, revision: ModeloRevision) -> ModeloDefinition:
    return modelo.model_copy(
        update={
            "revisions": {
                revision_id: revision if revision_id == revision.id else item
                for revision_id, item in modelo.revisions.items()
            },
        },
    )


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
    assert revision.orden_aplicabilidad == ("orden-eha-3111-2009:art-1",)


def test_modelo_390_snapshot_builds_for_each_published_filing_year() -> None:
    for filing_year in (2020, 2021, 2022, 2023, 2024, 2025, 2026):
        snapshot = _committed_snapshot("390", filing_year, "0A")
        assert snapshot.revision.id == "2010-y-siguientes"


def test_modelo_390_snapshot_carries_legal_authority_and_record_design() -> None:
    _, catalogues = _load_modelo_390()
    snapshot = _committed_snapshot("390", 2025, "0A")
    assert "orden-eha-3111-2009:art-1" in snapshot.legal
    assert "orden-eha-3111-2009:art-8" in snapshot.legal
    assert snapshot.revision.orden_aplicabilidad == ("orden-eha-3111-2009:art-1",)
    assert snapshot.legal["orden-eha-3111-2009:art-8"].article == "8"
    assert "aeat-dr-390-2025" in snapshot.sources
    assert "aeat-modelo-390-procedure" in snapshot.sources
    assert "boe-modelo-390-2009-form" in snapshot.sources
    assert catalogues.sources["aeat-modelo-390-procedure"].evidence_tier == "official_source_guidance"
    assert catalogues.sources["boe-modelo-390-2009-form"].evidence_tier == "layout_authority"


def test_modelo_390_extraction_profile_legal_refs_match_target_casillas() -> None:
    modelo, _ = _load_modelo_390()
    revision = modelo.revisions["2010-y-siguientes"]
    casillas_by_id = {casilla.id: casilla for casilla in revision.casillas}

    assert revision.extraction_profiles, revision.id
    profile = next(item for item in revision.extraction_profiles if item.id == "modelo-390-declaracion-pdf")
    target_refs = frozenset(
        legal_ref for target in profile.target_casillas for legal_ref in casillas_by_id[target.casilla_id].legal_refs
    )

    assert target_refs == _M390_EXTRACTION_PROFILE_TARGET_LEGAL_REFS
    assert set(profile.legal_refs) == _M390_EXTRACTION_PROFILE_TARGET_LEGAL_REFS


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
    construct = next(c for c in revision.constructs if c.id == _M390_CONSTRUCT_ID)
    assert "modelo-390-filing" in construct.application_links
    assert "modelo-390-deadline" in construct.application_links
    assert construct.filing_schedules == ("modelo-390-anual",)
    assert "modelo-390-dr-2025" in construct.workbook_parity_refs
    assert "ley-37-1992:art-161" in construct.legal_refs
    assert "ley-37-1992:art-104" in construct.legal_refs
    assert "ley-37-1992:art-105" in construct.legal_refs
    assert "ley-37-1992:art-107" in construct.legal_refs
    assert "ley-37-1992:art-110" in construct.legal_refs


def test_modelo_390_construct_requires_recargo_grounding() -> None:
    modelo, catalogues = _load_modelo_390()
    revision = modelo.revisions["2010-y-siguientes"]
    constructs = tuple(
        construct.model_copy(
            update={"legal_refs": tuple(ref for ref in construct.legal_refs if ref != "ley-37-1992:art-161")},
        )
        if construct.id == _M390_CONSTRUCT_ID
        else construct
        for construct in revision.constructs
    )
    mutated_revision = revision.model_copy(update={"constructs": constructs})
    mutated_modelo = _replace_revision(modelo, mutated_revision)

    with pytest.raises(
        RegistryValidationError,
        match=(
            r"construct 'modelo-390-iva-resumen-anual' does not include legal refs "
            r"\['ley-37-1992:art-161'\] required by formula 'modelo-390-iva-anual-cuota-devengada-total'"
        ),
    ):
        RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(mutated_modelo)


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
        "modelo-390-iva-recargo-equivalencia-general-cuota",
        "modelo-390-iva-recargo-equivalencia-reducido-cuota",
        "modelo-390-iva-recargo-equivalencia-super-reducido-cuota",
    }


def test_modelo_390_declares_annual_reconciliation_predicates() -> None:
    """The annual result totals are blocked when they drift from the four 303s."""
    modelo, _ = _load_modelo_390()
    revision = modelo.revisions["2010-y-siguientes"]
    casilla_ids = {casilla.id for casilla in revision.casillas}
    predicates = {predicate.predicate_id: predicate for predicate in revision.verification_predicates}

    for predicate_id, computed_id, reconciliation_id, expression, legal_refs in _M390_RECONCILIATION_PREDICATES:
        predicate = predicates[predicate_id]
        assert computed_id in casilla_ids
        assert reconciliation_id in casilla_ids
        assert predicate.expression == expression
        assert predicate.finding_kind == "BLOCKING_RULE"
        assert set(str(ref) for ref in predicate.legal_refs) == legal_refs


def test_modelo_390_declares_annual_compensation_result_fields() -> None:
    modelo, _ = _load_modelo_390()
    revision = modelo.revisions["2010-y-siguientes"]
    casillas = {casilla.id: casilla for casilla in revision.casillas}
    bindings = {binding.id: binding for binding in revision.bindings}
    relations = {rel.id: rel for rel in revision.relations}
    compensation_source_ids = (
        _M303_COMPENSACION_GENERADA_CASILLA,
        _M303_COMPENSACION_APLICADA_CASILLA,
        _M303_COMPENSACION_DISPONIBLE_CASILLA,
        _M303_COMPENSACION_POSTERIOR_CASILLA,
    )

    assert casillas[_M390_COMPENSACION_ULTIMO_PERIODO_CASILLA].number == "97"
    assert casillas[_M390_COMPENSACION_GENERADA_EJERCICIO_NO_97_CASILLA].number == "662"
    box_97_binding = bindings["modelo-390-prev-303-compensacion-ultimo-periodo"]
    box_662_binding = bindings["modelo-390-prev-303-compensacion-generada-ejercicio-no-97"]
    assert box_97_binding.source == "iva_compensation_annual_partition"
    box_97_selector: Any = box_97_binding.selector
    assert box_97_selector.source_modelo == "303"
    assert binding_source_casilla_ids(box_97_binding) == compensation_source_ids
    assert box_97_selector.partition_output == "last_period_amount"
    assert box_662_binding.source == "iva_compensation_annual_partition"
    box_662_selector: Any = box_662_binding.selector
    assert box_662_selector.source_modelo == "303"
    assert binding_source_casilla_ids(box_662_binding) == compensation_source_ids
    assert box_662_selector.partition_output == "generated_not_in_last_amount"
    assert "modelo-390-rel-303-compensacion-ultimo-periodo" not in relations
    assert "modelo-390-rel-303-compensacion-generada-ejercicio-no-97" not in relations


def test_modelo_390_declares_prorrata_regularizacion_annual_field() -> None:
    modelo, _ = _load_modelo_390()
    revision = modelo.revisions["2010-y-siguientes"]
    casillas = {casilla.id: casilla for casilla in revision.casillas}
    bindings = {binding.id: binding for binding in revision.bindings}
    export_fields = {
        field.id: field
        for layout in revision.export_layouts
        for record in layout.records
        for field in record.fields
    }

    casilla = casillas[_M390_PRORRATA_REGULARIZACION_CASILLA]
    assert casilla.number == "522"
    assert casilla.input_kind is InputKind.MANUAL
    assert casilla.binding is None
    assert "ley-37-1992:art-104" in casilla.legal_refs
    assert "ley-37-1992:art-105" in casilla.legal_refs
    assert casilla.export_refs == ("modelo-390-page-04-casilla-522",)

    binding = bindings["modelo-390-prorrata-regularizacion-anual"]
    assert binding.source is BindingSourceKind.PRORRATA_REGULARIZACION
    assert binding_source_modelo(binding) == "303"
    assert binding_source_casilla_ids(binding) == _M303_PRORRATA_REGULARIZACION_SOURCE_CASILLAS
    assert selector_as_dict(binding) == {
        "source_modelo": "303",
        "source_casilla_ids": _M303_PRORRATA_REGULARIZACION_SOURCE_CASILLAS,
        "source_periods": _M303_PRORRATA_REGULARIZACION_SOURCE_PERIODS,
        "regularizacion_output": "modelo_390_regularizacion_anual",
    }
    assert binding_aggregation_op(binding) is BindingAggregationOp.SUM
    assert "ley-37-1992:art-104" in binding.legal_refs
    assert "ley-37-1992:art-105" in binding.legal_refs

    field = export_fields["modelo-390-page-04-casilla-522"]
    assert field.casilla_id == _M390_PRORRATA_REGULARIZACION_CASILLA
    assert field.offset == 642
    assert field.length == 17
    assert field.signed is True


def test_modelo_390_declares_bienes_inversion_regularizacion_annual_field() -> None:
    modelo, _ = _load_modelo_390()
    revision = modelo.revisions["2010-y-siguientes"]
    casillas = {casilla.id: casilla for casilla in revision.casillas}
    bindings = {binding.id: binding for binding in revision.bindings}
    export_fields = {
        field.id: field
        for layout in revision.export_layouts
        for record in layout.records
        for field in record.fields
    }

    casilla = casillas[_M390_BIENES_INVERSION_REGULARIZACION_CASILLA]
    assert casilla.number == "63"
    assert casilla.input_kind is InputKind.BOUND
    assert casilla.binding == "modelo-390-bienes-inversion-regularizacion-casilla-63"
    assert "ley-37-1992:art-107" in casilla.legal_refs
    assert "ley-37-1992:art-110" in casilla.legal_refs
    assert casilla.export_refs == ("modelo-390-page-04-casilla-63",)
    assert casillas[_M390_COMPENSACION_GENERADA_EJERCICIO_NO_97_CASILLA].number == "662"

    binding = bindings["modelo-390-bienes-inversion-regularizacion-casilla-63"]
    assert binding.source is BindingSourceKind.BIENES_INVERSION_REGULARIZACION
    assert binding_source_modelo(binding) == "303"
    assert binding_source_casilla_ids(binding) == ()
    assert selector_as_dict(binding) == {
        "source_modelo": "303",
        "regularizacion_output": "modelo_390_casilla_63",
    }
    assert "ley-37-1992:art-107" in binding.legal_refs
    assert "ley-37-1992:art-110" in binding.legal_refs

    field = export_fields["modelo-390-page-04-casilla-63"]
    assert field.casilla_id == _M390_BIENES_INVERSION_REGULARIZACION_CASILLA
    assert field.offset == 625
    assert field.length == 17
    assert field.signed is True


def test_modelo_390_prorrata_regularizacion_is_in_annual_deducible_formula() -> None:
    modelo, _ = _load_modelo_390()
    revision = modelo.revisions["2010-y-siguientes"]
    formula = next(
        item for item in revision.formulas if item.target_casilla_id == _M390_CUOTA_DEDUCIBLE_TOTAL_CASILLA
    )

    assert _M390_PRORRATA_REGULARIZACION_CASILLA in set(expression_casilla_refs(formula.expression))
    assert _M390_BIENES_INVERSION_REGULARIZACION_CASILLA in set(expression_casilla_refs(formula.expression))


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
