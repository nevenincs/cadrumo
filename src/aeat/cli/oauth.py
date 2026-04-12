"""``aeat oauth-client`` sub-app skeleton — real verbs land in Phase 8."""

from __future__ import annotations

import typer

app = typer.Typer(name="oauth-client", no_args_is_help=True, help="OAuth 2.0 Desktop client provisioning.")


@app.callback()
def _callback() -> None:
    """OAuth client sub-app entry point. Sub-commands are added in Phase 8."""


@app.command(name="placeholder", hidden=True)
def _placeholder() -> None:
    """Reserve the sub-app surface so the skeleton renders in --help."""
    typer.secho("oauth-client subcommands land in Phase 8", fg=typer.colors.YELLOW)
    raise typer.Exit(code=1)
