"""`aeat financial ingest` command."""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path

import typer
from rich.console import Console
from rich.json import JSON

from ...financial import CsvProvider, OfxProvider, PdfN26Provider, XlsxProvider, detect_provider
from ...financial.providers import FinancialProviderError

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
    if output_json:
        for transaction in transactions:
            typer.echo(transaction.model_dump_json())
        typer.echo(
            f"ingested {len(transactions)} record(s) via {provider_impl.name}",
            err=True,
        )
        return
    _CONSOLE.print(
        f"[green]ingested[/green] {len(transactions)} record(s) via [bold]{provider_impl.name}[/bold]",
    )
    if verbose:
        for transaction in transactions:
            _CONSOLE.print(JSON(transaction.model_dump_json(indent=2)))


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
