"""``aeat deadlines explain`` - print the applies-because rationale for one modelo."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from aeat.cli.deadlines._helpers import load_profile, resolve_profile_path
from aeat.deadlines import explain

_CONSOLE = Console()


def explain_modelo(
    modelo: str = typer.Argument(..., help="The modelo string identifier (e.g. '303')."),
    profile: Path | None = typer.Option(
        None,
        "--profile",
        help="Path to a JSON AutonomoProfile (defaults to AEAT_DEFAULT_PROFILE_PATH).",
    ),
) -> None:
    """Print the human-readable rule that determines whether ``modelo`` applies."""
    profile_path = resolve_profile_path(profile)
    loaded_profile = load_profile(profile_path)
    rationale = explain(loaded_profile, modelo)
    _CONSOLE.print(f"[bold cyan]{modelo}[/bold cyan]: {rationale}")
