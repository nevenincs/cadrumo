"""Ledger import behavior handlers for ``aeat app ledger``."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import typer

from ...application.ledger.actions_import import (
    LedgerProviderID,
    aggregate_ledger_import_results,
    import_ledger_source,
    plan_ledger_import_sources,
)
from ...application.ledger.models import (
    LedgerSourceImportCommand,
    LedgerSourceImportResult,
    LedgerSourceValidationReport,
    LedgerSourceVerificationReport,
)
from ...core.bucket_pointer import resolve_active_bucket_id
from ...core.i18n.render import tr
from ...core.json_contract import Notice, NoticeSeverity
from ...domain.transactions.errors import TransactionValidationError
from ._common import bad, current_workflow_state, emit_envelope, transaction_catalogue_repo
from ._ledger_support import ledger_transaction_validation_no_recovery
from .period_parsing import _optional_canonical_period

if TYPE_CHECKING:
    from ...domain.currency.service import CurrencyNormalizationService
    from ...domain.transactions.protocols import TransactionCatalogueRepositoryProtocol


def _known_import_providers() -> tuple[str, ...]:
    """Return the tuple of recognised provider ids from the canonical enum."""
    return tuple(p.value for p in LedgerProviderID)


def _provider_catalogue_text() -> str:
    """Return the comma-joined recognised provider ids for messages."""
    return ", ".join(_known_import_providers())


def _validate_import_provider(provider: str) -> str:
    """Normalise a recognised import provider to its canonical id string.

    The ``--provider`` option is typed as the :class:`LedgerProviderID` enum, so
    Typer renders ``Choice([auto, csv, ...])`` and refuses an unrecognised value
    at parse time with the accepted set (the CLI-boundary rule), and any external
    input schema surfaces the closed set as a JSON ``enum``. This normaliser keeps
    the strip + lowercase pass and stays a defence-in-depth membership backstop for
    any non-``Choice`` caller.
    """
    normalised = provider.strip().lower()
    if normalised not in _known_import_providers():
        raise bad(
            tr(
                "cli.ledger.errors.unknown_provider",
                provider=provider,
                providers=_provider_catalogue_text(),
            ),
        )
    return normalised


@dataclass(frozen=True, slots=True)
class _ImportBucketContext:
    """Where an import writes, and who it is recorded as."""

    bucket_id: str | None
    actor: str
    transaction_repository: TransactionCatalogueRepositoryProtocol | None


@dataclass(frozen=True, slots=True)
class _ImportReport:
    """The text projection and canonical non-blocking notices."""

    lines: list[str]
    notices: list[Notice]


def _import_bucket_context(*, dry_run: bool) -> _ImportBucketContext:
    """Resolve the bucket an import writes to, and the actor it is recorded under.

    A real import requires an active profile. A dry run resolves the active
    bucket when one exists so the preview can count rows against the stored
    catalogue, but it still works on a cold workspace.
    """
    if not dry_run:
        transaction_repository = transaction_catalogue_repo(current_workflow_state())
        return _ImportBucketContext(
            bucket_id=transaction_repository.bucket_id,
            actor=resolve_active_bucket_id() or "operator",
            transaction_repository=transaction_repository,
        )
    if resolve_active_bucket_id() is None:
        return _ImportBucketContext(bucket_id=None, actor="operator", transaction_repository=None)
    transaction_repository = transaction_catalogue_repo(current_workflow_state())
    return _ImportBucketContext(
        bucket_id=transaction_repository.bucket_id,
        actor="operator",
        transaction_repository=transaction_repository,
    )


def _imported_files(
    import_paths: Sequence[Path],
    *,
    command: Callable[[Path], LedgerSourceImportCommand],
    transaction_repository: TransactionCatalogueRepositoryProtocol | None,
    currency_normalizer: CurrencyNormalizationService,
) -> list[LedgerSourceImportResult]:
    """Import each statement file without flattening typed failures.

    Caught per FILE, so one unreadable statement cannot discard the results
    already produced for the rest of the folder. Only the project's own failure
    taxonomy is caught: a TypeError here is a defect and must still crash rather
    than be reported as a bad statement.
    """
    file_results: list[LedgerSourceImportResult] = []
    for file_path in import_paths:
        try:
            file_results.append(
                import_ledger_source(
                    command(file_path),
                    transaction_repository=transaction_repository,
                    currency_normalizer=currency_normalizer,
                ),
            )
        except TransactionValidationError as exc:
            raise ledger_transaction_validation_no_recovery(exc) from None
    return file_results


def _import_report(result: LedgerSourceImportResult, *, verbose: bool, verify: bool) -> _ImportReport:
    """Render the counted totals, and every notice line they imply, for one import."""
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
        # Every file's report, not just the first. A directory import folds
        # several results into one and used to show one file's validation as
        # though it spoke for the import.
        for validation, source in zip(result.validations, result.sources, strict=True):
            lines.extend(_validation_lines(validation, source))
    return _ImportReport(
        lines=lines,
        notices=notices,
    )


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
) -> None:
    """Import a financial-statement file via the existing provider registry."""
    normalised_provider = _validate_import_provider(provider)
    context = _import_bucket_context(dry_run=dry_run)
    from ...adapters.outbound.fx.ecb_provider import default_ecb_rate_provider
    from ...domain.currency.service import CurrencyNormalizationService

    currency_normalizer = CurrencyNormalizationService(rate_provider=default_ecb_rate_provider())
    canonical_period = _optional_canonical_period(period, year=year)
    file_results = _imported_files(
        _resolve_import_paths(file),
        command=lambda file_path: LedgerSourceImportCommand(
            bucket_id=context.bucket_id,
            path=file_path,
            provider=normalised_provider,
            dry_run=dry_run,
            verify=verify,
            source=verify_source,
            period=canonical_period,
            actor=context.actor,
            source_command="aeat app ledger import",
        ),
        transaction_repository=context.transaction_repository,
        currency_normalizer=currency_normalizer,
    )
    result = file_results[0] if len(file_results) == 1 else aggregate_ledger_import_results(file_results)
    report = _import_report(result, verbose=verbose, verify=verify)
    from ._ledger_payloads import LedgerImportPayload

    emit_envelope(
        ctx,
        command="ledger.import",
        result=LedgerImportPayload.from_result(result),
        lines=report.lines,
        notices=report.notices,
    )


def _resolve_import_paths(path: Path) -> tuple[Path, ...]:
    """Resolve the import target, mapping the refusal to its operator message."""
    from ...domain.transactions.errors import TransactionValidationError

    try:
        return plan_ledger_import_sources(path)
    except TransactionValidationError as exc:
        raise bad(tr("cli.ledger.import.empty_directory", path=str(path))) from exc


def _empty_import_notice(result: LedgerSourceImportResult) -> tuple[str, Notice] | None:
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
    validation: LedgerSourceValidationReport,
    source_verification: LedgerSourceVerificationReport,
) -> list[str]:
    validation_payload = validation.model_dump(mode="json")
    source_payload = source_verification.model_dump(mode="json")
    valid_label = tr("cli.ledger.labels.yes") if validation_payload["valid"] else tr("cli.ledger.labels.no")
    lines = [
        f"{tr('cli.ledger.labels.valid')}\t{valid_label}",
        f"{tr('cli.ledger.labels.dialect')}\t{validation_payload['dialect'] or '-'}",
    ]
    if validation_payload["warnings"]:
        lines.append(f"{tr('cli.ledger.labels.warnings')}\t{'; '.join(validation_payload['warnings'])}")
    if source_payload["requested"]:
        lines.append(f"{tr('cli.ledger.labels.source')}\t{source_payload['path'] or '-'}")
    return lines
