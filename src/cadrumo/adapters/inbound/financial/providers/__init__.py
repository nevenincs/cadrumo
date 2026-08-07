"""Bank-statement provider contract and concrete file-ingest implementations.

Defines the financial-statement provider contract and the concrete per-format
parsers behind ``aeat app ledger import``. Detection picks the right provider
for a file; each provider parses a bank statement into
:class:`domain.transactions.RawTransaction` records plus an explicit
:class:`domain.transactions.TransactionDirection`. The provider layer
parses rows only; application ledger import owns active-bucket routing,
transaction persistence, currency normalization, and bucket events.

Concrete providers also declare corpus provenance through
``CorpusVerificationSource``. PDF providers use
:class:`BankStatementParseError` structured attributes for missing, malformed,
ambiguous, and coverage failures so callers do not need to parse messages.

Major declarations:

* :class:`FinancialProvider` — the provider abstract base class.
* ``CorpusVerificationSource`` and :class:`ProviderValidation` — the
  provider corpus and pre-ingest validation contracts.
* :class:`ParsedLedgerRow` — one parsed raw transaction paired with its
  authoritative flow direction.
* :class:`CsvProvider`, :class:`OfxProvider`, :class:`XlsxProvider`, and
  :class:`PdfN26Provider` — the concrete per-format parsers.
* :func:`detect_provider` and :func:`provider_for_extension` — resolve the
  provider for a given source.
* :class:`FinancialProviderError` and its subclasses
  (:class:`BankStatementParseError`,
  :class:`UnsupportedFinancialSourceError`,
  :class:`InvalidFinancialSourceError`, :class:`FinancialValidationError`)
  — the failure taxonomy.

See Also:
    - :mod:`adapters.inbound.financial` for the parent financial-import
      facade.
    - :mod:`application.ledger` for the operator-facing import service that
      calls these providers and persists ledger transactions.
    - :mod:`domain.transactions` for the raw transaction records produced
      by successful parsing.
"""

from __future__ import annotations

from ._base import (
    BankStatementParseError,
    CorpusVerificationSource,
    FinancialProvider,
    FinancialProviderConfigError,
    FinancialProviderError,
    FinancialValidationError,
    InvalidFinancialSourceError,
    ParsedLedgerRow,
    ProviderValidation,
    UnsupportedFinancialSourceError,
    direction_from_signed_amount,
)
from ._csv import CsvProvider
from ._detection import detect_provider, provider_for_extension
from ._mapped_tabular import (
    MAPPED_TABULAR_EXTENSIONS,
    REQUIRED_STATEMENT_ROLES,
    MappedTabularProvider,
    TabularMappingResolver,
    default_tabular_mapping_resolver,
)
from ._ofx import OfxProvider
from ._pdf_n26 import PdfN26Provider
from ._tabular_dialect import (
    CANDIDATE_DELIMITERS,
    NormalizedRow,
    NormalizedTable,
    TabularDialect,
    TabularNotice,
    TabularNoticeCode,
    normalize_tabular_bytes,
    normalize_tabular_text,
)
from ._tabular_projection import (
    AmbiguousRole,
    ColumnRoleMapping,
    ProjectedCell,
    ProjectedRow,
    ProjectedTable,
    UnmappedColumn,
    project_table,
)
from ._xlsx import XlsxProvider

__all__ = [
    "CANDIDATE_DELIMITERS",
    "MAPPED_TABULAR_EXTENSIONS",
    "REQUIRED_STATEMENT_ROLES",
    "AmbiguousRole",
    "BankStatementParseError",
    "ColumnRoleMapping",
    "CorpusVerificationSource",
    "CsvProvider",
    "FinancialProvider",
    "FinancialProviderConfigError",
    "FinancialProviderError",
    "FinancialValidationError",
    "InvalidFinancialSourceError",
    "MappedTabularProvider",
    "NormalizedRow",
    "NormalizedTable",
    "OfxProvider",
    "ParsedLedgerRow",
    "PdfN26Provider",
    "ProjectedCell",
    "ProjectedRow",
    "ProjectedTable",
    "ProviderValidation",
    "TabularDialect",
    "TabularMappingResolver",
    "TabularNotice",
    "TabularNoticeCode",
    "UnmappedColumn",
    "UnsupportedFinancialSourceError",
    "XlsxProvider",
    "default_tabular_mapping_resolver",
    "detect_provider",
    "direction_from_signed_amount",
    "normalize_tabular_bytes",
    "normalize_tabular_text",
    "project_table",
    "provider_for_extension",
]
