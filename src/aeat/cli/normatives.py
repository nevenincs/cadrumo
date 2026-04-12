"""``aeat normatives`` sub-app — Spanish tax normatives corpus CLI."""

from __future__ import annotations

import typer
from rich.console import Console
from rich.table import Table

from aeat.normatives import (
    NormativeError,
    NormativeNotFoundError,
    cite,
    find_reference,
    load_catalogue,
    raise_on_errors,
    short_title,
    verify_catalogue,
)

app = typer.Typer(
    name="normatives",
    no_args_is_help=True,
    help="Spanish tax normatives corpus helpers (#45).",
)

_console = Console()


@app.command(name="list", help="List every normative in the corpus, optionally filtered by tag.")
def list_normatives(
    tag: str | None = typer.Option(None, "--tag", "-t", help="Filter by tag, e.g. 'irpf'."),
) -> None:
    """Render the normative catalogue as a rich table."""
    catalogue = load_catalogue()
    table = Table(title="aeat normatives", header_style="bold")
    table.add_column("id", style="cyan")
    table.add_column("kind", style="white")
    table.add_column("number", style="white")
    table.add_column("short title", style="white")
    table.add_column("articulos", justify="right", style="white")
    table.add_column("tags", style="dim")
    count = 0
    for reference in catalogue:
        if tag is not None and tag not in reference.tags:
            continue
        table.add_row(
            reference.id,
            reference.kind.value,
            reference.number,
            short_title(reference),
            str(len(reference.articulos)),
            ", ".join(reference.tags),
        )
        count += 1
    _console.print(table)
    typer.echo(f"{count} normative(s)")


@app.command(name="show", help="Show a single normative's metadata and article index.")
def show(
    ref_id: str = typer.Argument(..., help="Stable id, e.g. 'ley-35-2006'."),
) -> None:
    """Print the metadata + article index for a single normative."""
    catalogue = load_catalogue()
    try:
        reference = find_reference(catalogue, ref_id)
    except NormativeNotFoundError as exc:
        typer.secho(str(exc), fg=typer.colors.RED)
        raise typer.Exit(code=1) from exc
    typer.echo(f"id: {reference.id}")
    typer.echo(f"kind: {reference.kind.value}")
    typer.echo(f"number: {reference.number}")
    typer.echo(f"title (es): {reference.title.get('es', '')}")
    typer.echo(f"published_at: {reference.published_at.isoformat()}")
    typer.echo(f"boe_id: {reference.boe_id}")
    typer.echo(f"boe_url: {reference.boe_url}")
    typer.echo(f"tags: {', '.join(reference.tags)}")
    typer.echo(f"reviewed_by: {reference.reviewed_by}")
    typer.echo(f"last_reviewed_at: {reference.last_reviewed_at.isoformat()}")
    if not reference.articulos:
        typer.echo("(no articulos codified)")
        return
    table = Table(title=f"{reference.id} articulos", header_style="bold")
    table.add_column("numero", style="cyan")
    table.add_column("titulo (es)", style="white")
    table.add_column("cite", style="dim")
    for articulo in reference.articulos:
        table.add_row(
            articulo.numero,
            articulo.titulo.get("es", ""),
            cite(reference, articulo),
        )
    _console.print(table)


@app.command(name="verify", help="Validate every normative against the schema and cross-references.")
def verify() -> None:
    """Run the verification pipeline and exit non-zero on errors."""
    try:
        report = verify_catalogue()
    except NormativeError as exc:
        typer.secho(f"verify failed: {exc}", fg=typer.colors.RED)
        raise typer.Exit(code=1) from exc
    if report.clean:
        typer.secho("✓ verify clean", fg=typer.colors.GREEN)
        return
    table = Table(title="verify findings", header_style="bold")
    table.add_column("level", style="white")
    table.add_column("code", style="cyan")
    table.add_column("reference", style="dim")
    table.add_column("message", style="white")
    for issue in report.issues:
        colour = "red" if issue.level == "error" else "yellow"
        table.add_row(
            f"[{colour}]{issue.level}[/{colour}]",
            issue.code,
            issue.reference_id or "-",
            issue.message,
        )
    _console.print(table)
    try:
        raise_on_errors(report)
    except NormativeError as exc:
        typer.secho(str(exc), fg=typer.colors.RED)
        raise typer.Exit(code=1) from exc


__all__ = ["app"]
