"""Spanish IVA (IVA) taxonomy and registry-backed lookup surface.

Provides strict IVA identifiers, classification primitives, and read-only
loaders for committed registry data. Python code owns validation and lookup
behaviour; rates, effective windows, and catalogue text are loaded from
`registry/aeat/iva`.

The substrate exposes:

* The closed enumerations :class:`IvaCategory`, :class:`EUMemberState`,
  :class:`IvaRateKind` and :class:`IvaCitationSource`.
* The period-keyed catalogue view :data:`IVA_CATALOGUES_BY_YEAR` and lookup
  helper :func:`resolve_catalogue`.
* The 27-state :data:`IVA_RATE_TABLE` with a load-time non-overlap invariant
  that raises :class:`IvaRateOverlapError` on drift.
* A full classification axis stack (:class:`IvaTerritorialScope` (used for both
  issuer and customer roles), :class:`CustomerTaxStatus`,
  :class:`TransactionKind`, :class:`InvoiceKind`) plus the deterministic
  resolver :func:`classify_iva` returning :class:`IvaClassificationResult`.

Callers from outside this subpackage must import exclusively from
:mod:`aeat.domain.iva` and must not reach into private modules.
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
    classify_input_deduction,
    compute_prorrata_general,
    compute_sectoral_prorrata,
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
from ._verify import verify_catalogue

__all__ = [
    "CUOTA_LESS_M303_IVA_CATEGORIES",
    "DEDUCIBLE_FLOW_DIRECTIONS",
    "DEVENGADA_FLOW_DIRECTIONS",
    "LAST_FILING_PERIOD_TOKENS",
    "REGIME_PERIODICITY",
    "CustomerTaxStatus",
    "DeductionScope",
    "EUMemberState",
    "InputClassification",
    "InvoiceKind",
    "IossFilerRole",
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
    "TransactionKind",
    "cite",
    "classify_input_deduction",
    "classify_invoice_line_for_iva",
    "classify_iva",
    "compute_prorrata_general",
    "compute_sectoral_prorrata",
    "derive_flow_for_classification",
    "invoice_line_to_iva_observation",
    "is_deducible_flow",
    "is_devengada_flow",
    "is_especial_mandatory",
    "is_last_filing_period_of_year",
    "load_iva_catalogues",
    "load_iva_rate_table",
    "load_iva_rules_from_manual",
    "load_recargo_rates",
    "lookup_rate",
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
