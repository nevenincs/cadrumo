"""Ledger import command registration for ``aeat app ledger``."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

import typer

from ...application.ledger import (
    LedgerProviderID,
    LedgerSourceImportCommand,
    LedgerSourceImportResult,
    LedgerSourceValidationReport,
    LedgerSourceVerificationReport,
    import_ledger_source,
)
from ...core import resolve_active_bucket_id
from ...core.errors import CadrumoError, resolve_error_message
from ...core.external_constants import XLS_EXTENSION, XLSX_EXTENSION
from ...core.i18n import tr
from ...core.json_contract import Notice, NoticeSeverity
from ._common import _bad, _emit_envelope, _optional_canonical_period, _state, _tx_repo

if TYPE_CHECKING:
    from ...domain.currency import CurrencyNormalizationService
    from ...domain.transactions import TransactionCatalogueRepositoryProtocol


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
    at parse time with the accepted set (the CLI-boundary rule), and the built MCP
    input schema surfaces the closed set as a JSON ``enum``. This normaliser keeps
    the strip + lowercase pass and stays a defence-in-depth membership backstop for
    any non-``Choice`` caller.
    """
    normalised = provider.strip().lower()
    if normalised not in _known_import_providers():
        raise _bad(
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
    """The operator-facing text lines plus the notice strings the payload echoes."""

    lines: list[str]
    dry_run_notice: str | None
    empty_import_notice: str | None
    likely_duplicate_notice: str | None


def _import_bucket_context(*, dry_run: bool) -> _ImportBucketContext:
    """Resolve the bucket an import writes to, and the actor it is recorded under.

    A real import requires an active profile. A dry run resolves the active
    bucket when one exists so the preview can count rows against the stored
    catalogue, but it still works on a cold workspace.
    """
    if not dry_run:
        transaction_repository = _tx_repo(_state())
        return _ImportBucketContext(
            bucket_id=transaction_repository.bucket_id,
            actor=resolve_active_bucket_id() or "operator",
            transaction_repository=transaction_repository,
        )
    if resolve_active_bucket_id() is None:
        return _ImportBucketContext(bucket_id=None, actor="operator", transaction_repository=None)
    transaction_repository = _tx_repo(_state())
    return _ImportBucketContext(
        bucket_id=transaction_repository.bucket_id,
        actor="operator",
        transaction_repository=transaction_repository,
    )


def _imported_files(
    import_paths: list[Path],
    *,
    command: Callable[[Path], LedgerSourceImportCommand],
    transaction_repository: TransactionCatalogueRepositoryProtocol | None,
    currency_normalizer: CurrencyNormalizationService,
) -> tuple[list[LedgerSourceImportResult], list[tuple[Path, str]]]:
    """Import each statement file, returning the successes and the refusals apart.

    Caught per FILE, so one unreadable statement cannot discard the results
    already produced for the rest of the folder. Only the project's own failure
    taxonomy is caught: a TypeError here is a defect and must still crash rather
    than be reported as a bad statement.
    """
    file_results: list[LedgerSourceImportResult] = []
    refusals: list[tuple[Path, str]] = []
    for file_path in import_paths:
        try:
            file_results.append(
                import_ledger_source(
                    command(file_path),
                    transaction_repository=transaction_repository,
                    currency_normalizer=currency_normalizer,
                ),
            )
        except CadrumoError as exc:
            refusals.append((file_path, resolve_error_message(exc)))
    return file_results, refusals


def _import_report(result: LedgerSourceImportResult, *, verbose: bool, verify: bool) -> _ImportReport:
    """Render the counted totals, and every notice line they imply, for one import."""
    lines = [
        f"{tr('cli.ledger.labels.rows')}\t{result.rows}",
        f"{tr('cli.ledger.labels.imported')}\t{result.imported}",
        f"{tr('cli.ledger.labels.skipped')}\t{result.skipped}",
    ]
    dry_run_notice: str | None = None
    likely_duplicate_notice: str | None = None
    if result.dry_run:
        lines.append(f"{tr('cli.ledger.labels.dry_run')}\t{tr('cli.ledger.labels.yes')}")
        dry_run_notice = f"{tr('cli.ledger.labels.notice')}\t{tr('cli.ledger.import.dry_run_preview')}"
        lines.append(dry_run_notice)
    empty_import_notice = _empty_import_notice(result)
    if empty_import_notice is not None:
        lines.append(empty_import_notice)
    if result.likely_duplicates > 0:
        likely_duplicate_notice = (
            f"{tr('cli.ledger.labels.warning')}\t"
            f"{tr('cli.ledger.import.likely_duplicates', count=result.likely_duplicates)}"
        )
        lines.append(likely_duplicate_notice)
    if verbose or verify:
        lines.extend(_validation_lines(result.validation, result.source))
    return _ImportReport(
        lines=lines,
        dry_run_notice=dry_run_notice,
        empty_import_notice=empty_import_notice,
        likely_duplicate_notice=likely_duplicate_notice,
    )


def _refusal_lines_and_notices(
    refusals: list[tuple[Path, str]],
    *,
    imported_files: int,
) -> tuple[list[str], list[Notice]]:
    """Surface every file that failed inside an otherwise-successful folder import.

    A partially-failed folder must not read as a clean import. The aggregate sums
    only the files that SUCCEEDED, so without these the totals would describe a
    subset while presenting themselves as the whole -- the silent-degradation
    shape, one layer up.
    """
    lines: list[str] = []
    notices: list[Notice] = []
    for refused_path, reason in refusals:
        refusal_line = tr(
            "cli.ledger.import.file_refused",
            path=refused_path.name,
            reason=reason,
        )
        lines.append(f"{tr('cli.ledger.labels.warning')}\t{refusal_line}")
        notices.append(
            Notice(
                severity=NoticeSeverity.WARNING,
                code="ledger.import.file_refused",
                message=refusal_line,
                context={
                    "path": refused_path.name,
                    "reason": reason,
                    "imported_files": str(imported_files),
                    "refused_files": str(len(refusals)),
                },
            ),
        )
    return lines, notices


def _all_files_refused(refusals: list[tuple[Path, str]]) -> typer.BadParameter:
    """Build the hard refusal for an import that produced no result at all.

    Nothing imported at all, which is the single-file failure case as well as a
    folder in which every file failed. That stays a hard refusal: downgrading it
    to a warning would turn today's error exit into a success for an operator who
    imported nothing.
    """
    detail = "; ".join(f"{path.name}: {reason}" for path, reason in refusals)
    return _bad(
        tr(
            "cli.ledger.import.all_files_refused",
            detail=detail,
            default="No statement file could be imported: " + detail,
        ),
    )


def register_import_commands(app: typer.Typer) -> None:
    """Register ledger import commands."""

    @app.command("import", help=tr("cli.ledger.import.help"))
    def ledger_import(
        ctx: typer.Context,
        file: Path = typer.Option(..., "--file", help=tr("cli.ledger.import.file_help")),
        provider: LedgerProviderID = typer.Option(
            ...,
            "--provider",
            help=tr("cli.ledger.import.provider_help", providers=_provider_catalogue_text()),
        ),
        dry_run: bool = typer.Option(False, "--dry-run", help=tr("cli.ledger.import.dry_run_help")),
        verify: bool = typer.Option(False, "--verify", help=tr("cli.ledger.import.verify_help")),
        verify_source: Path | None = typer.Option(
            None,
            "--verify-source",
            help=tr("cli.ledger.import.verify_source_help"),
        ),
        verbose: bool = typer.Option(False, "--verbose", help=tr("cli.ledger.import.verbose_help")),
        period: str | None = typer.Option(None, "--period", help=tr("cli.ledger.import.period_help")),
        year: int | None = typer.Option(
            None,
            "--year",
            help=tr("cli.ledger.import.year_help", default="Filing year for --period (e.g. 2024)."),
        ),
    ) -> None:
        """Import a financial-statement file via the existing provider registry."""
        normalised_provider = _validate_import_provider(provider)
        context = _import_bucket_context(dry_run=dry_run)

        from ...adapters.outbound.fx import default_ecb_rate_provider
        from ...domain.currency import CurrencyNormalizationService

        currency_normalizer = CurrencyNormalizationService(rate_provider=default_ecb_rate_provider())
        canonical_period = _optional_canonical_period(period, year=year)
        file_results, refusals = _imported_files(
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
        if not file_results:
            raise _all_files_refused(refusals)
        result = file_results[0] if len(file_results) == 1 else _aggregate_import_results(file_results)
        report = _import_report(result, verbose=verbose, verify=verify)
        refusal_lines, notices = _refusal_lines_and_notices(refusals, imported_files=len(file_results))

        from ._ledger_payloads import LedgerImportPayload

        _emit_envelope(
            ctx,
            command="ledger.import",
            result=LedgerImportPayload.from_result(
                result,
                dry_run_notice=report.dry_run_notice,
                empty_import_notice=report.empty_import_notice,
                likely_duplicate_notice=report.likely_duplicate_notice,
            ),
            lines=[*report.lines, *refusal_lines],
            notices=notices,
        )


_IMPORT_DIR_EXTENSIONS = frozenset(
    {".csv", XLSX_EXTENSION, XLS_EXTENSION, ".ofx", ".qfx", ".tsv"},
)


def _resolve_import_paths(path: Path) -> list[Path]:
    """Return the statement files to import."""
    if not path.is_dir():
        return [path]
    files = sorted(
        child for child in path.iterdir() if child.is_file() and child.suffix.lower() in _IMPORT_DIR_EXTENSIONS
    )
    if not files:
        raise _bad(
            tr(
                "cli.ledger.import.empty_directory",
                path=str(path),
                default=f"No importable statement files found in directory: {path}",
            ),
        )
    return files


def _aggregate_import_results(results: list[LedgerSourceImportResult]) -> LedgerSourceImportResult:
    """Sum per-file import results into one envelope for a folder import."""
    first = results[0]

    def _concat(attr: str) -> tuple[Any, ...]:
        out: list[Any] = []
        for result in results:
            out.extend(getattr(result, attr))
        return tuple(out)

    return LedgerSourceImportResult(
        rows=sum(r.rows for r in results),
        imported=sum(r.imported for r in results),
        skipped=sum(r.skipped for r in results),
        likely_duplicates=sum(r.likely_duplicates for r in results),
        dry_run=first.dry_run,
        verify=first.verify,
        period=first.period,
        bucket_id=first.bucket_id,
        import_batch_id=first.import_batch_id,
        bucket_event_ids=_concat("bucket_event_ids"),
        imported_transaction_refs=_concat("imported_transaction_refs"),
        skipped_transaction_refs=_concat("skipped_transaction_refs"),
        likely_duplicate_transaction_refs=_concat("likely_duplicate_transaction_refs"),
        validation=first.validation,
        source=first.source,
        diagnostics=_concat("diagnostics"),
    )


def _empty_import_notice(result: LedgerSourceImportResult) -> str | None:
    """Return an explanatory line when a parsed import yields zero rows."""
    if result.dry_run or result.imported > 0:
        return None
    if result.skipped > 0:
        return f"{tr('cli.ledger.labels.notice')}\t{tr('cli.ledger.import.all_rows_skipped', skipped=result.skipped)}"
    return f"{tr('cli.ledger.labels.notice')}\t{tr('cli.ledger.import.no_rows_imported')}"


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
