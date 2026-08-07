"""Public surface of the financial input adapter.

This package owns file parsers for bank statement formats. The provider layer
detects source formats and turns source files into
:class:`domain.transactions.RawTransaction` records with
:class:`domain.transactions.RawProvenance`; application services own
active-bucket routing, persistence, currency normalization, and ledger events.

Each concrete :class:`FinancialProvider` declares a ``CorpusVerificationSource``
and a provisional-specimen flag so bank-PDF and tabular imports carry the same
corpus-honesty discipline as the other inbound PDF surfaces.

See Also:
    :mod:`adapters.inbound.financial.providers`: concrete providers.
"""

from __future__ import annotations

from ....domain import canonical_decimal_string as canonical_decimal
from .providers import (
    AmbiguousRole,
    BankStatementParseError,
    ColumnRoleMapping,
    CorpusVerificationSource,
    CsvProvider,
    FinancialProvider,
    FinancialProviderError,
    FinancialValidationError,
    InvalidFinancialSourceError,
    MappedTabularProvider,
    NormalizedRow,
    NormalizedTable,
    OfxProvider,
    PdfN26Provider,
    ProjectedCell,
    ProjectedRow,
    ProjectedTable,
    ProviderValidation,
    TabularDialect,
    TabularMappingResolver,
    TabularNotice,
    UnmappedColumn,
    UnsupportedFinancialSourceError,
    XlsxProvider,
    detect_provider,
    normalize_tabular_bytes,
    normalize_tabular_text,
    project_table,
)

__all__ = [
    "AmbiguousRole",
    "BankStatementParseError",
    "ColumnRoleMapping",
    "CorpusVerificationSource",
    "CsvProvider",
    "FinancialProvider",
    "FinancialProviderError",
    "FinancialValidationError",
    "InvalidFinancialSourceError",
    "MappedTabularProvider",
    "NormalizedRow",
    "NormalizedTable",
    "OfxProvider",
    "PdfN26Provider",
    "ProjectedCell",
    "ProjectedRow",
    "ProjectedTable",
    "ProviderValidation",
    "TabularDialect",
    "TabularMappingResolver",
    "TabularNotice",
    "UnmappedColumn",
    "UnsupportedFinancialSourceError",
    "XlsxProvider",
    "canonical_decimal",
    "detect_provider",
    "normalize_tabular_bytes",
    "normalize_tabular_text",
    "project_table",
]
