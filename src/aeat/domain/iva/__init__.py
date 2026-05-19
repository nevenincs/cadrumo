"""Spanish VAT (IVA) taxonomy and registry-backed lookup surface.

Provides strict VAT identifiers, classification primitives, and read-only
loaders for committed registry data. Python code owns validation and lookup
behaviour; rates, effective windows, and catalogue text are loaded from
`registry/aeat/vat`.

The substrate exposes:

* The closed enumerations :class:`IvaCategory`, :class:`EUMemberState`,
  :class:`IvaRateKind` and :class:`IvaCitationSource`.
* The period-keyed catalogue view :data:`IVA_CATALOGUES_BY_YEAR` and lookup
  helper :func:`resolve_catalogue`.
* The 27-state :data:`IVA_RATE_TABLE` with a load-time non-overlap invariant
  that raises :class:`IvaRateOverlapError` on drift.
* A full classification axis stack (:class:`IvaResidency` (used for both
  issuer and customer roles), :class:`CustomerTaxStatus`,
  :class:`TransactionKind`, :class:`InvoiceKind`) plus the deterministic
  resolver :func:`classify_iva` returning :class:`IvaClassificationResult`.

Callers from outside this subpackage must import exclusively from
:mod:`aeat.domain.iva` and must not reach into private modules.
"""

from __future__ import annotations

from ._catalogue import load_iva_catalogues, resolve_catalogue
from ._classification import (
    CustomerTaxStatus,
    InvoiceKind,
    IvaClassificationResult,
    IvaInvoiceClassificationCriteria,
    IvaResidency,
    TransactionKind,
    classify_iva,
)
from ._corpus import load_iva_rules_from_manual
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
from ._schema import (
    EUMemberState,
    IvaCatalogue,
    IvaCategory,
    IvaCitation,
    IvaCitationSource,
    IvaRateRecord,
    IvaRateKind,
    IvaRegulation,
    IvaVerificationIssue,
    IvaVerificationReport,
)
from ._verify import verify_catalogue
from .errors import (
    ProrrataError,
    ProrrataInputError,
    ProrrataSectorError,
    IvaCatalogueError,
    IvaCategoryNotFoundError,
    IvaClassificationError,
    IvaError,
    IvaRateNotFoundError,
    IvaRateOverlapError,
)

__all__ = [
    "DEDUCIBLE_FLOW_DIRECTIONS",
    "DEVENGADA_FLOW_DIRECTIONS",
    "REGIME_PERIODICITY",
    "CustomerTaxStatus",
    "DeductionScope",
    "EUMemberState",
    "InputClassification",
    "InvoiceKind",
    "IossFilerRole",
    "IvaResidency",
    "IvaFlowDirection",
    "IvaSettlementSide",
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
    "RegimePeriodicity",
    "TransactionKind",
    "IvaCatalogue",
    "IvaCategory",
    "IvaClassificationResult",
    "IvaInvoiceClassificationCriteria",
    "IvaRateRecord",
    "IvaRateKind",
    "IvaRegulation",
    "IvaCatalogueError",
    "IvaCategoryNotFoundError",
    "IvaCitation",
    "IvaCitationSource",
    "IvaClassificationError",
    "IvaError",
    "IvaRateNotFoundError",
    "IvaRateOverlapError",
    "IvaVerificationIssue",
    "IvaVerificationReport",
    "cite",
    "classify_input_deduction",
    "classify_iva",
    "compute_prorrata_general",
    "compute_sectoral_prorrata",
    "derive_flow_for_classification",
    "is_deducible_flow",
    "is_devengada_flow",
    "is_especial_mandatory",
    "load_recargo_rates",
    "load_iva_catalogues",
    "load_iva_rate_table",
    "load_iva_rules_from_manual",
    "lookup_rate",
    "recargo_rate_for",
    "regime_allows_deduction",
    "requires_sectoral_separation",
    "resolve_catalogue",
    "settlement_sides_for_flow",
    "sum_deductible_amounts",
    "validate_prorrata_reference",
    "verify_catalogue",
]


