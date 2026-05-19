"""Spanish VAT (IVA) taxonomy and registry-backed lookup surface.

Provides strict VAT identifiers, classification primitives, and read-only
loaders for committed registry data. Python code owns validation and lookup
behaviour; rates, effective windows, and catalogue text are loaded from
`registry/aeat/vat`.

The substrate exposes:

* The closed enumerations :class:`VATCategory`, :class:`EUMemberState`,
  :class:`VATRateKind` and :class:`VatCitationSource`.
* The period-keyed catalogue view :data:`VAT_CATALOGUES_BY_YEAR` and lookup
  helper :func:`resolve_catalogue`.
* The 27-state :data:`VAT_RATE_TABLE` with a load-time non-overlap invariant
  that raises :class:`VatRateOverlapError` on drift.
* A full classification axis stack (:class:`IssuerResidency`,
  :class:`CustomerResidency`, :class:`CustomerTaxStatus`,
  :class:`TransactionKind`, :class:`InvoiceDirection`) plus the deterministic
  resolver :func:`classify_vat` returning :class:`VATClassification`.

Callers from outside this subpackage must import exclusively from
:mod:`aeat.domain.vat` and must not reach into private modules.
"""

from __future__ import annotations

from ._catalogue import load_vat_catalogues, resolve_catalogue
from ._classification import (
    CustomerResidency,
    CustomerTaxStatus,
    InvoiceDirection,
    IssuerResidency,
    TransactionKind,
    VATClassification,
    VATClassificationCriteria,
    classify_vat,
)
from ._corpus import load_vat_rules_from_manual
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
from ._rates import load_vat_rate_table
from ._recargo_equivalencia import (
    LivaArt161RecargoRates,
    load_recargo_rates,
    recargo_rate_for,
)
from ._schema import (
    EUMemberState,
    VATCatalogue,
    VATCategory,
    VatCitation,
    VatCitationSource,
    VATRate,
    VATRateKind,
    VATRegulation,
    VatVerificationIssue,
    VatVerificationReport,
)
from ._verify import verify_catalogue
from .errors import (
    ProrrataError,
    ProrrataInputError,
    ProrrataSectorError,
    VatCatalogueError,
    VatCategoryNotFoundError,
    VatClassificationError,
    VatError,
    VatRateNotFoundError,
    VatRateOverlapError,
)

__all__ = [
    "DEDUCIBLE_FLOW_DIRECTIONS",
    "DEVENGADA_FLOW_DIRECTIONS",
    "REGIME_PERIODICITY",
    "CustomerResidency",
    "CustomerTaxStatus",
    "DeductionScope",
    "EUMemberState",
    "InputClassification",
    "InvoiceDirection",
    "IossFilerRole",
    "IssuerResidency",
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
    "VATCatalogue",
    "VATCategory",
    "VATClassification",
    "VATClassificationCriteria",
    "VATRate",
    "VATRateKind",
    "VATRegulation",
    "VatCatalogueError",
    "VatCategoryNotFoundError",
    "VatCitation",
    "VatCitationSource",
    "VatClassificationError",
    "VatError",
    "VatRateNotFoundError",
    "VatRateOverlapError",
    "VatVerificationIssue",
    "VatVerificationReport",
    "cite",
    "classify_input_deduction",
    "classify_vat",
    "compute_prorrata_general",
    "compute_sectoral_prorrata",
    "derive_flow_for_classification",
    "is_deducible_flow",
    "is_devengada_flow",
    "is_especial_mandatory",
    "load_recargo_rates",
    "load_vat_catalogues",
    "load_vat_rate_table",
    "load_vat_rules_from_manual",
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


