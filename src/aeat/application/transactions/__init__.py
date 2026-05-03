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
    LedgerImportDiagnosticSeverity,
    build_ledger_import_diagnostic,
)

__all__ = [
    "LedgerImportDiagnostic",
    "LedgerImportDiagnosticKind",
    "LedgerImportDiagnosticSeverity",
    "build_ledger_import_diagnostic",
]
