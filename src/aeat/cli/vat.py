"""``aeat vat`` sub-app — Spanish VAT (IVA) taxonomy + rules CLI."""

from __future__ import annotations

import typer
from rich.console import Console
from rich.table import Table

from ..financial.vat import (
    VAT_CATALOGUE_2025,
    VAT_RATE_TABLE,
    EUMemberState,
    VATCategory,
    VatCategoryNotFoundError,
    VatError,
    cite,
    verify_catalogue,
)

app = typer.Typer(
    name="vat",
    no_args_is_help=True,
    help="Spanish VAT (IVA) taxonomy + rules (#85).",
)

categories_app = typer.Typer(
    name="categories",
    no_args_is_help=True,
    help="VAT category commands.",
)
rates_app = typer.Typer(
    name="rates",
    no_args_is_help=True,
    help="VAT rate commands.",
)
app.add_typer(categories_app, name="categories")
app.add_typer(rates_app, name="rates")

_console = Console()


def _parse_category(raw: str) -> VATCategory:
    """Parse ``raw`` into a :class:`VATCategory` or raise ``Exit``."""
    try:
        return VATCategory(raw)
    except ValueError as exc:
        typer.secho(
            f"unknown VAT category {raw!r}; run 'aeat vat categories list'",
            fg=typer.colors.RED,
        )
        raise typer.Exit(code=1) from exc


def _parse_member_state(raw: str) -> EUMemberState:
    """Parse ``raw`` into an :class:`EUMemberState` or raise ``Exit``."""
    try:
        return EUMemberState(raw.lower())
    except ValueError as exc:
        typer.secho(
            f"unknown EU member state {raw!r}; expected an ISO 3166-1 alpha-2 code",
            fg=typer.colors.RED,
        )
        raise typer.Exit(code=1) from exc


@categories_app.command(name="list", help="List every VAT category with its Spanish label.")
def categories_list() -> None:
    """Render the VAT catalogue as a rich table keyed by category."""
    table = Table(title="aeat vat categories", header_style="bold")
    table.add_column("category", style="cyan")
    table.add_column("label (es)", style="white")
    table.add_column("modelos", style="dim")
    table.add_column("rc", justify="center", style="white")
    for regulation in VAT_CATALOGUE_2025:
        table.add_row(
            regulation.category.value,
            regulation.label.get("es", ""),
            ", ".join(regulation.declares_in_modelos),
            "y" if regulation.requires_reverse_charge else "n",
        )
    _console.print(table)
    typer.echo(f"{len(VAT_CATALOGUE_2025)} category(ies)")


@rates_app.command(name="list", help="List VAT rates, optionally filtered by EU member state.")
def rates_list(
    member_state: str | None = typer.Option(
        None,
        "--member-state",
        "-m",
        help="Filter by ISO 3166-1 alpha-2 code, e.g. 'es'.",
    ),
) -> None:
    """Render the VAT rate table as a rich table."""
    filter_state: EUMemberState | None = None
    if member_state is not None:
        filter_state = _parse_member_state(member_state)
    table = Table(title="aeat vat rates", header_style="bold")
    table.add_column("member_state", style="cyan")
    table.add_column("kind", style="white")
    table.add_column("pct", justify="right", style="white")
    table.add_column("effective_from", style="dim")
    table.add_column("reference", style="dim")
    count = 0
    for state, rates in VAT_RATE_TABLE.items():
        if filter_state is not None and state is not filter_state:
            continue
        for rate in rates:
            table.add_row(
                state.value,
                rate.kind.value,
                f"{rate.pct}",
                rate.effective_from.isoformat(),
                rate.boe_or_directive_reference,
            )
            count += 1
    _console.print(table)
    typer.echo(f"{count} rate(s)")


@app.command(name="show", help="Show the full VATRegulation for a category, with citations.")
def show(
    category: str = typer.Argument(..., help="VAT category, e.g. 'domestic_general_21'."),
) -> None:
    """Print the full metadata for a single :class:`VATRegulation`."""
    vat_category = _parse_category(category)
    regulation = VAT_CATALOGUE_2025.get(vat_category)
    if regulation is None:
        typer.secho(f"category {category!r} not in catalogue", fg=typer.colors.RED)
        raise typer.Exit(code=1)
    typer.echo(f"category: {regulation.category.value}")
    typer.echo(f"label (es): {regulation.label.get('es', '')}")
    typer.echo(f"description (es): {regulation.description.get('es', '')}")
    typer.echo(f"triggers_when (es): {regulation.triggers_when.get('es', '')}")
    typer.echo(f"iva_treatment (es): {regulation.iva_treatment.get('es', '')}")
    typer.echo(f"declares_in_modelos: {', '.join(regulation.declares_in_modelos)}")
    typer.echo(f"requires_reverse_charge: {regulation.requires_reverse_charge}")
    typer.echo(f"requires_supplier_vat_id: {regulation.requires_supplier_vat_id}")
    typer.echo(f"boe_references: {', '.join(regulation.boe_references)}")
    if regulation.manual_references:
        typer.echo(f"manual_references: {', '.join(regulation.manual_references)}")
    table = Table(title=f"{regulation.category.value} citations", header_style="bold")
    table.add_column("source", style="cyan")
    table.add_column("article", style="white")
    table.add_column("quoted_text_es", style="white")
    for citation in regulation.citations:
        table.add_row(citation.source.value, citation.article, citation.quoted_text_es)
    _console.print(table)


@app.command(name="rule", help="Detailed view of a single VAT rule with its canonical citation.")
def rule(
    category: str = typer.Argument(..., help="VAT category, e.g. 'domestic_general_21'."),
) -> None:
    """Detailed view: delegates to ``show`` and appends ``cite(category)``."""
    vat_category = _parse_category(category)
    show(category)
    try:
        canonical = cite(vat_category)
    except VatCategoryNotFoundError as exc:
        typer.secho(str(exc), fg=typer.colors.RED)
        raise typer.Exit(code=1) from exc
    typer.echo("")
    typer.echo(f"canonical citation: {canonical}")


@app.command(name="verify", help="Validate VAT_CATALOGUE_2025 against the cross-record schema.")
def verify() -> None:
    """Run :func:`verify_catalogue` and exit non-zero on errors."""
    try:
        report = verify_catalogue(VAT_CATALOGUE_2025)
    except VatError as exc:
        typer.secho(f"verify failed: {exc}", fg=typer.colors.RED)
        raise typer.Exit(code=1) from exc
    if report.clean:
        typer.secho("verify clean", fg=typer.colors.GREEN)
        return
    table = Table(title="vat verify findings", header_style="bold")
    table.add_column("level", style="white")
    table.add_column("code", style="cyan")
    table.add_column("category", style="dim")
    table.add_column("message", style="white")
    for issue in report.issues:
        colour = "red" if issue.level == "error" else "yellow"
        table.add_row(
            f"[{colour}]{issue.level}[/{colour}]",
            issue.code,
            issue.category_id or "-",
            issue.message,
        )
    _console.print(table)
    raise typer.Exit(code=1)


__all__ = ["app"]
