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
from itertools import pairwise
from pathlib import Path

from pydantic import BaseModel

from ...core.models import STRICT_FROZEN_CONFIG
from ...core.errors.severity import BaseSeverity
from ...core.i18n import Translatable as tr
from ...core.logging import get_logger
from ...domain.transactions.models import TransactionCatalogue, derive_transaction_id, existing_transaction_import_fingerprints
from ...domain.transactions.raw_transaction import RawTransaction
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
    # The duplicate check keys on the stable import fingerprint — the
    # same identity the persisting import path deduplicates on — so a
    # verify run's preview agrees with what a real import would do,
    # including across file formats and after a transaction is edited.
    existing_fingerprints = _existing_import_fingerprints(existing_catalogue)

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

    imported_count, skipped_count, row_diagnostics, dates = _process_import_rows(
        rows,
        row_fingerprints,
        source_path=source_path,
        existing_fingerprints=existing_fingerprints,
    )
    diagnostics.extend(row_diagnostics)

    # Gap check
    _append_gap_diagnostic(diagnostics, dates, source_path=source_path)

    # Original file check
    _append_original_file_diagnostic(diagnostics, original_source_path)

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


def _existing_import_fingerprints(existing_catalogue: TransactionCatalogue) -> set[str]:
    return {
        fingerprint
        for transaction in existing_catalogue.values()
        for fingerprint in existing_transaction_import_fingerprints(transaction)
    }


def _process_import_rows(
    rows: tuple[RawTransaction, ...],
    row_fingerprints: tuple[str, ...],
    *,
    source_path: Path,
    existing_fingerprints: set[str],
) -> tuple[int, int, list[LedgerImportDiagnostic], list[_datetime.date]]:
    diagnostics: list[LedgerImportDiagnostic] = []
    imported_count = 0
    skipped_count = 0
    dates: list[_datetime.date] = []
    seen_fingerprints: set[str] = set()
    seen_transaction_ids: set[str] = set()
    for raw, fingerprint in zip(rows, row_fingerprints, strict=True):
        tx_id = derive_transaction_id(raw)
        verdict = classify_import_row(
            fingerprint=fingerprint,
            transaction_id=tx_id,
            stored_fingerprints=existing_fingerprints,
            batch_fingerprints=seen_fingerprints,
            batch_transaction_ids=seen_transaction_ids,
        )
        diagnostic = _duplicate_diagnostic(verdict, tx_id, source_path=source_path)
        if diagnostic is not None:
            diagnostics.append(diagnostic)
        if verdict.imports:
            imported_count += 1
            seen_transaction_ids.add(tx_id)
        else:
            skipped_count += 1
        seen_fingerprints.add(fingerprint)
        value_date = raw.value_date or raw.booked_date
        if value_date:
            dates.append(value_date)
    return imported_count, skipped_count, diagnostics, dates


def _duplicate_diagnostic(
    verdict: ImportRowVerdict,
    transaction_id: str,
    *,
    source_path: Path,
) -> LedgerImportDiagnostic | None:
    if verdict is ImportRowVerdict.DUPLICATE_OF_STORED:
        severity = BaseSeverity.INFO
        message = tr("transactions.import.message_082074")
    elif verdict is ImportRowVerdict.COLLIDING_TRANSACTION_ID:
        severity = BaseSeverity.WARNING
        message = tr("transactions.import.batch_id_collision")
    elif verdict is ImportRowVerdict.REPEATED_IN_BATCH:
        # Advisory, not a skip: both rows import.
        severity = BaseSeverity.WARNING
        message = tr("transactions.import.message_053465")
    else:
        return None
    return build_ledger_import_diagnostic(
        kind=LedgerImportDiagnosticKind.DUPLICATE,
        severity=severity,
        message=message,
        source_path=source_path,
        affected_transaction_ids=(transaction_id,),
    )


def _append_gap_diagnostic(
    diagnostics: list[LedgerImportDiagnostic],
    dates: list[_datetime.date],
    *,
    source_path: Path,
) -> None:
    dates.sort()
    if any((right - left) > _datetime.timedelta(days=35) for left, right in pairwise(dates)):
        diagnostics.append(
            build_ledger_import_diagnostic(
                kind=LedgerImportDiagnosticKind.GAP,
                severity=BaseSeverity.WARNING,
                message=tr("transactions.import.message_829073"),
                source_path=source_path,
            ),
        )


def _append_original_file_diagnostic(
    diagnostics: list[LedgerImportDiagnostic],
    original_source_path: Path | None,
) -> None:
    if original_source_path is None or not original_source_path.exists():
        return
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
