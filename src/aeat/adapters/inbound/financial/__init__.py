"""Public surface of the financial input adapter.

This package owns provider-native ingestion records and file parsers for bank
statement formats. Domain packages consume the typed raw records but never own
provider detection or source-file parsing themselves.

The exported symbols partition into three groups: provider-native record types
(:class:`aeat.domain.transactions.RawTransaction`,
:class:`aeat.domain.transactions.RawProvenance`,
:class:`aeat.domain.transactions.SourceFormat`), the provider abstract base
plus its concrete implementations (:class:`CsvProvider`, :class:`OfxProvider`,
:class:`PdfN26Provider`, :class:`XlsxProvider`), and the auto-detection helper
:func:`detect_provider`.

See Also:
    :mod:`aeat.adapters.inbound.financial.providers`: concrete providers.
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
