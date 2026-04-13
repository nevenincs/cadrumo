"""Financial ingest entry points for Phase 2 Track B.

This package defines the T1 ingest boundary for transaction sources:
strict `RawTransaction` records plus file-backed providers for CSV,
XLSX, and OFX inputs. Callers outside this package must import only
from `aeat.financial` or `aeat.financial.providers`.
"""

from __future__ import annotations

from ._raw_transaction import RawProvenance, RawTransaction, SourceFormat
from .providers import (
    CsvProvider,
    FinancialProvider,
    FinancialProviderError,
    InvalidFinancialSourceError,
    OfxProvider,
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
    "ProviderValidation",
    "RawProvenance",
    "RawTransaction",
    "SourceFormat",
    "UnsupportedFinancialSourceError",
    "XlsxProvider",
    "detect_provider",
]
