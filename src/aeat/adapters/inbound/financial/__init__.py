"""Financial input adapter surface.

This package owns provider-native ingestion records and file parsers. Domain
packages consume the typed raw records but do not own provider detection or
source-file parsing.
"""

from __future__ import annotations

from ._decimal import canonical_decimal
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
    "canonical_decimal",
    "detect_provider",
]
