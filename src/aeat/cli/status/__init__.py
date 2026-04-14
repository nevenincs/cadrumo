"""``aeat status`` sub-app — live AEAT status reader CLI (#43).

Wires one subcommand per status surface under ``aeat status``. Every
command is marked ``hidden=True`` until the cert-auth backend (#8)
lands: without a concrete :class:`aeat.status.CertificateBackend`
implementation the CLI cannot open an authenticated AEAT session
and will error out cleanly with exit code 2. Programmatic use of
:class:`aeat.status.StatusReader` is unaffected.

When the rendering path is wired (in a #43 follow-up after #8
merges), :mod:`aeat.cli.status._render` will host the pretty-table
and JSON emitters. v1 keeps the CLI deliberately thin: parse
flags, validate them, bail uniformly.
"""

from __future__ import annotations

from datetime import date

import typer
from rich.console import Console

from aeat.cli._observability import cli_run_context
from aeat.logging import get_logger

logger = get_logger(__name__)

app = typer.Typer(
    name="status",
    no_args_is_help=True,
    help=(
        "Live AEAT status reader (#43): expedientes, notificaciones, "
        "devoluciones, borrador, datos fiscales, calendario."
    ),
)

_CONSOLE = Console()

_CERT_BACKEND_MISSING_MSG = (
    "aeat status CLI requires the cert-auth backend (#8) and a live "
    "Playwright runtime; run the reader programmatically in the meantime."
)


def _bail_cert_missing() -> None:
    """Uniform exit for every hidden status subcommand until #8 lands."""
    _CONSOLE.print(f"[red]{_CERT_BACKEND_MISSING_MSG}[/red]")
    raise typer.Exit(code=2)


def _parse_since(raw: str | None) -> date | None:
    """Parse an optional ``--since`` ISO date, surfacing errors cleanly."""
    if raw is None:
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError as exc:
        raise typer.BadParameter(f"--since must be YYYY-MM-DD, got {raw!r}") from exc


@app.command("expedientes", help="List 'Mis expedientes' rows.", hidden=True)
def expedientes(
    since: str | None = typer.Option(
        None,
        "--since",
        help="Filter by presented_at >= YYYY-MM-DD.",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Emit JSON instead of a pretty table.",
    ),
) -> None:
    """Fetch and display the user's expediente history.

    Hidden until #8 wires the concrete cert backend; programmatic
    use of :class:`aeat.status.StatusReader` works today.
    """
    # Validate flags eagerly so the operator gets a clean error
    # even before the cert-backend bail-out.
    _parse_since(since)
    _ = json_output
    with cli_run_context(
        entrypoint="aeat status expedientes",
        arguments={"since": since, "json": json_output},
    ):
        _bail_cert_missing()


@app.command("notificaciones", help="List 'Mis notificaciones' rows.", hidden=True)
def notificaciones(
    since: str | None = typer.Option(None, "--since"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Stub: not yet implemented in v1."""
    _parse_since(since)
    _ = json_output
    with cli_run_context(
        entrypoint="aeat status notificaciones",
        arguments={"since": since, "json": json_output},
    ):
        _bail_cert_missing()


@app.command("devoluciones", help="List 'Mis devoluciones' rows.", hidden=True)
def devoluciones(
    year: int | None = typer.Option(None, "--year"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Stub: not yet implemented in v1."""
    with cli_run_context(
        entrypoint="aeat status devoluciones",
        arguments={"year": year, "json": json_output},
    ):
        _bail_cert_missing()


@app.command("borrador", help="Show the IRPF draft state.", hidden=True)
def borrador(
    year: int = typer.Option(..., "--year"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Stub: not yet implemented in v1."""
    with cli_run_context(
        entrypoint="aeat status borrador",
        arguments={"year": year, "json": json_output},
    ):
        _bail_cert_missing()


@app.command("datos-fiscales", help="Show third-party tax data.", hidden=True)
def datos_fiscales(
    year: int = typer.Option(..., "--year"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Stub: not yet implemented in v1."""
    with cli_run_context(
        entrypoint="aeat status datos-fiscales",
        arguments={"year": year, "json": json_output},
    ):
        _bail_cert_missing()


@app.command("calendario", help="Show the personalised filing calendar.", hidden=True)
def calendario(
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Stub: not yet implemented in v1."""
    with cli_run_context(
        entrypoint="aeat status calendario",
        arguments={"json": json_output},
    ):
        _bail_cert_missing()


__all__ = ["app"]
