"""Spanish VAT (IVA) taxonomy + rules substrate.

Provides a strictly-typed, hand-reviewed enumeration of Spanish VAT
situations and a minimal EU rate table, codified against specific
articles of **Ley 37/1992, del Impuesto sobre el Valor Añadido**
(BOE-A-1992-28740). Every record is a strict frozen pydantic v2
model; every regulation carries at least one :class:`Citation` with
a non-empty Spanish quote; every rate carries a BOE / Directive
reference and an effective window.

 (#85) shipped the enumerations, the 2025 catalogue and the
27-state rate table.

 (#183) extended this substrate with:
- ``DOMESTIC_REVERSE_CHARGE`` :class:`VATCategory` member.
- Period-keyed catalogue mapping :data:`VAT_CATALOGUES_BY_YEAR` +
  :func:`resolve_catalogue` helper.
- 2024 baseline ES rates with date bounds + a load-time non-overlap
  invariant (raises :class:`VatRateOverlapError` on drift).
- A full classification axis stack (:class:`IssuerResidency`,
  :class:`CustomerResidency`, :class:`CustomerTaxStatus`,
  :class:`TransactionKind`, :class:`InvoiceDirection`) plus a
  deterministic :func:`classify_vat` resolver returning
  :class:`VATClassification`.
- :data:`MODELO_303_CASILLA_MAPPING` bridge from
  ``(VATCategory, InvoiceDirection)`` to Modelo 303 casilla
  contributions, plus :func:`lookup_modelo_303_contribution`.

Public surface — callers from outside this subpackage must import
exclusively from ``aeat.domain.financial.vat`` and MUST NOT reach into
private modules.
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
from ._modelo_303_mapping import (
    MODELO_303_CASILLA_MAPPING,
    CasillaRole,
    Modelo303Contribution,
    lookup_modelo_303_contribution,
)
from ._rates import VAT_RATE_TABLE
from ._schema import (
    Citation,
    CitationSource,
    EUMemberState,
    VATCatalogue,
    VATCategory,
    VATRate,
    VATRateKind,
    VATRegulation,
    VerificationIssue,
    VerificationReport,
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
    "MODELO_303_CASILLA_MAPPING",
    "VAT_CATALOGUES_BY_YEAR",
    "VAT_CATALOGUE_2025",
    "VAT_RATE_TABLE",
    "CasillaRole",
    "Citation",
    "CitationSource",
    "CustomerResidency",
    "CustomerTaxStatus",
    "EUMemberState",
    "InvoiceDirection",
    "IssuerResidency",
    "Modelo303Contribution",
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
    "VatClassificationError",
    "VatError",
    "VatRateNotFoundError",
    "VatRateOverlapError",
    "VerificationIssue",
    "VerificationReport",
    "cite",
    "classify_vat",
    "load_vat_rules_from_manual",
    "lookup_modelo_303_contribution",
    "lookup_rate",
    "resolve_catalogue",
    "verify_catalogue",
]
