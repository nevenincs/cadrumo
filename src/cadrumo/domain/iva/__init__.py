"""Public facade for the registry-backed Spanish IVA substrate.

This package owns the canonical IVA taxonomy, dated rate lookup, settlement
flow mapping, invoice classification bridge, prorrata calculations, OSS/IOSS
regime metadata, recargo-equivalencia rates, refund eligibility, and SEPA marca
derivation. Runtime Python owns validation and deterministic resolution;
statutory rate windows, catalogue text, and recargo tables are loaded from
committed registry files under ``registry/aeat/iva``.

The facade exposes closed identifiers such as :class:`IvaCategory`,
:class:`EUMemberState`, :class:`IvaRateKind`, :class:`IvaCitationSource`,
:class:`IvaFlowDirection`, and :class:`IvaSettlementSide`; loaders and lookups
such as :func:`load_iva_catalogues`, :func:`resolve_catalogue`,
:func:`load_iva_rate_table`, :func:`lookup_rate`, :func:`load_recargo_rates`,
and :func:`recargo_rate_for`; and the classification axis stack
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

from ...core import RefundElection
from ._catalogue import load_iva_catalogues, resolve_catalogue
from ._classification import (
    CustomerTaxStatus,
    InvoiceKind,
    IvaClassificationResult,
    IvaInvoiceClassificationCriteria,
    IvaTerritorialScope,
    TransactionKind,
    classify_iva,
)
from ._corpus import load_iva_rules_from_manual
from ._errors import (
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
from ._invoice_classification import (
    IvaInvoiceClassification,
    classify_invoice_line_for_iva,
    invoice_line_to_iva_observation,
)
from ._lookup import cite, lookup_rate
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
from ._prorrata import (
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
    is_especial_mandatory,
    requires_sectoral_separation,
    sum_deductible_amounts,
    validate_prorrata_reference,
)
from ._rates import load_iva_rate_table
from ._recargo_equivalencia import (
    LivaArt161RecargoRates,
    load_recargo_rates,
    recargo_rate_for,
)
from ._refund_eligibility import (
    LAST_FILING_PERIOD_TOKENS,
    RefundEligibilityReason,
    is_last_filing_period_of_year,
    refund_disposition_available,
    refund_eligibility_reason,
)
from ._saturation import (
    IvaRateResolution,
    resolve_category_rate,
    split_gross_at_rate,
)
from ._schema import (
    CUOTA_LESS_M303_IVA_CATEGORIES,
    EUMemberState,
    EVIDENCE_EXEMPT_IVA_CATEGORIES,
    IvaCashAccountingPaymentEvidence,
    IvaCashAccountingTreatment,
    IvaCatalogue,
    IvaCategory,
    IvaCitation,
    IvaCitationSource,
    IvaExemptionArticle,
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
from ._verify import verify_catalogue

__all__ = [
    "CUOTA_LESS_M303_IVA_CATEGORIES",
    "DEDUCIBLE_FLOW_DIRECTIONS",
    "DEVENGADA_FLOW_DIRECTIONS",
    "EVIDENCE_EXEMPT_IVA_CATEGORIES",
    "LAST_FILING_PERIOD_TOKENS",
    "REGIME_PERIODICITY",
    "SEPA_ZONE_COUNTRY_CODES",
    "CustomerTaxStatus",
    "DeductionScope",
    "EUMemberState",
    "InputClassification",
    "InvoiceKind",
    "IossFilerRole",
    "IvaCashAccountingPaymentEvidence",
    "IvaCashAccountingTreatment",
    "IvaCatalogue",
    "IvaCatalogueError",
    "IvaCategory",
    "IvaCategoryNotFoundError",
    "IvaCitation",
    "IvaCitationSource",
    "IvaClassificationError",
    "IvaClassificationResult",
    "IvaError",
    "IvaExemptionArticle",
    "IvaFlowDirection",
    "IvaInvoiceClassification",
    "IvaInvoiceClassificationCriteria",
    "IvaRateKind",
    "IvaRateNotFoundError",
    "IvaRateOverlapError",
    "IvaRateRecord",
    "IvaRateResolution",
    "IvaRegulation",
    "IvaSettlementSide",
    "IvaTerritorialScope",
    "IvaValidationError",
    "IvaVerificationIssue",
    "IvaVerificationReport",
    "LivaArt161RecargoRates",
    "OssIossRegime",
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
    "RefundElection",
    "RefundEligibilityReason",
    "RegimePeriodicity",
    "RegularizacionProrrataDireccion",
    "RegularizacionProrrataResult",
    "SepaMarca",
    "TransactionKind",
    "cite",
    "classify_input_deduction",
    "classify_invoice_line_for_iva",
    "classify_iva",
    "compute_prorrata_definitiva_anual",
    "compute_prorrata_general",
    "compute_regularizacion_prorrata_anual",
    "compute_sectoral_prorrata",
    "deductible_percentage_for",
    "derive_flow_for_classification",
    "derive_sepa_marca",
    "invoice_line_to_iva_observation",
    "is_deducible_flow",
    "is_devengada_flow",
    "is_especial_mandatory",
    "is_last_filing_period_of_year",
    "is_m303_annual_settlement_period",
    "load_iva_catalogues",
    "load_iva_rate_table",
    "load_iva_rules_from_manual",
    "load_recargo_rates",
    "lookup_rate",
    "m303_annual_settlement_order_key",
    "m303_annual_settlement_period_order",
    "m303_annual_settlement_period_tokens",
    "recargo_rate_for",
    "refund_disposition_available",
    "refund_eligibility_reason",
    "regime_allows_deduction",
    "requires_sectoral_separation",
    "resolve_catalogue",
    "resolve_category_rate",
    "settlement_sides_for_flow",
    "split_gross_at_rate",
    "sum_deductible_amounts",
    "validate_prorrata_reference",
    "verify_catalogue",
]
