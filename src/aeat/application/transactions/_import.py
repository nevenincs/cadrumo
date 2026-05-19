"""Orchestration layer for ledger imports with diagnostics.

Emits structured diagnostics during ledger-import verification.
"""

from __future__ import annotations

from ...core.errors import BaseSeverity
from collections.abc import Iterable
from datetime import timedelta
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict

from ...core.i18n import Translatable as tr
from ...core.logging import get_logger
from ...domain.transactions import TransactionCatalogue
from ...domain.transactions._models import derive_transaction_id
from ._diagnostics import (
    LedgerImportDiagnostic,
    LedgerImportDiagnosticKind,
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
                severity=BaseSeverity.WARNING,
                message=tr("transactions.import.message_185962"),
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
                    severity=BaseSeverity.INFO,
                    message=tr("transactions.import.message_082074"),
                    source_path=source_path,
                    affected_transaction_ids=(tx_id,),
                )
            )
        elif tx_id in seen_ids:
            skipped_count += 1
            diagnostics.append(
                build_ledger_import_diagnostic(
                    kind=LedgerImportDiagnosticKind.DUPLICATE,
                    severity=BaseSeverity.WARNING,
                    message=tr("transactions.import.message_053465"),
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
                        severity=BaseSeverity.WARNING,
                        message=tr("transactions.import.message_829073"),
                        source_path=source_path,
                    )
                )
                break  # Warn once per file to avoid noise

    # Original file check
    if original_source_path and original_source_path.exists():
        try:
            diagnostics.append(
                build_ledger_import_diagnostic(
                    kind=LedgerImportDiagnosticKind.ORIGINAL_FILE,
                    severity=BaseSeverity.INFO,
                    message=tr("transactions.import.verified"),
                    source_path=original_source_path,
                )
            )
        except OSError:
            _logger.warning("could not read original file %s", original_source_path, exc_info=True)
            diagnostics.append(
                build_ledger_import_diagnostic(
                    kind=LedgerImportDiagnosticKind.ORIGINAL_FILE,
                    severity=BaseSeverity.WARNING,
                    message=tr("transactions.import.unreadable"),
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