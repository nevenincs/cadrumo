"""``aeat sync list-divergences`` -- enumerate persisted divergence records.

Loads :class:`aeat.application.sync.DivergenceRecord` instances from
:class:`aeat.application.sync.JsonFileDivergenceRepository` and
renders them as a Rich table, optionally filtered by
:class:`aeat.application.sync.ResolutionState`.
"""

from __future__ import annotations

import typer
from rich.console import Console
from rich.table import Table

from ....application.sync import JsonFileDivergenceRepository, ResolutionState
from ....core.config import load_settings
from .._observability import cli_run_context

_CONSOLE = Console()


def list_divergences(
    state: ResolutionState | None = typer.Option(
        None,
        "--state",
        help="Filter by resolution state (pending, auto_healed, human_approved, rejected).",
    ),
) -> None:
    """List every persisted divergence record, optionally filtered by state.

    Args:
        state: Optional :class:`aeat.application.sync.ResolutionState`
            to restrict the listing. When ``None`` every record is
            shown.
    """
    arguments = {"state": state}
    with cli_run_context(entrypoint="aeat sync list-divergences", arguments=arguments):
        settings = load_settings()
        repo = JsonFileDivergenceRepository(settings.aeat_sync_divergence_file_dir)
        records = repo.list()
        if state is not None:
            records = tuple(r for r in records if r.resolution_state == state)

        table = Table(title="divergence records", header_style="bold")
        table.add_column("id", style="cyan")
        table.add_column("modelo")
        table.add_column("classification")
        table.add_column("kind")
        table.add_column("state")
        for record in records:
            table.add_row(
                record.record_id,
                str(record.modelo) if record.modelo is not None else "-",
                record.classification.value,
                record.payload.kind.value,
                record.resolution_state.value,
            )
        _CONSOLE.print(table)
        _CONSOLE.print(f"[dim]{len(records)} record(s)[/dim]")
