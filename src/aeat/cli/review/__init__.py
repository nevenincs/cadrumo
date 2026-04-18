"""`aeat review` command group — pipeline-decision review surfaces (#237/#232/#204)."""

from __future__ import annotations

import typer

from .history import history_cmd

app = typer.Typer(
    name="review",
    no_args_is_help=True,
    help="Pipeline decision review surfaces (#237/#232/#204).",
)

app.command(
    name="history",
    help="Show the classification history chain for one transaction (#237).",
)(history_cmd)


__all__ = ["app"]
