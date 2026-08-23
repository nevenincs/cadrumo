"""Real import target used by the lazy-node kernel tests."""

from __future__ import annotations

import typer

from .._app_execution_policies import METADATA
from .._command_policy import command_execution_policy
from .._command_suggestions import CadrumoTyperGroup

app = typer.Typer(name="s09-fixture-parent", cls=CadrumoTyperGroup, invoke_without_command=True)


@app.callback()
@command_execution_policy(METADATA)
def target_callback() -> None:
    """Own the imported group's identity and policy."""


@app.command("show")
@command_execution_policy(METADATA)
def show() -> None:
    """Provide one eagerly registered child for identity checks."""


__all__ = ["app", "show", "target_callback"]
