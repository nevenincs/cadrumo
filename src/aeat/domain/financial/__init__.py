"""Track B financial-input subpackage root.

This subpackage hosts the Transaction Data Pipeline (TDP) building
blocks — VAT enumeration (``aeat.financial.vat``, issue #85), provider
detection (``aeat.financial.providers``, issue #73), and transaction
categorisation (``aeat.financial.categories``, issue #77). The root
package re-exports only the T1 ingest boundary defined by issue #73;
callers should import VAT and category symbols from their dedicated
child subpackages directly.
"""

from __future__ import annotations

from ._raw_transaction import RawProvenance, RawTransaction, SourceFormat
from .providers import (
    CsvProvider,
    FinancialProvider,
    FinancialProviderError,
    InvalidFinancialSourceError,
    OfxProvider,
    PdfN26Provider,
    ProviderValidation,
    UnsupportedFinancialSourceError,
    XlsxProvider,
    detect_provider,
)

__all__ = [
    "CsvProvider",
    "FinancialProvider",
    "FinancialProviderError",
    "InvalidFinancialSourceError",
    "OfxProvider",
    "PdfN26Provider",
    "ProviderValidation",
    "RawProvenance",
    "RawTransaction",
    "SourceFormat",
    "UnsupportedFinancialSourceError",
    "XlsxProvider",
    "detect_provider",
]
