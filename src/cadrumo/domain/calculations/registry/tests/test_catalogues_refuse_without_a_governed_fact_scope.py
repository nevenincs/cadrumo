"""A governed catalogue resolves only from an explicit authority or a validation scope."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

import pytest

from cadrumo.core.concepto_ingreso import ConceptoIngreso
from cadrumo.core.errors.hierarchy import InternalInvariantError
from cadrumo.core.period import Period
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.domain.renta.ledger_expenses import renta_first_slice_expense_routing
from cadrumo.domain.renta.retenciones_routing_integrity import resolve_m130_retenciones_route
from cadrumo.domain.retention.floor import retention_floor_years
from cadrumo.domain.transactions.irpf_categories import ledger_irpf_category_catalogue
from cadrumo.domain.transactions.retencion_facts import load_retencion_actividades_rates
from cadrumo.domain.transactions.tipo_actividad_partitions import resolve_tipo_actividad_selector
from cadrumo.domain.transactions.volumen_ingresos import (
    counts_toward_art_109_activity_income,
    counts_toward_volumen_de_ingresos,
)

from ..activity_kind_catalogue import resolve_irpf_activity_kind_catalogue
from ..amendment_regime_policy import resolve_amendment_regime_policy
from ..applicability_modelo202 import modelo_202_modality_from_inputs, resolve_modelo_202_art_40_3_incn_threshold
from ..applicability_payer_facts import resolve_payer_fact_catalogue
from ..bienes_inversion_catalogue import resolve_bienes_inversion_catalogue
from ..calendar_ccaa_catalogue import resolve_calendar_ccaa_catalogue
from ..ccaa_catalogue import resolve_ccaa_catalogue
from ..citation_blocklist import find_known_bad
from ..concepto_ingreso import resolve_concepto_ingreso_catalogue
from ..descendant_relacion_catalogue import resolve_descendant_relacion_catalogue
from ..entity_type import resolve_entity_vocabulary
from ..eu_member_state_catalogue import resolve_eu_member_state_catalogue
from ..foreign_asset_obligation_catalogue import resolve_foreign_asset_obligation_catalogue
from ..governed_fact_scope import GovernedFactSource, outside_governed_fact_validation, validating_governed_facts
from ..invoice_legal_classification import resolve_invoice_legal_classification_catalogue
from ..irnr_tipo_renta import resolve_tipo_renta_irnr_catalogue
from ..irpf_income_categories import resolve_irpf_income_category_catalogue
from ..irpf_regimes import resolve_irpf_regime_vocabulary
from ..iva_cash_accounting_vocabulary import resolve_iva_cash_accounting_catalogue
from ..iva_category_catalogue import resolve_iva_category_catalogue
from ..iva_deduction_catalogue import resolve_iva_deduction_catalogue
from ..iva_flow_catalogue import resolve_iva_flow_direction_catalogue
from ..iva_legal_vocabulary import resolve_iva_art69_dos_service_catalogue, resolve_iva_exemption_article_catalogue
from ..iva_rate_kind_catalogue import resolve_iva_rate_kind_catalogue
from ..iva_rate_role_catalogue import resolve_iva_rate_role_catalogue
from ..iva_regime_vocabulary import resolve_iva_regime_catalogue
from ..lorca_reduction import resolve_lorca_reduction
from ..m303_schema_vocabulary import resolve_m303_regime_composition_catalogue, resolve_m303_tax_territory_catalogue
from ..m347_threshold import resolve_m347_clave_c_declaration_threshold, resolve_m347_counterparty_annual_threshold
from ..modelo_pending_orden import pending_orden_vocabulary
from ..modelo_rendering import modelo_rendering_declarations
from ..nif_iva_catalogue import resolve_nif_iva_catalogue
from ..prorrata_exclusions import resolve_art104_tres_exclusion_catalogue
from ..prorrata_regime import resolve_prorrata_regime_catalogue
from ..prorrata_register_catalogue import resolve_prorrata_register_catalogue
from ..prorrata_vocabulary import resolve_input_classification_catalogue, resolve_prorrata_kind_catalogue
from ..refund_eligibility import resolve_refund_eligibility_policy
from ..renta_codes_catalogue import resolve_fiscal_residency_catalogue, ue_eea_country_codes
from ..renta_expense_policy import renta_expense_policy_declarations
from ..rental_reduction import resolve_rental_reduction_art232_tier_catalogue
from ..retenciones_bindings import _registry_schemes_for_modelo
from ..setup_profile_bindings import mapping_fact_entries
from ..situacion_familiar_catalogue import resolve_situacion_familiar_catalogue
from ..situacion_familiar_m145_catalogue import resolve_situacion_familiar_m145_catalogue
from ..third_party_declaration_roles import resolve_third_party_declaration_role_catalogue
from ..travel_agency_mediation import resolve_travel_agency_mediation_catalogue
from ..withholding_bindings import _withholding_role_declarations, resolve_retencion_clave

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_EFFECTIVE = date(2025, 3, 1)

_CATALOGUES: tuple[Callable[..., object], ...] = (
    resolve_ccaa_catalogue,
    resolve_descendant_relacion_catalogue,
    resolve_eu_member_state_catalogue,
    resolve_iva_rate_kind_catalogue,
    resolve_iva_rate_role_catalogue,
    resolve_tipo_renta_irnr_catalogue,
    resolve_nif_iva_catalogue,
    resolve_art104_tres_exclusion_catalogue,
    resolve_prorrata_regime_catalogue,
    resolve_prorrata_register_catalogue,
    resolve_rental_reduction_art232_tier_catalogue,
    resolve_third_party_declaration_role_catalogue,
    resolve_travel_agency_mediation_catalogue,
    resolve_amendment_regime_policy,
    resolve_bienes_inversion_catalogue,
    resolve_calendar_ccaa_catalogue,
    resolve_concepto_ingreso_catalogue,
    resolve_entity_vocabulary,
    resolve_fiscal_residency_catalogue,
    resolve_foreign_asset_obligation_catalogue,
    resolve_input_classification_catalogue,
    resolve_invoice_legal_classification_catalogue,
    resolve_irpf_activity_kind_catalogue,
    resolve_irpf_income_category_catalogue,
    resolve_irpf_regime_vocabulary,
    resolve_iva_category_catalogue,
    resolve_iva_cash_accounting_catalogue,
    resolve_iva_deduction_catalogue,
    resolve_iva_flow_direction_catalogue,
    resolve_iva_regime_catalogue,
    resolve_iva_art69_dos_service_catalogue,
    resolve_iva_exemption_article_catalogue,
    resolve_m303_regime_composition_catalogue,
    resolve_m303_tax_territory_catalogue,
    resolve_payer_fact_catalogue,
    resolve_prorrata_kind_catalogue,
    resolve_refund_eligibility_policy,
    resolve_situacion_familiar_catalogue,
    resolve_situacion_familiar_m145_catalogue,
    ue_eea_country_codes,
)


@pytest.mark.parametrize("resolve", _CATALOGUES, ids=lambda resolve: resolve.__name__)
def test_a_catalogue_refuses_when_neither_authority_nor_scope_is_supplied(resolve: Callable[..., object]) -> None:
    with (
        outside_governed_fact_validation(),
        pytest.raises(InternalInvariantError, match="requires an explicit generation-pinned governed-fact scope"),
    ):
        resolve(effective_date=_EFFECTIVE)


@pytest.mark.parametrize("resolve", _CATALOGUES, ids=lambda resolve: resolve.__name__)
def test_the_same_catalogue_resolves_from_an_explicit_authority(resolve: Callable[..., object]) -> None:
    """CONTROL: the refusal above is the missing scope, not the catalogue."""
    with bundled_indexed_authority().operation() as operation:
        assert resolve(effective_date=_EFFECTIVE, authority=operation) is not None


_FILING_YEAR_END = date(2025, 12, 31)
_LORCA_EFFECTIVE = date(2024, 12, 31)


@dataclass(frozen=True, slots=True)
class _EmptyRetencionesAggregation:
    """An aggregation with no rows: the scheme lookup reads only its modelo and period."""

    modelo: str
    period: Period
    rollups: tuple[()] = ()
    total_perceptors: int = 0
    total_taxable_base: Decimal = Decimal(0)
    total_retencion: Decimal = Decimal(0)
    type2_rows: tuple[()] = ()
    type2_record_count: int = 0


def _first_slice_routing(authority: GovernedFactSource | None) -> object:
    """Route through the production entry, which takes its facts from a scope rather than an argument."""
    if authority is None:
        return renta_first_slice_expense_routing(effective_date=_EFFECTIVE)
    with validating_governed_facts(authority):
        return renta_first_slice_expense_routing(effective_date=_EFFECTIVE)


_SCOPED_RESOLVERS: tuple[tuple[str, Callable[[GovernedFactSource | None], object]], ...] = (
    (
        "lorca_reduction",
        lambda authority: resolve_lorca_reduction(effective_date=_LORCA_EFFECTIVE, authority=authority),
    ),
    (
        "m347_counterparty_threshold",
        lambda authority: resolve_m347_counterparty_annual_threshold(effective_date=_EFFECTIVE, authority=authority),
    ),
    (
        "m347_clave_c_threshold",
        lambda authority: resolve_m347_clave_c_declaration_threshold(effective_date=_EFFECTIVE, authority=authority),
    ),
    ("pending_orden_vocabulary", lambda authority: pending_orden_vocabulary(authority=authority)),
    ("modelo_rendering", lambda authority: modelo_rendering_declarations(_EFFECTIVE, authority=authority)),
    ("renta_expense_policy", lambda authority: renta_expense_policy_declarations(2024, authority=authority)),
    (
        "retenciones_scheme_lookup",
        lambda authority: _registry_schemes_for_modelo(
            _EmptyRetencionesAggregation("111", Period.from_year_and_code(2025, "1T")), authority=authority
        ),
    ),
    (
        "setup_mapping_fact",
        lambda authority: mapping_fact_entries("legal-reference-schema-vocabulary", authority=authority),
    ),
    ("retencion_clave", lambda authority: resolve_retencion_clave("A", _EFFECTIVE, authority=authority)),
    ("withholding_role", lambda authority: _withholding_role_declarations(_EFFECTIVE, authority=authority)),
    (
        "known_bad_citation",
        lambda authority: find_known_bad(
            "ley", "79", "cuota l\u00edquida", effective_date=_EFFECTIVE, authority=authority
        ),
    ),
    (
        "modelo_202_incn_threshold",
        lambda authority: resolve_modelo_202_art_40_3_incn_threshold(effective_date=_EFFECTIVE, authority=authority),
    ),
    (
        "modelo_202_modality",
        lambda authority: modelo_202_modality_from_inputs(
            entity_type=None, incn_prior_12_months=None, effective_date=_EFFECTIVE, authority=authority
        ),
    ),
    ("retention_floor", lambda authority: retention_floor_years(effective_date=_EFFECTIVE, authority=authority)),
    ("m130_retenciones_route", lambda authority: resolve_m130_retenciones_route(authority=authority)),
    ("first_slice_expense_routing", _first_slice_routing),
    ("irpf_category_taxonomy", lambda authority: ledger_irpf_category_catalogue(authority=authority)),
    (
        "retencion_actividades_rates",
        lambda authority: load_retencion_actividades_rates(effective_date=_EFFECTIVE, authority=authority),
    ),
    (
        "tipo_actividad_selector",
        lambda authority: resolve_tipo_actividad_selector(
            "rirpf-art-95:selector-m036-actividades-profesionales",
            effective_date=_FILING_YEAR_END,
            authority=authority,
        ),
    ),
    (
        "art_110_excluded_concepts",
        lambda authority: counts_toward_volumen_de_ingresos(
            ConceptoIngreso.from_registry("subvencion_capital"), effective_date=_EFFECTIVE, authority=authority
        ),
    ),
    (
        "art_109_excluded_concepts",
        lambda authority: counts_toward_art_109_activity_income(
            ConceptoIngreso.from_registry("subvencion_capital"), effective_date=_EFFECTIVE, authority=authority
        ),
    ),
)


@pytest.mark.parametrize(("name", "resolve"), _SCOPED_RESOLVERS, ids=[name for name, _ in _SCOPED_RESOLVERS])
def test_a_scoped_resolver_refuses_when_neither_authority_nor_scope_is_supplied(
    name: str, resolve: Callable[[GovernedFactSource | None], object]
) -> None:
    with (
        outside_governed_fact_validation(),
        pytest.raises(InternalInvariantError, match="requires an explicit generation-pinned governed-fact scope"),
    ):
        resolve(None)


@pytest.mark.parametrize(("name", "resolve"), _SCOPED_RESOLVERS, ids=[name for name, _ in _SCOPED_RESOLVERS])
def test_the_same_scoped_resolver_resolves_from_an_explicit_authority(
    name: str, resolve: Callable[[GovernedFactSource | None], object]
) -> None:
    """CONTROL: the refusal above is the missing scope, not the resolver."""
    with bundled_indexed_authority().operation() as operation:
        assert resolve(operation) is not None
