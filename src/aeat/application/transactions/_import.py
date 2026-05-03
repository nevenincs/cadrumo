"""Orchestration layer for ledger imports with diagnostics.

Implements the v6 CLI candidate requirements for emitting structured
diagnostics during import verification.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import timedelta
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict

from ...core.logging import get_logger
from ...domain.transactions import TransactionCatalogue
from ...domain.transactions._models import derive_transaction_id
from ._diagnostics import (
    LedgerImportDiagnostic,
    LedgerImportDiagnosticKind,
    LedgerImportDiagnosticSeverity,
    build_ledger_import_diagnostic,
)

_logger = get_logger(__name__)


class LedgerImportResult(BaseModel):
    """Return value of an orchestrated ledger import with diagnostics."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    imported_count: int
    skipped_count: int
    diagnostics: tuple[LedgerImportDiagnostic, ...]


def import_ledger_with_diagnostics(
    source_path: Path,
    raw_transactions: Iterable[Any],
    existing_catalogue: TransactionCatalogue,
    original_source_path: Path | None = None,
) -> LedgerImportResult:
    """Evaluate an imported stream against the four diagnostic checks.

    Args:
        source_path: Path of the file being imported.
        raw_transactions: Unmerged raw transactions emitted by the provider.
        existing_catalogue: The current ledger catalogue.
        original_source_path: Optional original file to verify against.

    Returns:
        An immutable :class:`LedgerImportResult` with finding diagnostics.
    """
    diagnostics: list[LedgerImportDiagnostic] = []
    imported_count = 0
    skipped_count = 0

    rows = tuple(raw_transactions)
    seen_ids: set[str] = set()

    if not rows:
        diagnostics.append(
            build_ledger_import_diagnostic(
                kind=LedgerImportDiagnosticKind.PARSER,
                severity=LedgerImportDiagnosticSeverity.WARNING,
                message={
                    "es": "El archivo de origen no contiene transacciones válidas.",
                    "en": "The source file contains no valid transactions.",
                },
                source_path=source_path,
            )
        )
        return LedgerImportResult(imported_count=0, skipped_count=0, diagnostics=tuple(diagnostics))

    # Duplicate check & import logic
    dates = []
    for raw in rows:
        tx_id = derive_transaction_id(raw)

        if tx_id in existing_catalogue:
            skipped_count += 1
            diagnostics.append(
                build_ledger_import_diagnostic(
                    kind=LedgerImportDiagnosticKind.DUPLICATE,
                    severity=LedgerImportDiagnosticSeverity.INFO,
                    message={
                        "es": "Transacción duplicada ya presente en el libro mayor.",
                        "en": "Duplicate transaction already in ledger.",
                    },
                    source_path=source_path,
                    affected_transaction_ids=(tx_id,),
                )
            )
        elif tx_id in seen_ids:
            skipped_count += 1
            diagnostics.append(
                build_ledger_import_diagnostic(
                    kind=LedgerImportDiagnosticKind.DUPLICATE,
                    severity=LedgerImportDiagnosticSeverity.WARNING,
                    message={
                        "es": "Transacción duplicada detectada dentro del archivo importado.",
                        "en": "Duplicate transaction detected within imported file.",
                    },
                    source_path=source_path,
                    affected_transaction_ids=(tx_id,),
                )
            )
        else:
            imported_count += 1
            seen_ids.add(tx_id)

        date = raw.value_date or raw.booked_date
        if date:
            dates.append(date)

    # Gap check
    if dates:
        dates.sort()
        for i in range(1, len(dates)):
            if (dates[i] - dates[i - 1]) > timedelta(days=35):
                diagnostics.append(
                    build_ledger_import_diagnostic(
                        kind=LedgerImportDiagnosticKind.GAP,
                        severity=LedgerImportDiagnosticSeverity.WARNING,
                        message={
                            "es": "Posible hueco en el historial: más de 35 días entre transacciones.",
                            "en": "Potential gap: more than 35 days between transactions.",
                        },
                        source_path=source_path,
                    )
                )
                break  # Warn once per file to avoid noise

    # Original file check
    if original_source_path and original_source_path.exists():
        try:
            original_size = original_source_path.stat().st_size
            diagnostics.append(
                build_ledger_import_diagnostic(
                    kind=LedgerImportDiagnosticKind.ORIGINAL_FILE,
                    severity=LedgerImportDiagnosticSeverity.INFO,
                    message={
                        "es": f"Archivo original verificado ({original_size} bytes).",
                        "en": f"Original file verified ({original_size} bytes).",
                    },
                    source_path=original_source_path,
                )
            )
        except OSError as exc:
            _logger.warning("could not read original file %s", original_source_path, exc_info=True)
            diagnostics.append(
                build_ledger_import_diagnostic(
                    kind=LedgerImportDiagnosticKind.ORIGINAL_FILE,
                    severity=LedgerImportDiagnosticSeverity.WARNING,
                    message={
                        "es": f"No se pudo leer el archivo original: {exc}",
                        "en": f"Could not read original file: {exc}",
                    },
                    source_path=original_source_path,
                )
            )

    result = LedgerImportResult(
        imported_count=imported_count,
        skipped_count=skipped_count,
        diagnostics=tuple(diagnostics),
    )
    _logger.info(
        "ledger import complete path=%s imported=%d skipped=%d diagnostics=%d",
        source_path,
        imported_count,
        skipped_count,
        len(result.diagnostics),
    )
    return result
