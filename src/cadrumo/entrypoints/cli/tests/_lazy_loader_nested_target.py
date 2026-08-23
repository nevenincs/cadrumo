"""Real nested import target used by the lazy-node kernel tests."""

from __future__ import annotations

import typer

from .._app_execution_policies import METADATA
from .._command_policy import command_execution_policy
from .._command_suggestions import CadrumoTyperGroup

app = typer.Typer(name="nested", cls=CadrumoTyperGroup)


@app.callback()
@command_execution_policy(METADATA)
def nested_callback() -> None:
    """Keep the fixture materialized as a command group."""


@app.command("run")
@command_execution_policy(METADATA)
def run() -> None:
    """Provide a leaf below a second lazy boundary."""


__all__ = ["app", "nested_callback", "run"]
