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
from .authored_editions import filing_year_envelope, revision_covering
from .modelo_303_registry_constants import (
    M303_BIENES_INVERSION_REGULARIZACION_BINDING,
    M303_BIENES_INVERSION_REGULARIZACION_CASILLA,
    M303_CUOTA_DEDUCIBLE_TOTAL_CASILLA,
    M303_CUOTA_DEVENGADA_TOTAL_CASILLA,
    M303_PRORRATA_REGULARIZACION_BINDING,
    M303_PRORRATA_REGULARIZACION_CASILLA,
    M303_PRORRATA_REGULARIZACION_SOURCE_CASILLAS,
    M303_PRORRATA_REGULARIZACION_SOURCE_PERIOD_SELECTION,
    M303_SUPPORTED_EDITION_IDS,
    WWW1_HOST,
    WWW6_HOST,
    m303_record_design_source,
)
from .modelo_303_registry_support import load_modelo_303

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_FLOOR_REVISION = str(revision_covering("303", filing_year_envelope().floor).id)
_OBSERVATION_YEAR = filing_year_envelope().horizon


def test_modelo_303_live_cross_references_forbid_writes() -> None:
    modelo, _ = load_modelo_303()
    revision = modelo.revisions[_FLOOR_REVISION]
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
        WWW1_HOST,
        WWW6_HOST,
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
    revision = modelo.revisions[_FLOOR_REVISION]
    construct = next(c for c in revision.constructs if c.id == "modelo-303-iva-autoliquidacion")

    assert "modelo-303-filing" in construct.application_links
    assert "modelo-303-extractor" in construct.application_links
    assert "modelo-303-deadline" in construct.application_links
    assert construct.filing_schedules == ("modelo-303-trimestral",)
    assert "modelo-303-dr" in construct.workbook_parity_refs


def test_modelo_303_declares_iva_repercutido_soportado_autorepercutido_bindings() -> None:
    """Modelo 303 must declare ledger_iva_aggregation bindings for the
    three IVA flow directions so the runtime can resolve cuota
    devengada / cuota deducible / INVERSION_SUJETO_PASIVO cross-modelo."""
    modelo, _ = load_modelo_303()
    revision = modelo.revisions[_FLOOR_REVISION]

    iva_bindings = {binding.id: binding for binding in revision.bindings if binding.source == "ledger_iva_aggregation"}
    assert "modelo-303-iva-repercutido-general-cuota" in iva_bindings
    assert "modelo-303-iva-repercutido-reducido-cuota" in iva_bindings
    assert "modelo-303-iva-repercutido-super-reducido-cuota" in iva_bindings
    assert "modelo-303-iva-soportado-interiores-cuota" in iva_bindings
    assert "modelo-303-iva-autorepercutido-intracomunitaria-cuota" in iva_bindings


@pytest.mark.usefixtures("operation")
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
    revision = modelo.revisions[_FLOOR_REVISION]

    observations = [
        IvaLedgerObservation(
            ledger_id="rep-general-1",
            transaction_date=date(_OBSERVATION_YEAR, 6, 1),
            category=IvaCategory("domestic_general"),
            rate_kind=IvaRateKind("general"),
            flow_direction=IvaFlowDirection.from_registry("repercutido"),
            base_amount=Decimal("1000"),
            iva_amount=Decimal("210"),
            observation_role=IvaLedgerObservationRole.SETTLEMENT,
        ),
        IvaLedgerObservation(
            ledger_id="rep-reducido-1",
            transaction_date=date(_OBSERVATION_YEAR, 6, 3),
            category=IvaCategory("domestic_reduced"),
            rate_kind=IvaRateKind("reduced"),
            flow_direction=IvaFlowDirection.from_registry("repercutido"),
            base_amount=Decimal("200"),
            iva_amount=Decimal("20"),
            observation_role=IvaLedgerObservationRole.SETTLEMENT,
        ),
        IvaLedgerObservation(
            ledger_id="rep-super-1",
            transaction_date=date(_OBSERVATION_YEAR, 6, 4),
            category=IvaCategory("domestic_super_reduced"),
            rate_kind=IvaRateKind("super_reduced"),
            flow_direction=IvaFlowDirection.from_registry("repercutido"),
            base_amount=Decimal("100"),
            iva_amount=Decimal("4"),
            observation_role=IvaLedgerObservationRole.SETTLEMENT,
        ),
        IvaLedgerObservation(
            ledger_id="sop-interior-1",
            transaction_date=date(_OBSERVATION_YEAR, 6, 5),
            category=IvaCategory("domestic_general"),
            rate_kind=IvaRateKind("general"),
            flow_direction=IvaFlowDirection.from_registry("soportado"),
            base_amount=Decimal("300"),
            iva_amount=Decimal("63"),
            deduction_fact_kind=IvaDeductionFactKind.from_registry("domestic_current"),
            deduction_provenance=IvaDeductionClassificationProvenance(
                authority=IvaDeductionEvidenceAuthority.from_registry("invoice_evidence"),
                source_locator="test-ledger:sop-interior-1",
                evidence_digest="a" * 64,
            ),
            observation_role=IvaLedgerObservationRole.SETTLEMENT,
        ),
        IvaLedgerObservation(
            ledger_id="auto-ica-1",
            transaction_date=date(_OBSERVATION_YEAR, 6, 6),
            category=IvaCategory("intra_community_acquisition_reverse_charge"),
            rate_kind=IvaRateKind("general"),
            flow_direction=IvaFlowDirection.from_registry("inversion_sujeto_pasivo"),
            base_amount=Decimal("400"),
            iva_amount=Decimal("84"),
            deduction_fact_kind=IvaDeductionFactKind.from_registry("intra_eu_current"),
            deduction_provenance=IvaDeductionClassificationProvenance(
                authority=IvaDeductionEvidenceAuthority.from_registry("intra_eu_self_assessment"),
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
        # No third-country import rows in this observation set, so the import
        # deducible bindings, base [32] and cuota [33], resolve to zero.
        "modelo-303-iva-soportado-importaciones-base": Decimal("0"),
        "modelo-303-iva-soportado-importaciones-cuota": Decimal("0"),
        "modelo-303-iva-autorepercutido-intracomunitaria-cuota": Decimal("84"),
        # The AIC official-box parity bindings select the same AIC inversión row
        # as the semantic intracomunitaria binding, so they resolve to the same
        # self-assessed cuota (net-zero across the devengado/deducible pair),
        # and the devengado base [10] and deducible base [36] to that row's base.
        "modelo-303-iva-autorepercutido-intracomunitaria-devengado-base": Decimal("400"),
        "modelo-303-iva-autorepercutido-intracomunitaria-devengado-cuota": Decimal("84"),
        "modelo-303-iva-autorepercutido-intracomunitaria-deducible-cuota": Decimal("84"),
        "modelo-303-iva-autorepercutido-intracomunitaria-deducible-base": Decimal("400"),
        # No domestic inversión del sujeto pasivo rows in this observation
        # set, so every interior reverse-charge binding, devengado and the
        # deducible half feeding [28]-[31], resolves to zero.
        "modelo-303-iva-autorepercutido-interior-devengado-cuota": Decimal("0"),
        "modelo-303-iva-autorepercutido-interior-deducible-cuota": Decimal("0"),
        "modelo-303-iva-autorepercutido-interior-deducible-base": Decimal("0"),
        "modelo-303-iva-autorepercutido-interior-deducible-bienes-inversion-base": Decimal("0"),
        "modelo-303-iva-autorepercutido-interior-deducible-bienes-inversion-cuota": Decimal("0"),
        # No row carries the rectification deduction kind, so the three parts
        # of Rectificación de deducciones [40]/[41] resolve to zero.
        "modelo-303-iva-rectificacion-deducciones-interiores-base": Decimal("0"),
        "modelo-303-iva-rectificacion-deducciones-interiores-cuota": Decimal("0"),
        "modelo-303-iva-rectificacion-deducciones-importaciones-base": Decimal("0"),
        "modelo-303-iva-rectificacion-deducciones-importaciones-cuota": Decimal("0"),
        "modelo-303-iva-rectificacion-deducciones-inversion-sujeto-pasivo-base": Decimal("0"),
        "modelo-303-iva-rectificacion-deducciones-inversion-sujeto-pasivo-cuota": Decimal("0"),
        # No criterio-de-caja rows in this observation set (every observation
        # carries the default NONE treatment), so the art. 163 decies
        # informational bindings for casillas 62/63/74/75 resolve to zero.
        "modelo-303-criterio-caja-entregas-art75-base": Decimal("0"),
        "modelo-303-criterio-caja-entregas-art75-cuota": Decimal("0"),
        "modelo-303-criterio-caja-adquisiciones-base": Decimal("0"),
        "modelo-303-criterio-caja-adquisiciones-cuota": Decimal("0"),
        # Every deducible row here is a corriente, so the bienes de inversión
        # boxes [30]/[31], [34]/[35] and [38]/[39] resolve to zero while the
        # corrientes pairs above carry the whole deduction.
        "modelo-303-iva-soportado-interiores-bienes-inversion-base": Decimal("0"),
        "modelo-303-iva-soportado-interiores-bienes-inversion-cuota": Decimal("0"),
        "modelo-303-iva-soportado-importaciones-bienes-inversion-base": Decimal("0"),
        "modelo-303-iva-soportado-importaciones-bienes-inversion-cuota": Decimal("0"),
        "modelo-303-iva-autorepercutido-intracomunitaria-deducible-bienes-inversion-base": Decimal("0"),
        "modelo-303-iva-autorepercutido-intracomunitaria-deducible-bienes-inversion-cuota": Decimal("0"),
        # The informational volumen is base-only and selects a category no
        # observation here carries: casilla 122 takes the supplier's side of a
        # domestic reverse charge. It is a proven zero for this observation set,
        # not an absence.
        "modelo-303-casilla-122-inversion-sujeto-pasivo-base": Decimal("0"),
    }


def test_modelo_303_construct_includes_iva_bindings() -> None:
    """The Modelo 303 construct must list each ledger_iva_aggregation
    binding so downstream consumers see a complete construct envelope."""
    modelo, _ = load_modelo_303()
    revision = modelo.revisions[_FLOOR_REVISION]
    construct = next(c for c in revision.constructs if c.id == "modelo-303-iva-autoliquidacion")
    assert "modelo-303-iva-repercutido-general-cuota" in construct.bindings
    assert "modelo-303-iva-repercutido-reducido-cuota" in construct.bindings
    assert "modelo-303-iva-repercutido-super-reducido-cuota" in construct.bindings
    assert "modelo-303-iva-soportado-interiores-cuota" in construct.bindings
    assert "modelo-303-iva-autorepercutido-intracomunitaria-cuota" in construct.bindings


@pytest.mark.parametrize("revision_id", M303_SUPPORTED_EDITION_IDS)
def test_modelo_303_bienes_inversion_regularizacion_binding_feeds_casilla_43(
    revision_id: str,
) -> None:
    """The live capital-goods resolver fills the official box it is declared for."""
    modelo, _ = load_modelo_303()
    revision = modelo.revisions[revision_id]
    bindings = {binding.id: binding for binding in revision.bindings}
    casillas = {casilla.id: casilla for casilla in revision.casillas}

    binding = bindings[M303_BIENES_INVERSION_REGULARIZACION_BINDING]
    assert binding.source == BindingSourceKind.BIENES_INVERSION_REGULARIZACION
    assert selector_as_dict(binding) == {
        "source_modelo": "303",
        "regularizacion_output": "modelo_303_casilla_43",
    }
    assert binding_source_modelo(binding) == "303"
    assert binding_source_casilla_ids(binding) == ()

    casilla_43 = casillas[M303_BIENES_INVERSION_REGULARIZACION_CASILLA]
    assert casilla_43.input_kind is InputKind.BOUND
    assert casilla_43.binding == M303_BIENES_INVERSION_REGULARIZACION_BINDING


@pytest.mark.parametrize("revision_id", M303_SUPPORTED_EDITION_IDS)
def test_modelo_303_prorrata_regularizacion_binding_feeds_casilla_44(
    revision_id: str,
) -> None:
    modelo, _ = load_modelo_303()
    revision = modelo.revisions[revision_id]
    casilla = {item.id: item for item in revision.casillas}[M303_PRORRATA_REGULARIZACION_CASILLA]
    binding = {item.id: item for item in revision.bindings}[M303_PRORRATA_REGULARIZACION_BINDING]

    assert casilla.input_kind is InputKind.BOUND
    assert casilla.binding == M303_PRORRATA_REGULARIZACION_BINDING
    assert binding.source is BindingSourceKind.PRORRATA_REGULARIZACION
    assert binding_source_modelo(binding) == "303"
    assert binding_source_casilla_ids(binding) == M303_PRORRATA_REGULARIZACION_SOURCE_CASILLAS
    assert selector_as_dict(binding) == {
        "source_modelo": "303",
        "source_casilla_ids": M303_PRORRATA_REGULARIZACION_SOURCE_CASILLAS,
        "source_period_selection": M303_PRORRATA_REGULARIZACION_SOURCE_PERIOD_SELECTION,
        "regularizacion_output": "modelo_303_casilla_44",
    }
    assert binding_aggregation_op(binding) is BindingAggregationOp.SUM
    assert {"ley-37-1992:art-104", "ley-37-1992:art-105"}.issubset(binding.legal_refs)
    assert binding.source_refs == (
        m303_record_design_source(revision_id),
        "aeat-modelo-303-procedure",
        "boe-modelo-303-2008-form",
    )
    citations_by_source = {citation.source_ref: citation for citation in binding.source_citations}
    assert citations_by_source["aeat-modelo-303-procedure"].required_text == ("modelo 303",)


@pytest.mark.parametrize("revision_id", M303_SUPPORTED_EDITION_IDS)
def test_modelo_303_construct_exposes_prorrata_regularizacion_binding(revision_id: str) -> None:
    modelo, _ = load_modelo_303()
    revision = modelo.revisions[revision_id]
    construct = next(item for item in revision.constructs if item.id == "modelo-303-iva-autoliquidacion")

    assert M303_PRORRATA_REGULARIZACION_CASILLA in construct.casilla_ids
    assert M303_PRORRATA_REGULARIZACION_BINDING in construct.bindings
    assert "ley-37-1992:art-105" in construct.legal_refs


@pytest.mark.parametrize("revision_id", M303_SUPPORTED_EDITION_IDS)
def test_modelo_303_casilla_44_regularizacion_flows_to_total_deducible(revision_id: str) -> None:
    modelo, _ = load_modelo_303()
    revision = modelo.revisions[revision_id]
    refs_by_formula_id = {formula.id: set(expression_casilla_refs(formula.expression)) for formula in revision.formulas}

    assert all(formula.target_casilla_id != M303_PRORRATA_REGULARIZACION_CASILLA for formula in revision.formulas)
    assert all(
        formula.target_casilla_id != M303_BIENES_INVERSION_REGULARIZACION_CASILLA for formula in revision.formulas
    )

    cuota_deducible_total = next(
        formula for formula in revision.formulas if formula.target_casilla_id == M303_CUOTA_DEDUCIBLE_TOTAL_CASILLA
    )
    refs = set(expression_casilla_refs(cuota_deducible_total.expression))
    assert M303_BIENES_INVERSION_REGULARIZACION_CASILLA in refs
    assert M303_PRORRATA_REGULARIZACION_CASILLA in refs
    assert refs_by_formula_id["modelo-303-iva-resultado-regimen-general"] == {
        M303_CUOTA_DEVENGADA_TOTAL_CASILLA,
        M303_CUOTA_DEDUCIBLE_TOTAL_CASILLA,
    }

    projection = next(formula for formula in revision.formulas if formula.id == "modelo-303-dr303-45-projection")
    assert projection.expression.casilla_id == M303_CUOTA_DEDUCIBLE_TOTAL_CASILLA
