"""Pre-persistence ledger-import diagnostics package.

Transaction catalogue mutation primitives are pure domain services; import them
from :mod:`domain.transactions`. This application package hosts the
diagnostic preview helper the ledger import path consumes before persistence.

:func:`import_ledger_with_diagnostics` evaluates provider-emitted
:class:`domain.transactions.RawTransaction` rows against an existing
:class:`domain.transactions.TransactionCatalogue`, returns an immutable
:class:`LedgerImportResult`, and leaves catalogue mutation, FX normalization,
and bucket-event emission to :mod:`application.ledger`. Duplicate diagnostics
use the same :func:`domain.transactions.derive_import_fingerprint` identity as
the persisting import path, so dry-run reports and saved imports agree.

See Also:
    :class:`LedgerImportDiagnostic`
        Typed import finding grouped by
        :class:`LedgerImportDiagnosticKind` and
        :class:`core.errors.BaseSeverity`.
    :class:`LedgerImportResult`
        Immutable preview summary containing imported/skipped counts and
        diagnostics.
    :func:`import_ledger_with_diagnostics`
        Diagnostic-only import preview helper.
    :func:`application.ledger.import_ledger_transactions`
        Bucket-scoped import service that persists new transactions and emits
        ledger bucket events.
    :func:`application.ledger.import_ledger_source`
        CLI-facing source import orchestration that parses provider files before
        calling the persisting ledger import path.
"""

from __future__ import annotations

from ._diagnostics import (
    LedgerImportDiagnostic,
    LedgerImportDiagnosticKind,
    build_ledger_import_diagnostic,
)
from ._import import LedgerImportResult, import_ledger_with_diagnostics

__all__ = [
    "LedgerImportDiagnostic",
    "LedgerImportDiagnosticKind",
    "LedgerImportResult",
    "build_ledger_import_diagnostic",
    "import_ledger_with_diagnostics",
]
