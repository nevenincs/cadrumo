"""Spanish VAT (IVA) taxonomy + rules substrate (Track B Step R-1).

Provides a strictly-typed, hand-reviewed enumeration of Spanish VAT
situations and a minimal EU rate table, codified against specific
articles of **Ley 37/1992, del Impuesto sobre el Valor Añadido**
(BOE-A-1992-28740). Every record is a strict frozen pydantic v2
model; every regulation carries at least one :class:`Citation` with
a non-empty Spanish quote; every rate carries a BOE / Directive
reference and an effective window.

Public surface — callers from outside this subpackage must import
exclusively from ``aeat.financial.vat`` and MUST NOT reach into
private ``_schema``, ``_rates``, ``_catalogue``, ``_lookup``,
``_corpus``, or ``_verify`` modules.

Example:
    ```python
    from datetime import date

    from . import (
        EUMemberState,
        VATCategory,
        VATRateKind,
        cite,
        lookup_rate,
    )

    rate = lookup_rate(EUMemberState.ES, VATRateKind.GENERAL, date(2025, 6, 1))
    assert rate.pct == 21
    print(cite(VATCategory.DOMESTIC_GENERAL_21))
    ```
"""

from __future__ import annotations

from ._catalogue import VAT_CATALOGUE_2025
from ._corpus import load_vat_rules_from_manual
from ._lookup import cite, lookup_rate
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
    VatError,
    VatRateNotFoundError,
)

__all__ = [
    "VAT_CATALOGUE_2025",
    "VAT_RATE_TABLE",
    "Citation",
    "CitationSource",
    "EUMemberState",
    "VATCatalogue",
    "VATCategory",
    "VATRate",
    "VATRateKind",
    "VATRegulation",
    "VatCatalogueError",
    "VatCategoryNotFoundError",
    "VatError",
    "VatRateNotFoundError",
    "VerificationIssue",
    "VerificationReport",
    "cite",
    "load_vat_rules_from_manual",
    "lookup_rate",
    "verify_catalogue",
]
