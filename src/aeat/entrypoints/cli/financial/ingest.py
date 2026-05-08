"""Implement the ``aeat financial ingest`` Typer command.

Wires the inbound financial provider registry
(:mod:`aeat.adapters.inbound.financial.providers`) to the persisted
transaction catalogue
(:class:`aeat.domain.transactions.TransactionCatalogueRepository`).
The command validates a source file, ingests its rows into
:class:`aeat.domain.transactions.RawTransaction`
records, optionally persists them through the governed repository,
and emits either NDJSON or a rich human-readable summary depending on
operator flags and TTY status.
"""

from __future__ import annotations

import sys
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING

import typer
from rich.console import Console
from rich.json import JSON

from ....adapters.inbound.financial.providers import (
    CsvProvider,
    FinancialProviderError,
    OfxProvider,
    PdfN26Provider,
    XlsxProvider,
    detect_provider,
    provider_for_extension,
)
from ....core.logging import get_logger
from ....domain.transactions import RawTransaction
from .._i18n import tr

if TYPE_CHECKING:
    from ....domain.transactions import ImportSummary

_CONSOLE = Console()
_logger = get_logger(__name__)


class ProviderChoice(StrEnum):
    """Selectable inbound provider for ``aeat financial ingest``.

    Each member maps either to a concrete provider class in
    :mod:`aeat.adapters.inbound.financial.providers` or to the
    auto-detection helper :func:`aeat.adapters.inbound.financial.providers.detect_provider`.

    Attributes:
        AUTO: Run the detector first, then fall back to file-extension
            heuristics in :func:`_resolve_provider`.
        CSV: Force :class:`aeat.adapters.inbound.financial.providers.CsvProvider`.
        XLSX: Force :class:`aeat.adapters.inbound.financial.providers.XlsxProvider`.
        OFX: Force :class:`aeat.adapters.inbound.financial.providers.OfxProvider`.
        N26_PDF: Force :class:`aeat.adapters.inbound.financial.providers.PdfN26Provider`.
    """

    AUTO = "auto"
    CSV = "csv"
    XLSX = "xlsx"
    OFX = "ofx"
    N26_PDF = "n26-pdf"


def ingest_cmd(
    path: Path = typer.Argument(..., exists=True, dir_okay=False, help=tr("cli.financial.ingest.path_help")),
    provider: ProviderChoice = typer.Option(
        ProviderChoice.AUTO,
        "--provider",
        case_sensitive=False,
        help=tr("cli.financial.ingest.provider_help"),
    ),
    output_json: bool = typer.Option(
        False,
        "--output-json",
        help=tr("cli.financial.ingest.output_json_help"),
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        help=tr("cli.financial.ingest.verbose_help"),
    ),
    persist: bool | None = typer.Option(
        None,
        "--persist/--no-persist",
        help=tr("cli.financial.ingest.persist_help"),
    ),
) -> None:
    """Validate a source file and emit strict raw transaction records.

    Resolves the requested provider (auto-detecting when ``provider`` is
    :attr:`ProviderChoice.AUTO`), runs the provider's
    :meth:`~aeat.adapters.inbound.financial.providers.FinancialProvider.validate_source`
    check, ingests the file into a tuple of
    :class:`aeat.domain.transactions.RawTransaction`
    records, and then either persists them through
    :func:`_persist_transactions` and/or streams them to stdout.

    Args:
        path: Source file path; must exist and be a regular file.
        provider: Provider selector. ``AUTO`` invokes
            :func:`aeat.adapters.inbound.financial.providers.detect_provider`
            with extension fallbacks.
        output_json: When ``True`` emit each
            :class:`~aeat.domain.transactions.RawTransaction`
            as a JSON line on stdout.
        verbose: When ``True`` pretty-print every emitted record on
            stderr after ingest.
        persist: Tri-state persistence toggle. ``None`` means default
            (ON when stdout is a TTY, OFF when piped) so the legacy
            stdout-only pipe workflow keeps working without a flag.
    Raises:
        :exc:`typer.Exit`: With exit code ``2`` when no provider can
            handle ``path``, when validation fails, or when the
            provider raises
            :exc:`~aeat.adapters.inbound.financial.providers.FinancialProviderError`
            during ingest.
    """
    _logger.info("financial ingest: starting ingest for %s (provider=%s)", path, provider.value)
    provider_impl = _resolve_provider(provider, path)
    if provider_impl is None:
        _logger.warning("financial ingest: no provider can handle %s", path)
        typer.echo(
            tr("cli.ingest.errors.auto_detect_failed", path=path),
            err=True,
        )
        raise typer.Exit(code=2)
    _logger.debug("financial ingest: resolved provider %s for %s", provider_impl.name, path)
    validation = provider_impl.validate_source(path)
    if not validation.is_valid:
        _logger.warning(
            "financial ingest: source validation failed for %s via %s (%d warning(s))",
            path,
            provider_impl.name,
            len(validation.warnings),
        )
        for warning in validation.warnings:
            typer.echo(
                str(warning),
                err=True,
            )
        raise typer.Exit(code=2)
    for warning in validation.warnings:
        typer.echo(
            str(warning),
            err=True,
        )
    try:
        transactions = tuple(provider_impl.ingest(path))
    except FinancialProviderError as exc:
        _logger.warning(
            "financial ingest: provider %s raised an error ingesting %s",
            provider_impl.name,
            path,
            exc_info=True,
        )
        typer.echo(
            tr("cli.ingest.errors.ingest_failed", path=path),
            err=True,
        )
        raise typer.Exit(code=2) from exc
    _logger.info(
        "financial ingest: ingested %d transaction(s) from %s via %s",
        len(transactions),
        path,
        provider_impl.name,
    )

    # --persist defaults: ON when stdout is a TTY (interactive
    # operator), OFF when piped (preserves the
    # RawTransaction-jsonl-to-stdout pipe-to-file workflow).
    persist_resolved = persist if persist is not None else sys.stdout.isatty()
    summary: ImportSummary | None = None
    if persist_resolved:
        _logger.debug("financial ingest: persisting %d transaction(s) to catalogue", len(transactions))
        summary = _persist_transactions(transactions)
        _logger.info(
            "financial ingest: catalogue updated (imported=%d skipped=%d)",
            summary.imported,
            summary.skipped,
        )

    if output_json:
        for transaction in transactions:
            typer.echo(transaction.model_dump_json())
        if summary is not None:
            typer.echo(summary.model_dump_json(), err=True)
        else:
            typer.echo(
                tr("cli.ingest.errors.at_least_one_row"),
                err=True,
            )
        return

    _CONSOLE.print(
        "[green]"
        + tr("cli.ingest.labels.ingesting", path=path)
        + f"[/green] {len(transactions)} "
        + tr("cli.ingest.labels.rows_found", n=len(transactions))
        + f" [bold]{provider_impl.name}[/bold]",
    )
    if summary is not None:
        _CONSOLE.print(
            "[green]" + tr("cli.ingest.labels.complete") + f"[/green] imported={summary.imported} "
            f"skipped={summary.skipped} catalogue={summary.catalogue_path}",
        )
    if verbose:
        for transaction in transactions:
            _CONSOLE.print(JSON(transaction.model_dump_json(indent=2)))


def _persist_transactions(
    transactions: tuple[RawTransaction, ...],
) -> ImportSummary:
    """Merge ``transactions`` through the governed repository.

    The repository (and the storage substrate it imports) is loaded
    lazily on first persist so other CLI commands that never touch
    the financial-domain persistence path are not slowed down by
    Alembic plugin discovery during import.

    Args:
        transactions: Raw provider rows produced by the ingest stage.
    Returns:
        :class:`aeat.domain.transactions.ImportSummary` describing how
        many rows were imported, skipped, and the on-disk catalogue
        location.
    """
    from ....domain.transactions import TransactionCatalogueRepository, TransactionDirection

    def _direction_from_amount(raw: RawTransaction) -> TransactionDirection:
        # Zero-amount rows (fee waivers, FX-zero adjustments, paired
        # reversals) map to INTERNAL_TRANSFER so the operator sees them
        # as neutral rather than silently classed as OUTGOING.
        if raw.amount > 0:
            return TransactionDirection.INCOMING
        if raw.amount < 0:
            return TransactionDirection.OUTGOING
        return TransactionDirection.INTERNAL_TRANSFER

    repository = TransactionCatalogueRepository()
    return repository.merge_raw_transactions(
        transactions,
        direction_resolver=_direction_from_amount,
    )


def _resolve_provider(provider: ProviderChoice, path: Path):
    """Resolve the requested or auto-detected provider instance.

    For :attr:`ProviderChoice.AUTO` the detector
    (:func:`aeat.adapters.inbound.financial.providers.detect_provider`)
    runs first; on miss, file-extension heuristics select
    :class:`~aeat.adapters.inbound.financial.providers.CsvProvider`,
    :class:`~aeat.adapters.inbound.financial.providers.XlsxProvider`,
    or :class:`~aeat.adapters.inbound.financial.providers.OfxProvider`.

    Args:
        provider: Provider selector from ``--provider``.
        path: Source file path used by the auto-detector.

    Returns:
        A provider instance ready for validation and ingest, or
        ``None`` when no provider can handle ``path`` under
        :attr:`ProviderChoice.AUTO`.
    """
    if provider is ProviderChoice.AUTO:
        detected = detect_provider(path)
        if detected is not None:
            return detected
        return provider_for_extension(path)
    if provider is ProviderChoice.CSV:
        return CsvProvider()
    if provider is ProviderChoice.XLSX:
        return XlsxProvider()
    if provider is ProviderChoice.N26_PDF:
        return PdfN26Provider()
    return OfxProvider()
