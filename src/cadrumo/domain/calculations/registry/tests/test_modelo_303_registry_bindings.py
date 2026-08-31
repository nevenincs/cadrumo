"""Tests for Modelo 303 registry bindings and live registry surfaces."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from .....core.aggregation import BindingAggregationOp, BindingSourceKind
from .....core.iva_deduction_fact import IvaDeductionEvidenceAuthority, IvaDeductionFactKind
from ....iva.deduction_facts import IvaDeductionClassificationProvenance
from ....iva.schema import IvaLedgerObservationRole
from ..binding_aggregation import binding_aggregation_op
from ..binding_selector_utils import selector_as_dict
from ..bindings import binding_source_casilla_ids, binding_source_modelo
from ..runtime_graph import expression_casilla_refs
from ..schema_input_kind import InputKind
from ._modelo_303_registry_support import (
    _M303_BIENES_INVERSION_REGULARIZACION_BINDING,
    _M303_BIENES_INVERSION_REGULARIZACION_CASILLA,
    _M303_CUOTA_DEDUCIBLE_TOTAL_CASILLA,
    _M303_CUOTA_DEVENGADA_TOTAL_CASILLA,
    _M303_EXPLICIT_RECORD_DESIGN_REVISIONS,
    _M303_PRORRATA_REGULARIZACION_BINDING,
    _M303_PRORRATA_REGULARIZACION_CASILLA,
    _M303_PRORRATA_REGULARIZACION_SOURCE_CASILLAS,
    _M303_PRORRATA_REGULARIZACION_SOURCE_PERIODS,
    _M303_RECORD_DESIGN_SOURCE_BY_REVISION,
    _WWW1_HOST,
    _WWW6_HOST,
    load_modelo_303,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_modelo_303_live_cross_references_forbid_writes() -> None:
    modelo, _ = load_modelo_303()
    revision = modelo.revisions["2022"]
    cross_refs = {ref.id: ref for ref in revision.live_cross_references}

    static_ref = cross_refs["modelo-303-static-documentation"]
    assert static_ref.surface == "static_official_documentation"
    assert static_ref.requires_authentication is False

    filed_ref = cross_refs["modelo-303-filed-declarations-read"]
    assert filed_ref.surface == "authenticated_read_surface"
    assert filed_ref.requires_authentication is True
    assert filed_ref.requires_aeat_authorization is True
    assert set(filed_ref.allowed_methods) == {"GET", "HEAD", "OPTIONS"}
    assert set(filed_ref.allowed_hosts) == {
        _WWW1_HOST,
        _WWW6_HOST,
    }
    forbidden = set(filed_ref.forbidden_actions)
    assert {
        "presentation",
        "signing",
        "amendment",
        "payment",
        "cancellation",
        "declaration-submission",
        "document-submission",
        "server-side-save",
    }.issubset(forbidden)


def test_modelo_303_construct_links_living_filing_and_extractor_surfaces() -> None:
    modelo, _ = load_modelo_303()
    revision = modelo.revisions["2022"]
    construct = next(c for c in revision.constructs if c.id == "modelo-303-iva-autoliquidacion")

    assert "modelo-303-filing" in construct.application_links
    assert "modelo-303-extractor" in construct.application_links
    assert "modelo-303-deadline" in construct.application_links
    assert construct.filing_schedules == ("modelo-303-trimestral",)
    assert "modelo-303-dr-2022" in construct.workbook_parity_refs


def test_modelo_303_declares_iva_repercutido_soportado_autorepercutido_bindings() -> None:
    """Modelo 303 must declare ledger_iva_aggregation bindings for the
    three IVA flow directions so the runtime can resolve cuota
    devengada / cuota deducible / INVERSION_SUJETO_PASIVO cross-modelo."""
    modelo, _ = load_modelo_303()
    revision = modelo.revisions["2022"]

    iva_bindings = {binding.id: binding for binding in revision.bindings if binding.source == "ledger_iva_aggregation"}
    assert "modelo-303-iva-repercutido-general-cuota" in iva_bindings
    assert "modelo-303-iva-repercutido-reducido-cuota" in iva_bindings
    assert "modelo-303-iva-repercutido-super-reducido-cuota" in iva_bindings
    assert "modelo-303-iva-soportado-interiores-cuota" in iva_bindings
    assert "modelo-303-iva-autorepercutido-intracomunitaria-cuota" in iva_bindings


def test_modelo_303_iva_bindings_resolve_end_to_end_with_substrate_observations() -> None:
    """End-to-end: a small ledger of substrate-classified observations
    aggregates to the expected per-binding totals via the
    ledger_iva_aggregation runtime resolver."""

    from ....iva.flow import IvaFlowDirection
    from ....iva.schema import IvaCategory, IvaRateKind
    from ..ledger_iva_bindings import (
        IvaLedgerObservation,
        resolve_ledger_iva_aggregation_binding_values,
    )

    modelo, _ = load_modelo_303()
    revision = modelo.revisions["2022"]

    observations = [
        IvaLedgerObservation(
            ledger_id="rep-general-1",
            transaction_date=date(2025, 6, 1),
            category=IvaCategory.DOMESTIC_GENERAL,
            rate_kind=IvaRateKind.GENERAL,
            flow_direction=IvaFlowDirection.REPERCUTIDO,
            base_amount=Decimal("1000"),
            iva_amount=Decimal("210"),
            observation_role=IvaLedgerObservationRole.SETTLEMENT,
        ),
        IvaLedgerObservation(
            ledger_id="rep-reducido-1",
            transaction_date=date(2025, 6, 3),
            category=IvaCategory.DOMESTIC_REDUCED,
            rate_kind=IvaRateKind.REDUCED,
            flow_direction=IvaFlowDirection.REPERCUTIDO,
            base_amount=Decimal("200"),
            iva_amount=Decimal("20"),
            observation_role=IvaLedgerObservationRole.SETTLEMENT,
        ),
        IvaLedgerObservation(
            ledger_id="rep-super-1",
            transaction_date=date(2025, 6, 4),
            category=IvaCategory.DOMESTIC_SUPER_REDUCED,
            rate_kind=IvaRateKind.SUPER_REDUCED,
            flow_direction=IvaFlowDirection.REPERCUTIDO,
            base_amount=Decimal("100"),
            iva_amount=Decimal("4"),
            observation_role=IvaLedgerObservationRole.SETTLEMENT,
        ),
        IvaLedgerObservation(
            ledger_id="sop-interior-1",
            transaction_date=date(2025, 6, 5),
            category=IvaCategory.DOMESTIC_GENERAL,
            rate_kind=IvaRateKind.GENERAL,
            flow_direction=IvaFlowDirection.SOPORTADO,
            base_amount=Decimal("300"),
            iva_amount=Decimal("63"),
            deduction_fact_kind=IvaDeductionFactKind.DOMESTIC_CURRENT,
            deduction_provenance=IvaDeductionClassificationProvenance(
                authority=IvaDeductionEvidenceAuthority.INVOICE_EVIDENCE,
                source_locator="test-ledger:sop-interior-1",
                evidence_digest="a" * 64,
            ),
            observation_role=IvaLedgerObservationRole.SETTLEMENT,
        ),
        IvaLedgerObservation(
            ledger_id="auto-ica-1",
            transaction_date=date(2025, 6, 6),
            category=IvaCategory.INTRA_COMMUNITY_ACQUISITION_REVERSE_CHARGE,
            rate_kind=IvaRateKind.GENERAL,
            flow_direction=IvaFlowDirection.INVERSION_SUJETO_PASIVO,
            base_amount=Decimal("400"),
            iva_amount=Decimal("84"),
            deduction_fact_kind=IvaDeductionFactKind.INTRA_EU_CURRENT,
            deduction_provenance=IvaDeductionClassificationProvenance(
                authority=IvaDeductionEvidenceAuthority.INTRA_EU_SELF_ASSESSMENT,
                source_locator="test-ledger:auto-ica-1",
                evidence_digest="a" * 64,
            ),
            observation_role=IvaLedgerObservationRole.SETTLEMENT,
        ),
    ]

    result = resolve_ledger_iva_aggregation_binding_values(revision, observations)
    assert result == {
        "modelo-303-iva-repercutido-general-base": Decimal("1000"),
        "modelo-303-iva-repercutido-general-cuota": Decimal("210"),
        "modelo-303-iva-repercutido-reducido-base": Decimal("200"),
        "modelo-303-iva-repercutido-reducido-cuota": Decimal("20"),
        "modelo-303-iva-repercutido-super-reducido-base": Decimal("100"),
        "modelo-303-iva-repercutido-super-reducido-cuota": Decimal("4"),
        "modelo-303-iva-soportado-interiores-base": Decimal("300"),
        "modelo-303-iva-soportado-interiores-cuota": Decimal("63"),
        # This fixture has no recargo-charged repercutido rows, so the
        # recargo-equivalencia tier bindings resolve to zero.
        "modelo-303-recargo-equivalencia-general-cuota": Decimal("0"),
        "modelo-303-recargo-equivalencia-reducido-cuota": Decimal("0"),
        "modelo-303-recargo-equivalencia-super-reducido-cuota": Decimal("0"),
        # The reverse-charge AIC row is not an intra-community supply, and this
        # fixture has no export rows, so casillas 59/60 resolve to zero.
        "modelo-303-casilla-59-entregas-intracomunitarias-base": Decimal("0"),
        "modelo-303-casilla-60-exportaciones-base": Decimal("0"),
        # Casilla 122 is deliberately ABSENT here. This test resolves against
        # 2022, while the supplier-side inversión binding belongs
        # to the later explicit record-design revisions. Listing it here would
        # assert a resolution this revision cannot produce.
        # No third-country import rows in this observation set, so the import
        # deducible binding resolves to zero.
        "modelo-303-iva-soportado-importaciones-cuota": Decimal("0"),
        "modelo-303-iva-autorepercutido-intracomunitaria-cuota": Decimal("84"),
        # The AIC official-box parity bindings select the same AIC inversión row
        # as the semantic intracomunitaria binding, so they resolve to the same
        # self-assessed cuota (net-zero across the devengado/deducible pair).
        "modelo-303-iva-autorepercutido-intracomunitaria-devengado-cuota": Decimal("84"),
        "modelo-303-iva-autorepercutido-intracomunitaria-deducible-cuota": Decimal("84"),
        # No domestic inversión del sujeto pasivo rows in this observation
        # set, so both interior reverse-charge bindings resolve to zero.
        "modelo-303-iva-autorepercutido-interior-devengado-cuota": Decimal("0"),
        "modelo-303-iva-autorepercutido-interior-deducible-cuota": Decimal("0"),
        # No criterio-de-caja rows in this observation set (every observation
        # carries the default NONE treatment), so the art. 163 decies
        # informational bindings for casillas 62/63/74/75 resolve to zero.
        "modelo-303-criterio-caja-entregas-art75-base": Decimal("0"),
        "modelo-303-criterio-caja-entregas-art75-cuota": Decimal("0"),
        "modelo-303-criterio-caja-adquisiciones-base": Decimal("0"),
        "modelo-303-criterio-caja-adquisiciones-cuota": Decimal("0"),
    }


def test_modelo_303_construct_includes_iva_bindings() -> None:
    """The Modelo 303 construct must list each ledger_iva_aggregation
    binding so downstream consumers see a complete construct envelope."""
    modelo, _ = load_modelo_303()
    revision = modelo.revisions["2022"]
    construct = next(c for c in revision.constructs if c.id == "modelo-303-iva-autoliquidacion")
    assert "modelo-303-iva-repercutido-general-cuota" in construct.bindings
    assert "modelo-303-iva-repercutido-reducido-cuota" in construct.bindings
    assert "modelo-303-iva-repercutido-super-reducido-cuota" in construct.bindings
    assert "modelo-303-iva-soportado-interiores-cuota" in construct.bindings
    assert "modelo-303-iva-autorepercutido-intracomunitaria-cuota" in construct.bindings


@pytest.mark.parametrize("revision_id", ["2022", *_M303_EXPLICIT_RECORD_DESIGN_REVISIONS])
def test_modelo_303_bienes_inversion_regularizacion_binding_is_declared_while_casilla_43_stays_manual(
    revision_id: str,
) -> None:
    """The live capital-goods resolver owns a binding slot; the official box remains operator-visible."""
    modelo, _ = load_modelo_303()
    revision = modelo.revisions[revision_id]
    bindings = {binding.id: binding for binding in revision.bindings}
    casillas = {casilla.id: casilla for casilla in revision.casillas}

    binding = bindings[_M303_BIENES_INVERSION_REGULARIZACION_BINDING]
    assert binding.source == BindingSourceKind.BIENES_INVERSION_REGULARIZACION
    assert selector_as_dict(binding) == {
        "source_modelo": "303",
        "regularizacion_output": "modelo_303_casilla_43",
    }
    assert binding_source_modelo(binding) == "303"
    assert binding_source_casilla_ids(binding) == ()

    casilla_43 = casillas[_M303_BIENES_INVERSION_REGULARIZACION_CASILLA]
    assert casilla_43.input_kind is InputKind.MANUAL
    assert casilla_43.binding is None


@pytest.mark.parametrize("revision_id", ["2022", *_M303_EXPLICIT_RECORD_DESIGN_REVISIONS])
def test_modelo_303_prorrata_regularizacion_binding_is_declared_while_casilla_44_stays_manual(
    revision_id: str,
) -> None:
    modelo, _ = load_modelo_303()
    revision = modelo.revisions[revision_id]
    casilla = {item.id: item for item in revision.casillas}[_M303_PRORRATA_REGULARIZACION_CASILLA]
    binding = {item.id: item for item in revision.bindings}[_M303_PRORRATA_REGULARIZACION_BINDING]

    assert casilla.input_kind is InputKind.MANUAL
    assert casilla.binding is None
    assert binding.source is BindingSourceKind.PRORRATA_REGULARIZACION
    assert binding_source_modelo(binding) == "303"
    assert binding_source_casilla_ids(binding) == _M303_PRORRATA_REGULARIZACION_SOURCE_CASILLAS
    assert selector_as_dict(binding) == {
        "source_modelo": "303",
        "source_casilla_ids": _M303_PRORRATA_REGULARIZACION_SOURCE_CASILLAS,
        "source_periods": _M303_PRORRATA_REGULARIZACION_SOURCE_PERIODS,
        "regularizacion_output": "modelo_303_casilla_44",
    }
    assert binding_aggregation_op(binding) is BindingAggregationOp.SUM
    assert {"ley-37-1992:art-104", "ley-37-1992:art-105"}.issubset(binding.legal_refs)
    assert binding.source_refs == (
        _M303_RECORD_DESIGN_SOURCE_BY_REVISION[revision_id],
        "aeat-modelo-303-procedure",
        "boe-modelo-303-2008-form",
    )
    citations_by_source = {citation.source_ref: citation for citation in binding.source_citations}
    assert citations_by_source["aeat-modelo-303-procedure"].required_text == ("modelo 303",)


@pytest.mark.parametrize("revision_id", ["2022", *_M303_EXPLICIT_RECORD_DESIGN_REVISIONS])
def test_modelo_303_construct_exposes_prorrata_regularizacion_binding(revision_id: str) -> None:
    modelo, _ = load_modelo_303()
    revision = modelo.revisions[revision_id]
    construct = next(item for item in revision.constructs if item.id == "modelo-303-iva-autoliquidacion")

    assert _M303_PRORRATA_REGULARIZACION_CASILLA in construct.casilla_ids
    assert _M303_PRORRATA_REGULARIZACION_BINDING in construct.bindings
    assert "ley-37-1992:art-105" in construct.legal_refs


@pytest.mark.parametrize("revision_id", ["2022", *_M303_EXPLICIT_RECORD_DESIGN_REVISIONS])
def test_modelo_303_casilla_44_regularizacion_flows_to_total_deducible(revision_id: str) -> None:
    modelo, _ = load_modelo_303()
    revision = modelo.revisions[revision_id]
    refs_by_formula_id = {formula.id: set(expression_casilla_refs(formula.expression)) for formula in revision.formulas}

    assert all(formula.target_casilla_id != _M303_PRORRATA_REGULARIZACION_CASILLA for formula in revision.formulas)
    assert all(
        formula.target_casilla_id != _M303_BIENES_INVERSION_REGULARIZACION_CASILLA for formula in revision.formulas
    )

    cuota_deducible_total = next(
        formula for formula in revision.formulas if formula.target_casilla_id == _M303_CUOTA_DEDUCIBLE_TOTAL_CASILLA
    )
    refs = set(expression_casilla_refs(cuota_deducible_total.expression))
    assert _M303_BIENES_INVERSION_REGULARIZACION_CASILLA in refs
    assert _M303_PRORRATA_REGULARIZACION_CASILLA in refs
    assert refs_by_formula_id["modelo-303-iva-resultado-regimen-general"] == {
        _M303_CUOTA_DEVENGADA_TOTAL_CASILLA,
        _M303_CUOTA_DEDUCIBLE_TOTAL_CASILLA,
    }

    if revision_id in _M303_EXPLICIT_RECORD_DESIGN_REVISIONS:
        projection = next(formula for formula in revision.formulas if formula.id == "modelo-303-dr303-45-projection")
        assert projection.expression.casilla_id == _M303_CUOTA_DEDUCIBLE_TOTAL_CASILLA
