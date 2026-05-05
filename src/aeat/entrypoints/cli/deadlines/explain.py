"""``aeat deadlines explain`` — print the applies-because rationale for one modelo.

Loads the current :class:`aeat.domain.deadlines.AutonomoProfile` and
asks :func:`aeat.domain.deadlines.explain` for the human-readable rule
that determines whether the named modelo applies.
"""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from ....domain.deadlines import explain
from .._i18n import tr
from ._helpers import load_profile, resolve_profile_path

_CONSOLE = Console()


def explain_modelo(
    modelo: str = typer.Argument(..., help=tr("cli.deadlines.explain.modelo_help")),
    profile: Path | None = typer.Option(
        None,
        "--profile",
        help=tr("cli.deadlines.explain.profile_help"),
    ),
) -> None:
    """Print the human-readable rule that determines whether ``modelo`` applies."""
    profile_path = resolve_profile_path(profile)
    loaded_profile = load_profile(profile_path)
    rationale = explain(loaded_profile, modelo)
    _CONSOLE.print(f"[bold cyan]{modelo}[/bold cyan]: {rationale}")
