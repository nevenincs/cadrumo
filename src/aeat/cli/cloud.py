"""``aeat cloud`` sub-app skeleton — real verbs land in Phase 7."""

from __future__ import annotations

import typer

app = typer.Typer(name="cloud", no_args_is_help=True, help="GCP product helpers.")


@app.callback()
def _callback() -> None:
    """Cloud sub-app entry point. Sub-commands are added in Phase 7."""


@app.command(name="placeholder", hidden=True)
def _placeholder() -> None:
    """Reserve the sub-app surface so the skeleton renders in --help."""
    typer.secho("cloud subcommands land in Phase 7", fg=typer.colors.YELLOW)
    raise typer.Exit(code=1)
