"""Orchestration layer for ledger imports with diagnostics.

:func:`~cadrumo.application.transactions.import_ledger_with_diagnostics` accepts an
existing :class:`TransactionCatalogue` and an iterable of
:class:`~cadrumo.domain.transactions.RawTransaction` rows. It emits structured
diagnostics for parser-empty, duplicate, calendar-gap, and original-file checks
during import verification.

Duplicate detection routes through
:func:`~cadrumo.application.transactions.classify_import_row`, the same verdict
the persisting ledger import path consumes, so the diagnostics and the
persistence path cannot disagree about what a row is. They did: this module once
counted a fingerprint repeated within one file as skipped while the persisting
path imported both rows, so ``--verify`` reported a duplicate the import would
never skip. An intra-batch repeat is therefore an advisory here, not a skip.
"""

from __future__ import annotations

import datetime as _datetime
from collections.abc import Iterable
from pathlib import Path

from pydantic import BaseModel

from ...core import STRICT_FROZEN_CONFIG
from ...core.errors import BaseSeverity
from ...core.i18n import Translatable as tr
from ...core.logging import get_logger
from ...domain.transactions import (
    RawTransaction,
    TransactionCatalogue,
    derive_transaction_id,
    existing_transaction_import_fingerprints,
)
from ._diagnostics import (
    LedgerImportDiagnostic,
    LedgerImportDiagnosticKind,
    build_ledger_import_diagnostic,
)
from ._import_classification import ImportRowVerdict, classify_import_row

_logger = get_logger(__name__)


class LedgerImportResult(BaseModel):
    """Return value of an orchestrated ledger import with diagnostics.

    ``imported_count`` and ``skipped_count`` reflect the previewed outcome for
    the supplied :class:`~cadrumo.domain.transactions.RawTransaction` rows;
    ``diagnostics`` carries the structured
    :class:`~cadrumo.application.transactions.LedgerImportDiagnostic` records
    explaining parser, duplicate, gap, or original-file findings.
    """

    model_config = STRICT_FROZEN_CONFIG

    imported_count: int
    skipped_count: int
    diagnostics: tuple[LedgerImportDiagnostic, ...]


def import_ledger_with_diagnostics(
    source_path: Path,
    raw_transactions: Iterable[RawTransaction],
    existing_catalogue: TransactionCatalogue,
    import_fingerprints: Iterable[str],
    original_source_path: Path | None = None,
) -> LedgerImportResult:
    """Evaluate an imported stream against the four diagnostic checks.

    Args:
        source_path: Path of the file being imported.
        raw_transactions: Unmerged raw transactions emitted by the provider.
        existing_catalogue: The current :class:`TransactionCatalogue` used for
            import-fingerprint duplicate detection.
        import_fingerprints: One import fingerprint per raw row, derived by the
            caller with the flow direction the provider read at the parse
            boundary. Required rather than defaulted: a fingerprint derived
            here would carry no direction, and
            :func:`~cadrumo.domain.transactions.derive_import_fingerprint`
            substitutes the literal ``UNSPECIFIED`` discriminator for a missing
            one, which can never equal a stored direction-qualified fingerprint.
            Dedup would then fail open and read every row as new.
        original_source_path: Optional original file path to record when it is
            present on disk.

    Returns:
        An immutable :class:`~cadrumo.application.transactions.LedgerImportResult`
        with finding diagnostics.
    """
    diagnostics: list[LedgerImportDiagnostic] = []
    imported_count = 0
    skipped_count = 0

    rows = tuple(raw_transactions)
    row_fingerprints = tuple(import_fingerprints)
    if len(row_fingerprints) != len(rows):
        raise ValueError("import_fingerprints must contain one fingerprint per raw transaction")
    seen_fingerprints: set[str] = set()
    seen_transaction_ids: set[str] = set()
    # The duplicate check keys on the stable import fingerprint — the
    # same identity the persisting import path deduplicates on — so a
    # verify run's preview agrees with what a real import would do,
    # including across file formats and after a transaction is edited.
    existing_fingerprints = {
        fingerprint
        for transaction in existing_catalogue.values()
        for fingerprint in existing_transaction_import_fingerprints(transaction)
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
    dates: list[_datetime.date] = []
    for raw, fingerprint in zip(rows, row_fingerprints, strict=True):
        tx_id = derive_transaction_id(raw)

        verdict = classify_import_row(
            fingerprint=fingerprint,
            transaction_id=tx_id,
            stored_fingerprints=existing_fingerprints,
            batch_fingerprints=seen_fingerprints,
            batch_transaction_ids=seen_transaction_ids,
        )
        if verdict is ImportRowVerdict.DUPLICATE_OF_STORED:
            diagnostics.append(
                build_ledger_import_diagnostic(
                    kind=LedgerImportDiagnosticKind.DUPLICATE,
                    severity=BaseSeverity.INFO,
                    message=tr("transactions.import.message_082074"),
                    source_path=source_path,
                    affected_transaction_ids=(tx_id,),
                ),
            )
        elif verdict is ImportRowVerdict.COLLIDING_TRANSACTION_ID:
            diagnostics.append(
                build_ledger_import_diagnostic(
                    kind=LedgerImportDiagnosticKind.DUPLICATE,
                    severity=BaseSeverity.WARNING,
                    message=tr("transactions.import.batch_id_collision"),
                    source_path=source_path,
                    affected_transaction_ids=(tx_id,),
                ),
            )
        elif verdict is ImportRowVerdict.REPEATED_IN_BATCH:
            # Advisory, not a skip: both rows import. The message says so, because
            # a "duplicate" the operator assumes was dropped is how a real
            # double-count in the source file goes unreviewed.
            diagnostics.append(
                build_ledger_import_diagnostic(
                    kind=LedgerImportDiagnosticKind.DUPLICATE,
                    severity=BaseSeverity.WARNING,
                    message=tr("transactions.import.message_053465"),
                    source_path=source_path,
                    affected_transaction_ids=(tx_id,),
                ),
            )

        if verdict.imports:
            imported_count += 1
            seen_transaction_ids.add(tx_id)
        else:
            skipped_count += 1
        seen_fingerprints.add(fingerprint)

        date = raw.value_date or raw.booked_date
        if date:
            dates.append(date)

    # Gap check
    if dates:
        dates.sort()
        for i in range(1, len(dates)):
            if (dates[i] - dates[i - 1]) > _datetime.timedelta(days=35):
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
