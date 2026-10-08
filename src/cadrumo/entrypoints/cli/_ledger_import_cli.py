"""Ledger import behavior handlers for ``aeat app ledger``."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import typer

from ...application.ledger.actions_import import LedgerProviderID, plan_ledger_import_sources
from ...application.ledger.import_operation import (
    MAX_LEDGER_IMPORT_FILES,
    LedgerImportFileRefusal,
    LedgerImportResultProjection,
    LedgerImportSourceProjection,
    LedgerImportValidationProjection,
)
from ...core.i18n.render import tr
from ...core.json_contract import Notice, NoticeSeverity
from ...domain.transactions.errors import TransactionValidationError
from ._ledger_payloads import LedgerImportPayload
from .common import bad, emit_envelope
from .period_parsing import _optional_canonical_period
from .runtime_ledger_import import import_ledger_sources_for_cli


def _known_import_providers() -> tuple[str, ...]:
    """Return the tuple of recognised provider ids from the canonical enum."""
    return tuple(provider.value for provider in LedgerProviderID)


def _provider_catalogue_text() -> str:
    """Return the comma-joined recognised provider ids for messages."""
    return ", ".join(_known_import_providers())


def _validate_import_provider(provider: str) -> LedgerProviderID:
    """Normalise a provider id and retain a closed-set CLI backstop."""
    normalised = provider.strip().lower()
    if normalised not in _known_import_providers():
        raise bad(
            tr(
                "cli.ledger.errors.unknown_provider",
                provider=provider,
                providers=_provider_catalogue_text(),
            ),
        )
    return LedgerProviderID(normalised)


def _refusal_message(refusal: LedgerImportFileRefusal) -> str:
    """Explain one refused statement; an own-account mismatch names its cause."""
    if refusal.reason_code == "own_account_mismatch":
        return tr("cli.ledger.import.file_refused_account_mismatch", file=refusal.file_name)
    return tr("cli.ledger.import.file_refused", file=refusal.file_name)


class _ImportReport:
    """The text projection and canonical non-blocking notices."""

    def __init__(self, lines: list[str], notices: list[Notice]) -> None:
        self.lines = lines
        self.notices = notices


def _refused_file_report(refusals: Sequence[LedgerImportFileRefusal]) -> _ImportReport:
    """Render every refused statement using a safe filename and reason code."""
    lines: list[str] = []
    notices: list[Notice] = []
    for refusal in refusals:
        lines.append(f"  refused\t{refusal.file_name}\t{refusal.reason_code}")
        notices.append(
            Notice(
                severity=NoticeSeverity.WARNING,
                code="ledger.import.file_refused",
                message=_refusal_message(refusal),
                context={"file": refusal.file_name, "reason_code": refusal.reason_code},
            ),
        )
    return _ImportReport(lines=lines, notices=notices)


def _import_report(result: LedgerImportResultProjection, *, verbose: bool, verify: bool) -> _ImportReport:
    """Render counted totals and bounded validation facts for one import."""
    lines = [
        f"{tr('cli.ledger.labels.rows')}\t{result.rows}",
        f"{tr('cli.ledger.labels.imported')}\t{result.imported}",
        f"{tr('cli.ledger.labels.skipped')}\t{result.skipped}",
    ]
    notices: list[Notice] = []
    if result.dry_run:
        lines.append(f"{tr('cli.ledger.labels.dry_run')}\t{tr('cli.ledger.labels.yes')}")
        message = tr("cli.ledger.import.dry_run_preview")
        lines.append(f"{tr('cli.ledger.labels.notice')}\t{message}")
        notices.append(
            Notice(
                severity=NoticeSeverity.INFO,
                code="ledger.import.dry_run_preview",
                message=message,
                context={"dry_run": "true", "would_import": str(result.imported), "would_skip": str(result.skipped)},
            ),
        )
    empty_import = _empty_import_notice(result)
    if empty_import is not None:
        lines.append(empty_import[0])
        notices.append(empty_import[1])
    if result.likely_duplicates > 0:
        message = tr("cli.ledger.import.likely_duplicates", count=result.likely_duplicates)
        lines.append(f"{tr('cli.ledger.labels.warning')}\t{message}")
        notices.append(
            Notice(
                severity=NoticeSeverity.WARNING,
                code="ledger.import.likely_duplicates",
                message=message,
                context={"likely_duplicate_count": str(result.likely_duplicates)},
            ),
        )
    if verbose or verify:
        for validation, source in zip(result.validations, result.sources, strict=True):
            lines.extend(_validation_lines(validation, source))
    return _ImportReport(lines=lines, notices=notices)


def ledger_import(
    ctx: typer.Context,
    file: Path,
    provider: LedgerProviderID,
    dry_run: bool = False,
    verify: bool = False,
    verify_source: Path | None = None,
    verbose: bool = False,
    period: str | None = None,
    year: int | None = None,
    account: str | None = None,
) -> None:
    """Import statement files through the exact-profile operation registry."""
    normalised_provider = _validate_import_provider(provider)
    import_paths = _resolve_import_paths(file)
    if len(import_paths) > MAX_LEDGER_IMPORT_FILES:
        raise bad(
            tr(
                "cli.ledger.errors.command_input_invalid",
                details=f"ledger import accepts at most {MAX_LEDGER_IMPORT_FILES} files per operation",
            ),
        )
    canonical_period = _optional_canonical_period(period, year=year)
    completed = import_ledger_sources_for_cli(
        ctx,
        files=import_paths,
        provider=normalised_provider,
        dry_run=dry_run,
        verify=verify,
        verify_source=verify_source,
        period=canonical_period,
        own_account_id=account,
    )
    result = completed.projection
    if not result.validations and result.refused_files:
        raise bad(_refusal_message(result.refused_files[0]))
    report = _import_report(result, verbose=verbose, verify=verify)
    refused = _refused_file_report(result.refused_files)
    report.lines.extend(refused.lines)
    report.notices.extend(refused.notices)
    emit_envelope(
        ctx,
        command="ledger.import",
        result=_ledger_import_payload(result),
        lines=report.lines,
        notices=report.notices,
    )


def _resolve_import_paths(path: Path) -> tuple[Path, ...]:
    """Resolve a file/folder using the canonical source-selection contract."""
    try:
        return plan_ledger_import_sources(path)
    except TransactionValidationError as exc:
        raise bad(tr("cli.ledger.import.empty_directory", path=str(path))) from exc


def _empty_import_notice(result: LedgerImportResultProjection) -> tuple[str, Notice] | None:
    """Return an explanatory line when a parsed import yields zero rows."""
    if result.dry_run or result.imported > 0:
        return None
    if result.skipped > 0:
        message = tr("cli.ledger.import.all_rows_skipped", skipped=result.skipped)
        return (
            f"{tr('cli.ledger.labels.notice')}\t{message}",
            Notice(
                severity=NoticeSeverity.INFO,
                code="ledger.import.all_rows_skipped",
                message=message,
                context={"imported": "0", "skipped": str(result.skipped)},
            ),
        )
    if result.period is not None and result.rows == 0:
        message = tr("cli.ledger.import.no_rows_in_period")
        return (
            f"{tr('cli.ledger.labels.notice')}\t{message}",
            Notice(
                severity=NoticeSeverity.INFO,
                code="ledger.import.no_rows_in_period",
                message=message,
                context={"imported": "0", "skipped": "0"},
            ),
        )
    message = tr("cli.ledger.import.no_rows_imported")
    return (
        f"{tr('cli.ledger.labels.notice')}\t{message}",
        Notice(
            severity=NoticeSeverity.INFO,
            code="ledger.import.no_rows_imported",
            message=message,
            context={"imported": "0", "skipped": "0"},
        ),
    )


def _validation_lines(
    validation: LedgerImportValidationProjection,
    source_verification: LedgerImportSourceProjection,
) -> list[str]:
    valid_label = tr("cli.ledger.labels.yes") if validation.valid else tr("cli.ledger.labels.no")
    lines = [
        f"{tr('cli.ledger.labels.valid')}\t{valid_label}",
        f"{tr('cli.ledger.labels.dialect')}\t-",
    ]
    if validation.warning_count:
        lines.append(
            f"{tr('cli.ledger.labels.warnings')}\t{validation.warning_count} validation warning(s); details withheld",
        )
    if source_verification.requested:
        source_value = source_verification.sha256 or "-"
        lines.append(f"{tr('cli.ledger.labels.source')}\t{source_value}")
    return lines


def _ledger_import_payload(result: LedgerImportResultProjection) -> LedgerImportPayload:
    """Adapt the allowlisted operation result to the stable CLI envelope."""
    return LedgerImportPayload.model_validate(
        {
            "rows": result.rows,
            "imported": result.imported,
            "skipped": result.skipped,
            "likely_duplicates": result.likely_duplicates,
            "dry_run": result.dry_run,
            "verify": result.verify,
            "period": result.period.to_period() if result.period is not None else None,
            "bucket_id": result.bucket_id,
            "import_batch_id": result.import_batch_id,
            "bucket_event_ids": list(result.bucket_event_ids),
            "imported_transaction_refs": [item.model_dump(mode="json") for item in result.imported_transaction_refs],
            "skipped_transaction_refs": [item.model_dump(mode="json") for item in result.skipped_transaction_refs],
            "likely_duplicate_transaction_refs": [
                item.model_dump(mode="json") for item in result.likely_duplicate_transaction_refs
            ],
            "validations": [
                {
                    "valid": item.valid,
                    "warnings": (
                        [f"{item.warning_count} validation warning(s); details withheld"] if item.warning_count else []
                    ),
                    "encoding": item.encoding,
                    "dialect": None,
                }
                for item in result.validations
            ],
            "sources": [{"requested": item.requested, "path": None, "sha256": item.sha256} for item in result.sources],
            "diagnostics": [
                {
                    "kind": item.kind,
                    "severity": item.severity,
                    "message": item.message,
                    "source_path": None,
                    "source_locator": None,
                    "affected_transaction_ids": list(item.affected_transaction_ids),
                }
                for item in result.diagnostics
            ],
        },
    )


__all__ = ["ledger_import"]
