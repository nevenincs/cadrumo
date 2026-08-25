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
    OfxProvider,
    PdfN26Provider,
    ProjectedCell,
    ProjectedRow,
    ProjectedTable,
    ProviderValidation,
    TabularMappingResolver,
    UnmappedColumn,
    UnsupportedFinancialSourceError,
    XlsxProvider,
    detect_provider,
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
    "OfxProvider",
    "PdfN26Provider",
    "ProjectedCell",
    "ProjectedRow",
    "ProjectedTable",
    "ProviderValidation",
    "TabularMappingResolver",
    "UnmappedColumn",
    "UnsupportedFinancialSourceError",
    "XlsxProvider",
    "detect_provider",
    "project_table",
]
