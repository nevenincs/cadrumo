"""Public surface of the financial input adapter.

This package owns file parsers for bank statement formats. The raw transaction
records are part of :mod:`aeat.domain.transactions`; this adapter only detects
providers and turns source files into those domain records.

See Also:
    :mod:`aeat.adapters.inbound.financial.providers`: concrete providers.
"""

from __future__ import annotations

from ....domain._identifiers import canonical_decimal_string as canonical_decimal
from .providers import (
    BankStatementParseError,
    CorpusVerificationSource,
    CsvProvider,
    FinancialProvider,
    FinancialProviderError,
    FinancialValidationError,
    InvalidFinancialSourceError,
    OfxProvider,
    PdfN26Provider,
    ProviderValidation,
    UnsupportedFinancialSourceError,
    XlsxProvider,
    detect_provider,
)

__all__ = [
    "BankStatementParseError",
    "CorpusVerificationSource",
    "CsvProvider",
    "FinancialProvider",
    "FinancialProviderError",
    "FinancialValidationError",
    "InvalidFinancialSourceError",
    "OfxProvider",
    "PdfN26Provider",
    "ProviderValidation",
    "UnsupportedFinancialSourceError",
    "XlsxProvider",
    "canonical_decimal",
    "detect_provider",
]
