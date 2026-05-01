"""`aeat financial ingest` command."""

from __future__ import annotations

import sys
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING

import typer
from rich.console import Console
from rich.json import JSON

from ....domain.financial import CsvProvider, OfxProvider, PdfN26Provider, XlsxProvider, detect_provider
from ....domain.financial.providers import FinancialProviderError, RawTransaction

if TYPE_CHECKING:
    from ....domain.financial.transactions import ImportSummary

_CONSOLE = Console()


class ProviderChoice(StrEnum):
    """Selectable ingest-provider names."""

    AUTO = "auto"
    CSV = "csv"
    XLSX = "xlsx"
    OFX = "ofx"
    N26_PDF = "n26-pdf"


def ingest_cmd(
    path: Path = typer.Argument(..., exists=True, dir_okay=False, help="Path to the source file."),
    provider: ProviderChoice = typer.Option(
        ProviderChoice.AUTO,
        "--provider",
        case_sensitive=False,
        help="Provider selection: csv, xlsx, ofx, n26-pdf, or auto.",
    ),
    output_json: bool = typer.Option(
        False,
        "--output-json",
        help="Emit RawTransaction records as newline-delimited JSON on stdout.",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        help="Pretty-print each emitted RawTransaction after ingest.",
    ),
    persist: bool | None = typer.Option(
        None,
        "--persist/--no-persist",
        help=(
            "When ON, parsed rows are merged through the governed "
            "TransactionCatalogueRepository (encrypted-at-rest at "
            "FINANCIAL classification, idempotent re-imports, "
            "file-locked for concurrency). Default: ON when stdout is "
            "a TTY, OFF when piped (preserves the existing "
            "RawTransaction-jsonl-to-stdout behaviour)."
        ),
    ),
    catalogue_dir: Path | None = typer.Option(
        None,
        "--catalogue-dir",
        help=("Optional override for the catalogue directory. Defaults to AEAT_FINANCIAL_TXS_DIR / <provider-name>."),
    ),
) -> None:
    """Validate a source file and emit strict raw transaction records."""
    provider_impl = _resolve_provider(provider, path)
    if provider_impl is None:
        typer.echo(f"refusing: no provider can handle {path}", err=True)
        raise typer.Exit(code=2)
    validation = provider_impl.validate_source(path)
    if not validation.is_valid:
        for warning in validation.warnings:
            typer.echo(f"validation error: {warning}", err=True)
        raise typer.Exit(code=2)
    for warning in validation.warnings:
        typer.echo(f"warning: {warning}", err=True)
    try:
        transactions = tuple(provider_impl.ingest(path))
    except FinancialProviderError as exc:
        typer.echo(f"ingest error: {exc}", err=True)
        raise typer.Exit(code=2) from exc

    # --persist defaults: ON when stdout is a TTY (interactive
    # operator), OFF when piped (preserves the
    # RawTransaction-jsonl-to-stdout pipe-to-file workflow).
    persist_resolved = persist if persist is not None else sys.stdout.isatty()
    summary: ImportSummary | None = None
    if persist_resolved:
        summary = _persist_transactions(transactions, catalogue_dir=catalogue_dir)

    if output_json:
        for transaction in transactions:
            typer.echo(transaction.model_dump_json())
        if summary is not None:
            typer.echo(summary.model_dump_json(), err=True)
        else:
            typer.echo(
                f"ingested {len(transactions)} record(s) via {provider_impl.name}",
                err=True,
            )
        return

    _CONSOLE.print(
        f"[green]ingested[/green] {len(transactions)} record(s) via [bold]{provider_impl.name}[/bold]",
    )
    if summary is not None:
        _CONSOLE.print(
            f"[green]persisted[/green] imported={summary.imported} "
            f"skipped={summary.skipped} catalogue={summary.catalogue_path}",
        )
    if verbose:
        for transaction in transactions:
            _CONSOLE.print(JSON(transaction.model_dump_json(indent=2)))


def _persist_transactions(
    transactions: tuple[RawTransaction, ...],
    *,
    catalogue_dir: Path | None,
) -> ImportSummary:
    """Merge ``transactions`` through the governed repository.

    The repository (and the storage substrate it imports) is loaded
    lazily on first persist so other CLI commands that never touch
    the financial-domain persistence path are not slowed down by
    Alembic plugin discovery during import.
    """
    from ....core.config import load_settings
    from ....domain.financial.transactions import TransactionCatalogueRepository
    from ....domain.financial.transactions._enums import TransactionDirection

    def _direction_from_amount(raw: RawTransaction) -> TransactionDirection:
        # Zero-amount rows (fee waivers, FX-zero adjustments, paired
        # reversals) map to INTERNAL_TRANSFER so the operator sees them
        # as neutral rather than silently classed as OUTGOING.
        if raw.amount > 0:
            return TransactionDirection.INCOMING
        if raw.amount < 0:
            return TransactionDirection.OUTGOING
        return TransactionDirection.INTERNAL_TRANSFER

    if catalogue_dir is None:
        settings = load_settings()
        catalogue_dir = Path(settings.aeat_financial_txs_dir)
    repository = TransactionCatalogueRepository(store_dir=catalogue_dir)
    return repository.merge_raw_transactions(
        transactions,
        direction_resolver=_direction_from_amount,
    )


def _resolve_provider(provider: ProviderChoice, path: Path):
    """Resolve the requested or auto-detected provider instance."""
    if provider is ProviderChoice.AUTO:
        detected = detect_provider(path)
        if detected is not None:
            return detected
        suffix = path.suffix.lower()
        if suffix in {".csv", ".txt"}:
            return CsvProvider()
        if suffix == ".xlsx":
            return XlsxProvider()
        if suffix in {".ofx", ".qfx"}:
            return OfxProvider()
        return None
    if provider is ProviderChoice.CSV:
        return CsvProvider()
    if provider is ProviderChoice.XLSX:
        return XlsxProvider()
    if provider is ProviderChoice.N26_PDF:
        return PdfN26Provider()
    return OfxProvider()
