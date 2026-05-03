"""Module-local CLI surface for inbound sanitizer inspection."""

from __future__ import annotations

import typer

app = typer.Typer(
    name="sanitize",
    no_args_is_help=True,
    help="Inspect inbound sanitizer state.",
)


@app.command(name="status", help="Show sanitizer availability.")
def status() -> None:
    """Print a minimal sanitizer availability marker."""
    typer.echo("sanitizer\tavailable")


__all__ = ["app"]
