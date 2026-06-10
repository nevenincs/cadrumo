"""Ledger import command registration for ``aeat app ledger``."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import typer

from ...application.ledger import (
    LedgerSourceImportCommand,
    LedgerSourceImportResult,
    LedgerSourceValidationReport,
    LedgerSourceVerificationReport,
    import_ledger_source,
)
from ...core import resolve_active_bucket_id
from ...core.i18n import tr
from ._common import _bad, _emit_envelope, _optional_canonical_period, _state, _tx_repo


def _known_import_providers() -> tuple[str, ...]:
    """Return the tuple of recognised provider ids from the canonical enum."""
    from ...application.ledger import LedgerProviderID

    return tuple(p.value for p in LedgerProviderID)


def _provider_catalogue_text() -> str:
    """Return the comma-joined recognised provider ids for messages."""
    return ", ".join(_known_import_providers())


def _validate_import_provider(provider: str) -> str:
    """Reject an unrecognised import provider with a discoverable message."""
    normalised = provider.strip().lower()
    if normalised not in _known_import_providers():
        raise _bad(
            tr(
                "cli.ledger.errors.unknown_provider",
                provider=provider,
                providers=_provider_catalogue_text(),
            )
        )
    return normalised


def register_import_commands(app: typer.Typer) -> None:
    """Register ledger import commands."""

    @app.command("import", help=tr("cli.ledger.import.help"))
    def ledger_import(
        ctx: typer.Context,
        path: Path = typer.Argument(..., help=tr("cli.ledger.import.path_help")),
        provider: str = typer.Option(
            ...,
            "--provider",
            help=tr("cli.ledger.import.provider_help", providers=_provider_catalogue_text()),
        ),
        dry_run: bool = typer.Option(False, "--dry-run", help=tr("cli.ledger.import.dry_run_help")),
        verify: bool = typer.Option(False, "--verify", help=tr("cli.ledger.import.verify_help")),
        source: Path | None = typer.Option(None, "--source", help=tr("cli.ledger.import.source_help")),
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
        bucket_id: str | None = None
        actor = "operator"
        transaction_repository = None
        # A real import requires an active profile. A dry run resolves the
        # active bucket when one exists so the preview can count rows against
        # the stored catalogue, but it still works on a cold workspace.
        if dry_run:
            if resolve_active_bucket_id() is not None:
                transaction_repository = _tx_repo(_state())
                bucket_id = transaction_repository.bucket_id
        else:
            current_state = _state()
            transaction_repository = _tx_repo(current_state)
            bucket_id = transaction_repository.bucket_id
            actor = resolve_active_bucket_id() or "operator"

        from ...adapters.outbound.fx import default_ecb_rate_provider
        from ...domain.currency import CurrencyNormalizationService

        currency_normalizer = CurrencyNormalizationService(rate_provider=default_ecb_rate_provider())
        canonical_period = _optional_canonical_period(period, year=year)
        import_paths = _resolve_import_paths(path)
        file_results = [
            import_ledger_source(
                LedgerSourceImportCommand(
                    bucket_id=bucket_id,
                    path=file_path,
                    provider=normalised_provider,
                    dry_run=dry_run,
                    verify=verify,
                    source=source,
                    period=canonical_period,
                    actor=actor,
                    source_command="aeat app ledger import",
                ),
                transaction_repository=transaction_repository,
                currency_normalizer=currency_normalizer,
            )
            for file_path in import_paths
        ]
        result = file_results[0] if len(file_results) == 1 else _aggregate_import_results(file_results)
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
        from ._ledger_payloads import LedgerImportPayload

        _emit_envelope(
            ctx,
            command="ledger.import",
            result=LedgerImportPayload.from_result(
                result,
                dry_run_notice=dry_run_notice,
                empty_import_notice=empty_import_notice,
                likely_duplicate_notice=likely_duplicate_notice,
            ),
            lines=lines,
        )


_IMPORT_DIR_EXTENSIONS = frozenset({".csv", ".xlsx", ".xls", ".ofx", ".qfx", ".tsv"})


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
            )
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
