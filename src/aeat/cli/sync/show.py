"""``aeat sync show-divergence`` — print a single divergence record."""

from __future__ import annotations

import typer
from rich.console import Console

from ...config import load_settings
from ...sync import DivergenceRepositoryError, JsonFileDivergenceRepository

_CONSOLE = Console()


def show_divergence(
    record_id: str = typer.Argument(..., help="The divergence record id."),
) -> None:
    """Print the full JSON payload of a divergence record."""
    settings = load_settings()
    repo = JsonFileDivergenceRepository(settings.aeat_sync_divergence_file_dir)
    try:
        record = repo.load(record_id)
    except DivergenceRepositoryError as exc:
        _CONSOLE.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc
    _CONSOLE.print_json(record.model_dump_json(indent=2))
