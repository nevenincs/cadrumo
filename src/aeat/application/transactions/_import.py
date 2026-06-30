"""Orchestration layer for ledger imports with diagnostics.

:func:`import_ledger_with_diagnostics` accepts an existing
:class:`TransactionCatalogue` and an iterable of raw rows. It emits
structured diagnostics for parser-empty, duplicate, calendar-gap, and
original-file checks during import verification.

Duplicate detection uses the stable
:func:`~aeat.domain.transactions.derive_import_fingerprint` identity so
the dry-run diagnostics match the persistence path used by ledger import
actions.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import timedelta
from pathlib import Path

from pydantic import BaseModel

from ...core import STRICT_FROZEN_CONFIG
from ...core.errors import BaseSeverity
from ...core.i18n import Translatable as tr
from ...core.logging import get_logger
from ...domain.transactions import RawTransaction, TransactionCatalogue
from ...domain.transactions._models import derive_import_fingerprint, derive_transaction_id
from ._diagnostics import (
    LedgerImportDiagnostic,
    LedgerImportDiagnosticKind,
    build_ledger_import_diagnostic,
)

_logger = get_logger(__name__)


class LedgerImportResult(BaseModel):
    """Return value of an orchestrated ledger import with diagnostics.

    ``imported_count`` and ``skipped_count`` reflect the previewed outcome for
    the supplied :class:`RawTransaction` rows; ``diagnostics`` carries the
    structured :class:`LedgerImportDiagnostic` records explaining parser,
    duplicate, gap, or original-file findings.
    """

    model_config = STRICT_FROZEN_CONFIG

    imported_count: int
    skipped_count: int
    diagnostics: tuple[LedgerImportDiagnostic, ...]


def import_ledger_with_diagnostics(
    source_path: Path,
    raw_transactions: Iterable[RawTransaction],
    existing_catalogue: TransactionCatalogue,
    original_source_path: Path | None = None,
    import_fingerprints: Iterable[str] | None = None,
) -> LedgerImportResult:
    """Evaluate an imported stream against the four diagnostic checks.

    Args:
        source_path: Path of the file being imported.
        raw_transactions: Unmerged raw transactions emitted by the provider.
        existing_catalogue: The current :class:`TransactionCatalogue` used for
            import-fingerprint duplicate detection.
        original_source_path: Optional original file path to record when it is
            present on disk.
        import_fingerprints: Optional per-row import fingerprints derived by
            the caller from parse-boundary facts such as transaction direction.

    Returns:
        An immutable :class:`LedgerImportResult` with finding diagnostics.
    """
    diagnostics: list[LedgerImportDiagnostic] = []
    imported_count = 0
    skipped_count = 0

    rows = tuple(raw_transactions)
    row_fingerprints = (
        tuple(import_fingerprints)
        if import_fingerprints is not None
        else tuple(derive_import_fingerprint(raw) for raw in rows)
    )
    if len(row_fingerprints) != len(rows):
        raise ValueError("import_fingerprints must contain one fingerprint per raw transaction")
    seen_fingerprints: set[str] = set()
    # The duplicate check keys on the stable import fingerprint — the
    # same identity the persisting import path deduplicates on — so a
    # verify run's preview agrees with what a real import would do,
    # including across file formats and after a transaction is edited.
    existing_fingerprints = {
        fingerprint
        for transaction in existing_catalogue.values()
        for fingerprint in (
            transaction.import_fingerprint,
            derive_import_fingerprint(transaction.raw, direction=transaction.direction),
            derive_import_fingerprint(transaction.raw),
        )
        if fingerprint is not None
    }

    if not rows:
        diagnostics.append(
            build_ledger_import_diagnostic(
                kind=LedgerImportDiagnosticKind.PARSER,
                severity=BaseSeverity.WARNING,
                message=tr("transactions.import.message_185962"),
                source_path=source_path,
            ),
        )
        return LedgerImportResult(imported_count=0, skipped_count=0, diagnostics=tuple(diagnostics))

    # Duplicate check & import logic
    dates = []
    for raw, fingerprint in zip(rows, row_fingerprints, strict=True):
        tx_id = derive_transaction_id(raw)

        if fingerprint in existing_fingerprints:
            skipped_count += 1
            diagnostics.append(
                build_ledger_import_diagnostic(
                    kind=LedgerImportDiagnosticKind.DUPLICATE,
                    severity=BaseSeverity.INFO,
                    message=tr("transactions.import.message_082074"),
                    source_path=source_path,
                    affected_transaction_ids=(tx_id,),
                ),
            )
        elif fingerprint in seen_fingerprints:
            skipped_count += 1
            diagnostics.append(
                build_ledger_import_diagnostic(
                    kind=LedgerImportDiagnosticKind.DUPLICATE,
                    severity=BaseSeverity.WARNING,
                    message=tr("transactions.import.message_053465"),
                    source_path=source_path,
                    affected_transaction_ids=(tx_id,),
                ),
            )
        else:
            imported_count += 1
            seen_fingerprints.add(fingerprint)

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
                    ),
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
                ),
            )
        except OSError:
            _logger.warning("could not read original file %s", original_source_path, exc_info=True)
            diagnostics.append(
                build_ledger_import_diagnostic(
                    kind=LedgerImportDiagnosticKind.ORIGINAL_FILE,
                    severity=BaseSeverity.WARNING,
                    message=tr("transactions.import.unreadable"),
                    source_path=original_source_path,
                ),
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
