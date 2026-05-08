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

from ._catalogue import VAT_CATALOGUES_BY_YEAR, resolve_catalogue
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
from ._rates import VAT_RATE_TABLE
from ._recargo_equivalencia import (
    LIVA_ART_161_RECARGO,
    LivaArt161RecargoRates,
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
    "LIVA_ART_161_RECARGO",
    "REGIME_PERIODICITY",
    "VAT_CATALOGUES_BY_YEAR",
    "VAT_RATE_TABLE",
    "CustomerResidency",
    "CustomerTaxStatus",
    "DeductionScope",
    "EUMemberState",
    "InvoiceDirection",
    "IossFilerRole",
    "IssuerResidency",
    "IvaFlowDirection",
    "IvaSettlementSide",
    "LivaArt161RecargoRates",
    "OssIossRegime",
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
    "classify_vat",
    "derive_flow_for_classification",
    "is_deducible_flow",
    "is_devengada_flow",
    "load_vat_rules_from_manual",
    "lookup_rate",
    "recargo_rate_for",
    "regime_allows_deduction",
    "resolve_catalogue",
    "settlement_sides_for_flow",
    "verify_catalogue",
]
