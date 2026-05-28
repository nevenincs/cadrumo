"""Provider ABC and concrete file-ingest implementations."""

from __future__ import annotations

from ._base import (
    BankStatementParseError,
    CorpusVerificationSource,
    FinancialProvider,
    FinancialProviderError,
    FinancialValidationError,
    InvalidFinancialSourceError,
    ProviderValidation,
    UnsupportedFinancialSourceError,
)
from ._csv import CsvProvider
from ._detection import detect_provider, provider_for_extension
from ._ofx import OfxProvider
from ._pdf_n26 import PdfN26Provider
from ._xlsx import XlsxProvider

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
    "detect_provider",
    "provider_for_extension",
]
