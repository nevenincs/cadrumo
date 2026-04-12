"""``aeat docs`` sub-app skeleton — real verbs land in Phase 6."""

from __future__ import annotations

import typer

app = typer.Typer(name="docs", no_args_is_help=True, help="Google Docs helpers.")


@app.callback()
def _callback() -> None:
    """Docs sub-app entry point. Sub-commands are added in Phase 6."""


@app.command(name="placeholder", hidden=True)
def _placeholder() -> None:
    """Reserve the sub-app surface so the skeleton renders in --help."""
    typer.secho("docs subcommands land in Phase 6", fg=typer.colors.YELLOW)
    raise typer.Exit(code=1)
