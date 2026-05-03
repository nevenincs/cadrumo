"""Spanish VAT (IVA) taxonomy and rules substrate.

Provides a strictly-typed, hand-reviewed enumeration of Spanish VAT
situations and a minimal EU rate table, codified against specific articles of
**Ley 37/1992, del Impuesto sobre el Valor Añadido** (BOE-A-1992-28740).
Every record is a strict frozen pydantic v2 model; every regulation carries
at least one :class:`VatCitation` with a non-empty Spanish quote; every rate
carries a BOE or Council Directive reference and an effective window.

The substrate exposes:

* The closed enumerations :class:`VATCategory`, :class:`EUMemberState`,
  :class:`VATRateKind` and :class:`VatCitationSource`.
* The hand-curated :data:`VAT_CATALOGUE_2025` plus the period-keyed view
  :data:`VAT_CATALOGUES_BY_YEAR` and lookup helper :func:`resolve_catalogue`.
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

from ._catalogue import VAT_CATALOGUE_2025, VAT_CATALOGUES_BY_YEAR, resolve_catalogue
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
from ._lookup import cite, lookup_rate
from ._rates import VAT_RATE_TABLE
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
    "VAT_CATALOGUES_BY_YEAR",
    "VAT_CATALOGUE_2025",
    "VAT_RATE_TABLE",
    "CustomerResidency",
    "CustomerTaxStatus",
    "EUMemberState",
    "InvoiceDirection",
    "IssuerResidency",
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
    "load_vat_rules_from_manual",
    "lookup_rate",
    "resolve_catalogue",
    "verify_catalogue",
]
