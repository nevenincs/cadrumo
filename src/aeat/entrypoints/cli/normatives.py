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
    help="Spanish tax normatives corpus helpers.",
)

_console = Console()
"""Shared :class:`rich.console.Console` for tabular output."""


@app.command(name="list", help="List every normative in the corpus, optionally filtered by tag.")
def list_normatives(
    tag: str | None = typer.Option(None, "--tag", "-t", help="Filter by tag, e.g. 'irpf'."),
) -> None:
    """Render the normative catalogue as a :class:`rich.table.Table`.

    Args:
        tag: Optional tag filter (e.g. ``"irpf"``); only normatives
            carrying ``tag`` in their tag set are listed.
    """
    catalogue = load_catalogue()
    table = Table(title="aeat normatives", header_style="bold")
    table.add_column(tr("cli.normatives.t_708509"), style="cyan")
    table.add_column(tr("cli.normatives.t_484866"), style="white")
    table.add_column(tr("cli.normatives.t_532988"), style="white")
    table.add_column(tr("cli.normatives.t_033361"), style="white")
    table.add_column(tr("cli.normatives.t_849756"), justify="right", style="white")
    table.add_column(tr("cli.normatives.t_232960"), style="dim")
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
    typer.echo(tr("cli.normatives.t_360736"))


@app.command(name="show", help="Show a single normative's metadata and article index.")
def show(
    ref_id: str = typer.Argument(..., help="Stable id, e.g. 'ley-35-2006'."),
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
    typer.echo(f"id: {reference.id}")
    typer.echo(f"{tr('cli.normatives.t_329493')}: {reference.kind.value}")
    typer.echo(f"{tr('cli.normatives.t_896602')}: {reference.number}")
    typer.echo(f"{tr('cli.normatives.t_528486')}: {title_text}")
    typer.echo(f"{tr('cli.normatives.t_032146')}: {reference.published_at.isoformat()}")
    typer.echo(f"boe_id: {reference.boe_id}")
    typer.echo(f"boe_url: {reference.boe_url}")
    typer.echo(f"{tr('cli.normatives.t_888840')}: {', '.join(reference.tags)}")
    typer.echo(f"{tr('cli.normatives.t_628053')}: {reference.reviewed_by}")
    typer.echo(f"{tr('cli.normatives.t_596645')}: {reference.last_reviewed_at.isoformat()}")
    if not reference.articulos:
        typer.echo(tr("cli.normatives.t_506342"))
        return
    table = Table(
        title=f"{reference.id} {tr('cli.normatives.t_876125')}",
        header_style="bold",
    )
    table.add_column(tr("cli.normatives.t_956665"), style="cyan")
    table.add_column(tr("cli.normatives.t_908462"), style="white")
    table.add_column(tr("cli.normatives.t_300148"), style="dim")
    for articulo in reference.articulos:
        articulo_title = articulo.titulo if articulo.titulo else ""
        table.add_row(
            articulo.numero,
            articulo_title,
            cite(reference, articulo),
        )
    _console.print(table)


@app.command(name="verify", help="Validate every normative against the schema and cross-references.")
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
            tr("cli.normatives.t_688044"),
            fg=typer.colors.RED,
        )
        raise typer.Exit(code=1) from exc
    if report.clean:
        typer.secho(
            tr("cli.normatives.t_838663"),
            fg=typer.colors.GREEN,
        )
        return
    table = Table(
        title=tr("cli.normatives.t_757078"),
        header_style="bold",
    )
    table.add_column(tr("cli.normatives.t_668112"), style="white")
    table.add_column(tr("cli.normatives.t_253101"), style="cyan")
    table.add_column(tr("cli.normatives.t_311779"), style="dim")
    table.add_column(tr("cli.normatives.t_756958"), style="white")
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
