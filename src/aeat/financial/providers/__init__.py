"""Provider ABC and concrete file-ingest implementations."""

from __future__ import annotations

from .._raw_transaction import RawTransaction
from ._base import (
    FinancialProvider,
    FinancialProviderError,
    InvalidFinancialSourceError,
    ProviderValidation,
    UnsupportedFinancialSourceError,
)
from ._csv import CsvProvider
from ._detection import detect_provider
from ._ofx import OfxProvider
from ._pdf_n26 import PdfN26Provider
from ._xlsx import XlsxProvider

__all__ = [
    "CsvProvider",
    "FinancialProvider",
    "FinancialProviderError",
    "InvalidFinancialSourceError",
    "OfxProvider",
    "PdfN26Provider",
    "ProviderValidation",
    "RawTransaction",
    "UnsupportedFinancialSourceError",
    "XlsxProvider",
    "detect_provider",
]
