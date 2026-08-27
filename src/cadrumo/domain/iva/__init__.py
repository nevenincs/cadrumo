"""Public facade for the registry-backed Spanish IVA substrate.

This package owns the canonical IVA taxonomy, dated rate lookup, settlement
flow mapping, invoice classification bridge, prorrata calculations, OSS/IOSS
regime metadata, recargo-equivalencia rates, refund eligibility, and SEPA marca
derivation. Runtime Python owns validation and deterministic resolution;
statutory rate windows, catalogue text, and recargo tables are loaded from
committed registry files under ``registry/aeat/iva``.

The facade exposes closed identifiers such as :class:`IvaCategory`,
:class:`EUMemberState`, :class:`IvaRateKind`,
:class:`IvaFlowDirection`, and :class:`IvaSettlementSide`; loaders and lookups
such as :func:`bundled_iva_catalogue`, :func:`iva_catalogue_years`,
:func:`resolve_catalogue`,
:func:`load_iva_rate_table`, :func:`lookup_rate`, :func:`load_recargo_rates`,
and :func:`recargo_rate_for_applied_rate`; and the classification axis stack
(:class:`IvaTerritorialScope`, :class:`CustomerTaxStatus`,
:class:`TransactionKind`, :class:`InvoiceKind`) resolved by
:func:`classify_iva` into :class:`IvaClassificationResult`.

Ledger and invoice callers use :class:`IvaInvoiceClassification`,
:func:`classify_invoice_line_for_iva`, :func:`invoice_line_to_iva_observation`,
and :func:`derive_flow_for_classification` to carry the
category/rate/flow/settlement-side tuple without re-encoding IVA rules.
Legal prorrata remains a distinct LIVA arts. 101-103 substrate through
:class:`ProrrataInputs`, :class:`ProrrataReference`, :class:`ProrrataResult`,
:func:`compute_prorrata_general`, and :func:`compute_sectoral_prorrata`; it is
not a usage-ratio or ledger business-percentage mechanism.

Callers from outside this subpackage import exclusively from
:mod:`domain.iva` and must not reach into private modules. This domain
surface is pure substrate logic: repositories, CLI commands, modelo binding,
and live AEAT access belong to application and adapter layers.

See Also:
    :mod:`domain.invoices`
        Invoice records and helpers that use this IVA substrate to produce
        registry-ready invoice and IVA observations.
    :mod:`application.aggregation`
        Source-mesh resolvers that convert bucket-local ledger and invoice facts
        into IVA, OSS/IOSS, and prorrata-aware calculation payloads.
    :mod:`domain.calculations.registry`
        Binding declarations, observation models, and formulas that consume the
        resolved IVA substrate during modelo calculation.
    :mod:`application.modelo`
        Work-unit calculation and verification flows that persist the registry
        results; they do not own IVA taxonomy or rate lookup.
"""

from __future__ import annotations

from ._catalogue import bundled_iva_catalogue, iva_catalogue_years, resolve_catalogue
from ._classification import (
    CustomerTaxStatus,
    InvoiceKind,
    IvaClassificationResult,
    IvaInvoiceClassificationCriteria,
    IvaTerritorialScope,
    PartyFact,
    TransactionKind,
    classifiable_categories,
    classify_iva,
    domestic_categories_by_rate_kind,
    domestic_rate_tier_is_required,
    rate_kind_for_domestic_category,
)
from ._components import (
    IVA_CATEGORY_COMPONENTS,
    IvaCategoryComponents,
    IvaComponentPresence,
    IvaCuotaSettlement,
    IvaGroundingConfidence,
    IvaKindApplicability,
    IvaRetencionExpectation,
    IvaRetencionRole,
    category_bears_taxable_base,
    category_components,
    category_cuota_is_zero_by_law,
    cuota_less_m303_categories_from_table,
)
from ._corpus import load_iva_rules_from_manual
from ._deduction_facts import (
    IvaDeductionClassificationProvenance,
    required_deduction_evidence_authority,
    validate_iva_deduction_fact,
)
from ._establishment import (
    SPAIN_COUNTRY_CODE,
    StatedCountryCodeStatus,
    country_code_for_printed_country_name,
    country_code_for_printed_tax_identifier,
    country_code_for_stated_country_code,
    record_country_code_status,
    stated_country_code_status,
    territorial_scope_for_country,
    territorial_scope_for_printed_country_name,
    territorial_scope_for_spanish_postal_code,
)
from ._flow import (
    DEDUCIBLE_FLOW_DIRECTIONS,
    DEVENGADA_FLOW_DIRECTIONS,
    IvaFlowDirection,
    IvaSettlementSide,
    derive_flow_for_classification,
    is_deducible_flow,
    is_devengada_flow,
    settlement_sides_for_flow,
)
from ._identification import identification_state_for_printed_tax_identifier
from ._invoice_classification import (
    IvaInvoiceClassification,
    classify_invoice_line_for_iva,
    invoice_line_to_iva_observation,
)
from ._legend_derivation import (
    LegendDerivation,
    LegendDerivationOutcome,
    derive_category_from_regime_legend,
    match_regime_legend,
)
from ._lookup import (
    cite,
    lookup_rate,
    rate_kinds_for_declared_rate,
    rate_table_covers,
    rate_table_covers_any_positive_tier,
)
from ._m303_settlement import (
    is_m303_annual_settlement_period,
    m303_annual_settlement_order_key,
    m303_annual_settlement_period_order,
    m303_annual_settlement_period_tokens,
)
from ._oss import (
    REGIME_PERIODICITY,
    DeductionScope,
    IossFilerRole,
    OssIossRegime,
    RegimePeriodicity,
    regime_allows_deduction,
)
from ._place_of_supply import (
    IvaPlaceOfSupplyRule,
    load_place_of_supply_table,
    place_of_supply_rule,
    place_of_supply_years,
    required_supply_nature_for_rule,
)
from ._prorrata import (
    EspecialMandatoryRule,
    InputClassification,
    ProrrataInputDeduction,
    ProrrataInputs,
    ProrrataKind,
    ProrrataReference,
    ProrrataRegime,
    ProrrataResult,
    ProrrataSector,
    RegularizacionProrrataDireccion,
    RegularizacionProrrataResult,
    classify_input_deduction,
    compute_prorrata_definitiva_anual,
    compute_prorrata_general,
    compute_regularizacion_prorrata_anual,
    compute_sectoral_prorrata,
    deductible_percentage_for,
    especial_mandatory_rule,
    is_especial_mandatory,
    requires_sectoral_separation,
    sum_deductible_amounts,
    validate_prorrata_reference,
)
from ._rates import load_iva_rate_table
from ._recargo_equivalencia import (
    LivaArt161RecargoRates,
    RecargoRateRecord,
    load_recargo_rate_table,
    load_recargo_rates,
    recargo_rate_for_applied_rate,
)
from ._refund_eligibility import (
    LAST_FILING_PERIOD_TOKENS,
    RefundEligibilityReason,
    is_last_filing_period_of_year,
    refund_disposition_available,
    refund_eligibility_reason,
)
from ._regime_legend import REGIME_LEGENDS, RegimeLegend, regime_legend_phrases
from ._regimen_simplificado_rows import (
    ActividadAgricolaSimplificado,
    ActividadNoAgricolaSimplificado,
    ActividadOrdenAnual,
    ActividadOrdenAnualId,
    AutoridadAgricolaOrdenAnualNoResuelta,
    DificilJustificacionOrdenAnual,
    EntradaModuloSimplificado,
    HechoActividadSimplificado,
    IaeEpigrafe,
    IndiceCuotaDevengadaAgricolaOrdenAnual,
    IndiceTemporadaOrdenAnual,
    M303RegimenSimplificadoScope,
    M303RegimenSimplificadoScopeDecision,
    ModuloOrdenAnual,
    PorcentajeIngresoCuentaAgricolaOrdenAnual,
    PorcentajeIngresoCuentaIaeOrdenAnual,
    ReduccionLorcaOrdenAnual,
    RegimenSimplificadoActivity,
    RegimenSimplificadoFilingRows,
    validate_regimen_simplificado_rows,
)
from ._saturation import (
    IvaRateResolution,
    resolve_category_rate,
    split_gross_at_rate,
)
from ._schema import (
    CUOTA_LESS_M303_IVA_CATEGORIES,
    EVIDENCE_EXEMPT_IVA_CATEGORIES,
    M303_BASE_OUT_OF_SCOPE_IVA_CATEGORIES,
    NO_PRINTED_TAX_IVA_CATEGORIES,
    EUMemberState,
    IvaArt69DosService,
    IvaCashAccountingPaymentEvidence,
    IvaCashAccountingTreatment,
    IvaCatalogue,
    IvaCategory,
    IvaCitation,
    IvaExemptionArticle,
    IvaLedgerObservationRole,
    IvaRateKind,
    IvaRateRecord,
    IvaRegulation,
    IvaVerificationIssue,
    IvaVerificationReport,
)
from ._sepa_marca import (
    SEPA_ZONE_COUNTRY_CODES,
    SepaMarca,
    derive_sepa_marca,
)
from ._supply_nature import (
    LIVA_CITATION_QUALIFIERS,
    STATUTORY_CITATIONS,
    StatutoryCitation,
    SupplyNature,
    SupplyNatureDerivation,
    SupplyNatureDerivationOutcome,
    derive_supply_nature_from_citation,
    match_statutory_citations,
    supply_nature_implied_by_category,
    supply_nature_is_required,
)
from .errors import (
    IvaCatalogueError,
    IvaCategoryNotFoundError,
    IvaClassificationError,
    IvaError,
    IvaRateNotFoundError,
    IvaRateOverlapError,
    IvaValidationError,
    ProrrataError,
    ProrrataInputError,
    ProrrataSectorError,
)
from .verify import verify_catalogue

__all__ = [
    "CUOTA_LESS_M303_IVA_CATEGORIES",
    "DEDUCIBLE_FLOW_DIRECTIONS",
    "DEVENGADA_FLOW_DIRECTIONS",
    "EVIDENCE_EXEMPT_IVA_CATEGORIES",
    "IVA_CATEGORY_COMPONENTS",
    "LAST_FILING_PERIOD_TOKENS",
    "LIVA_CITATION_QUALIFIERS",
    "M303_BASE_OUT_OF_SCOPE_IVA_CATEGORIES",
    "NO_PRINTED_TAX_IVA_CATEGORIES",
    "REGIME_LEGENDS",
    "REGIME_PERIODICITY",
    "SEPA_ZONE_COUNTRY_CODES",
    "SPAIN_COUNTRY_CODE",
    "STATUTORY_CITATIONS",
    "ActividadAgricolaSimplificado",
    "ActividadNoAgricolaSimplificado",
    "ActividadOrdenAnual",
    "ActividadOrdenAnualId",
    "AutoridadAgricolaOrdenAnualNoResuelta",
    "CustomerTaxStatus",
    "DeductionScope",
    "DificilJustificacionOrdenAnual",
    "EUMemberState",
    "EntradaModuloSimplificado",
    "EspecialMandatoryRule",
    "HechoActividadSimplificado",
    "IaeEpigrafe",
    "IndiceCuotaDevengadaAgricolaOrdenAnual",
    "IndiceTemporadaOrdenAnual",
    "InputClassification",
    "InvoiceKind",
    "IossFilerRole",
    "IvaArt69DosService",
    "IvaCashAccountingPaymentEvidence",
    "IvaCashAccountingTreatment",
    "IvaCatalogue",
    "IvaCatalogueError",
    "IvaCategory",
    "IvaCategoryComponents",
    "IvaCategoryNotFoundError",
    "IvaCitation",
    "IvaClassificationError",
    "IvaClassificationResult",
    "IvaComponentPresence",
    "IvaCuotaSettlement",
    "IvaDeductionClassificationProvenance",
    "IvaError",
    "IvaExemptionArticle",
    "IvaFlowDirection",
    "IvaGroundingConfidence",
    "IvaInvoiceClassification",
    "IvaInvoiceClassificationCriteria",
    "IvaKindApplicability",
    "IvaLedgerObservationRole",
    "IvaPlaceOfSupplyRule",
    "IvaRateKind",
    "IvaRateNotFoundError",
    "IvaRateOverlapError",
    "IvaRateRecord",
    "IvaRateResolution",
    "IvaRegulation",
    "IvaRetencionExpectation",
    "IvaRetencionRole",
    "IvaSettlementSide",
    "IvaTerritorialScope",
    "IvaValidationError",
    "IvaVerificationIssue",
    "IvaVerificationReport",
    "LegendDerivation",
    "LegendDerivationOutcome",
    "LivaArt161RecargoRates",
    "M303RegimenSimplificadoScope",
    "M303RegimenSimplificadoScopeDecision",
    "ModuloOrdenAnual",
    "OssIossRegime",
    "PartyFact",
    "PorcentajeIngresoCuentaAgricolaOrdenAnual",
    "PorcentajeIngresoCuentaIaeOrdenAnual",
    "ProrrataError",
    "ProrrataInputDeduction",
    "ProrrataInputError",
    "ProrrataInputs",
    "ProrrataKind",
    "ProrrataReference",
    "ProrrataRegime",
    "ProrrataResult",
    "ProrrataSector",
    "ProrrataSectorError",
    "RecargoRateRecord",
    "ReduccionLorcaOrdenAnual",
    "RefundEligibilityReason",
    "RegimeLegend",
    "RegimePeriodicity",
    "RegimenSimplificadoActivity",
    "RegimenSimplificadoFilingRows",
    "RegularizacionProrrataDireccion",
    "RegularizacionProrrataResult",
    "SepaMarca",
    "StatedCountryCodeStatus",
    "StatutoryCitation",
    "SupplyNature",
    "SupplyNatureDerivation",
    "SupplyNatureDerivationOutcome",
    "TransactionKind",
    "bundled_iva_catalogue",
    "category_bears_taxable_base",
    "category_components",
    "category_cuota_is_zero_by_law",
    "cite",
    "classifiable_categories",
    "classify_input_deduction",
    "classify_invoice_line_for_iva",
    "classify_iva",
    "compute_prorrata_definitiva_anual",
    "compute_prorrata_general",
    "compute_regularizacion_prorrata_anual",
    "compute_sectoral_prorrata",
    "country_code_for_printed_country_name",
    "country_code_for_printed_tax_identifier",
    "country_code_for_stated_country_code",
    "cuota_less_m303_categories_from_table",
    "deductible_percentage_for",
    "derive_category_from_regime_legend",
    "derive_flow_for_classification",
    "derive_sepa_marca",
    "derive_supply_nature_from_citation",
    "domestic_categories_by_rate_kind",
    "domestic_rate_tier_is_required",
    "especial_mandatory_rule",
    "identification_state_for_printed_tax_identifier",
    "invoice_line_to_iva_observation",
    "is_deducible_flow",
    "is_devengada_flow",
    "is_especial_mandatory",
    "is_last_filing_period_of_year",
    "is_m303_annual_settlement_period",
    "iva_catalogue_years",
    "load_iva_rate_table",
    "load_iva_rules_from_manual",
    "load_place_of_supply_table",
    "load_recargo_rate_table",
    "load_recargo_rates",
    "lookup_rate",
    "m303_annual_settlement_order_key",
    "m303_annual_settlement_period_order",
    "m303_annual_settlement_period_tokens",
    "match_regime_legend",
    "match_statutory_citations",
    "place_of_supply_rule",
    "place_of_supply_years",
    "rate_kind_for_domestic_category",
    "rate_kinds_for_declared_rate",
    "rate_table_covers",
    "rate_table_covers_any_positive_tier",
    "recargo_rate_for_applied_rate",
    "record_country_code_status",
    "refund_disposition_available",
    "refund_eligibility_reason",
    "regime_allows_deduction",
    "regime_legend_phrases",
    "required_deduction_evidence_authority",
    "required_supply_nature_for_rule",
    "requires_sectoral_separation",
    "resolve_catalogue",
    "resolve_category_rate",
    "settlement_sides_for_flow",
    "split_gross_at_rate",
    "stated_country_code_status",
    "sum_deductible_amounts",
    "supply_nature_implied_by_category",
    "supply_nature_is_required",
    "territorial_scope_for_country",
    "territorial_scope_for_printed_country_name",
    "territorial_scope_for_spanish_postal_code",
    "validate_iva_deduction_fact",
    "validate_prorrata_reference",
    "validate_regimen_simplificado_rows",
    "verify_catalogue",
]
