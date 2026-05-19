"""Transaction orchestration package.

Transaction catalogue mutation primitives are pure domain services;
import them from :mod:`aeat.domain.transactions`. The application
layer hosts the orchestration the CLI consumes, including the
ledger-import diagnostic surface defined in
:mod:`._diagnostics`.
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
