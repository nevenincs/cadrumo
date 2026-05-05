"""Module-local CLI surface for inbound sanitizer inspection."""

from __future__ import annotations

import typer

from .._i18n import tr

app = typer.Typer(
    name="sanitize",
    no_args_is_help=True,
    help=tr("cli.sanitize.app_help"),
)


@app.command(name="status", help=tr("cli.sanitize.status_help"))
def status() -> None:
    """Print a minimal sanitizer availability marker."""
    typer.echo(f"sanitizer\t{tr('cli.sanitize.labels.available')}")


__all__ = ["app"]
