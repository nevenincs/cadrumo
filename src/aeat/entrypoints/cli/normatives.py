"""``aeat normatives`` Typer sub-app — Spanish tax normatives corpus CLI.

Exposes the :mod:`aeat.domain.normatives` corpus (legal references,
articles, BOE citations) through ``list``, ``show``, and ``verify``
verbs. Renders results via :mod:`rich` tables for operator-friendly
output.
"""

from __future__ import annotations

import typer
from rich.console import Console
from rich.table import Table

from ...domain.normatives import (
    NormativeError,
    NormativeNotFoundError,
    cite,
    find_reference,
    load_catalogue,
    raise_on_errors,
    short_title,
    verify_catalogue,
)
from ._i18n import output_language, tr

app = typer.Typer(
    name="normatives",
    no_args_is_help=True,
    help=tr("cli.normatives.app_help"),
)

_console = Console()
"""Shared :class:`rich.console.Console` for tabular output."""


@app.command(name="list", help=tr("cli.normatives.list_help"))
def list_normatives(
    tag: str | None = typer.Option(None, "--tag", "-t", help=tr("cli.normatives.list_tag_help")),
) -> None:
    """Render the normative catalogue as a :class:`rich.table.Table`.

    Args:
        tag: Optional tag filter (e.g. ``"irpf"``); only normatives
            carrying ``tag`` in their tag set are listed.
    """
    catalogue = load_catalogue()
    table = Table(title="aeat normatives", header_style="bold")
    table.add_column(tr("cli.normatives.labels.id"), style="cyan")
    table.add_column(tr("cli.normatives.labels.kind"), style="white")
    table.add_column(tr("cli.normatives.labels.number"), style="white")
    table.add_column(tr("cli.normatives.labels.short_title"), style="white")
    table.add_column(tr("cli.normatives.labels.articulos"), justify="right", style="white")
    table.add_column(tr("cli.normatives.labels.tags"), style="dim")
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
    typer.echo(tr("cli.normatives.labels.found", count=count))


@app.command(name="show", help=tr("cli.normatives.show_help"))
def show(
    ref_id: str = typer.Argument(..., help=tr("cli.normatives.show_ref_id_help")),
) -> None:
    """Print the metadata and article index for a single normative.

    Args:
        ref_id: Stable normative identifier (e.g. ``"ley-35-2006"``)
            looked up via :func:`aeat.domain.normatives.find_reference`.

    Raises:
        :exc:`typer.Exit`: With exit code ``1`` when no normative
            matches ``ref_id``.
    """
    catalogue = load_catalogue()
    try:
        reference = find_reference(catalogue, ref_id)
    except NormativeNotFoundError as exc:
        typer.secho(str(exc), fg=typer.colors.RED)
        raise typer.Exit(code=1) from exc
    output_language()
    title_text = reference.title if reference.title else ""
    typer.echo(f"{tr('cli.normatives.labels.id')}: {reference.id}")
    typer.echo(f"{tr('cli.normatives.labels.kind')}: {reference.kind.value}")
    typer.echo(f"{tr('cli.normatives.labels.number')}: {reference.number}")
    typer.echo(f"{tr('cli.normatives.labels.short_title')}: {title_text}")
    typer.echo(f"{tr('cli.normatives.labels.published_at')}: {reference.published_at.isoformat()}")
    typer.echo(f"{tr('cli.normatives.labels.boe_id')}: {reference.boe_id}")
    typer.echo(f"{tr('cli.normatives.labels.boe_url')}: {reference.boe_url}")
    typer.echo(f"{tr('cli.normatives.labels.tags')}: {', '.join(reference.tags)}")
    typer.echo(f"{tr('cli.normatives.labels.reviewed_by')}: {reference.reviewed_by}")
    typer.echo(f"{tr('cli.normatives.labels.last_reviewed_at')}: {reference.last_reviewed_at.isoformat()}")
    if not reference.articulos:
        typer.echo(tr("cli.normatives.labels.no_articulos"))
        return
    table = Table(
        title=f"{reference.id} {tr('cli.normatives.labels.articles')}",
        header_style="bold",
    )
    table.add_column(tr("cli.normatives.headers.numero"), style="cyan")
    table.add_column(tr("cli.normatives.headers.titulo"), style="white")
    table.add_column(tr("cli.normatives.headers.citation"), style="dim")
    for articulo in reference.articulos:
        articulo_title = articulo.titulo if articulo.titulo else ""
        table.add_row(
            articulo.numero,
            articulo_title,
            cite(reference, articulo),
        )
    _console.print(table)


@app.command(name="verify", help=tr("cli.normatives.verify_help"))
def verify() -> None:
    """Run the verification pipeline and exit non-zero on errors.

    Invokes :func:`aeat.domain.normatives.verify_catalogue` and
    surfaces any findings as a :class:`rich.table.Table`. Errors
    propagate to a non-zero exit code via
    :func:`aeat.domain.normatives.raise_on_errors`.

    Raises:
        :exc:`typer.Exit`: With exit code ``1`` when verification
            fails or surfaces error-level findings.
    """
    try:
        report = verify_catalogue()
    except NormativeError as exc:
        typer.secho(
            tr("cli.normatives.errors.load_failed"),
            fg=typer.colors.RED,
        )
        raise typer.Exit(code=1) from exc
    if report.clean:
        typer.secho(
            tr("cli.normatives.success.clean"),
            fg=typer.colors.GREEN,
        )
        return
    table = Table(
        title=tr("cli.normatives.success.verification_results"),
        header_style="bold",
    )
    table.add_column(tr("cli.normatives.headers.level"), style="white")
    table.add_column(tr("cli.normatives.headers.code"), style="cyan")
    table.add_column(tr("cli.normatives.headers.reference_id"), style="dim")
    table.add_column(tr("cli.normatives.headers.message"), style="white")
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
