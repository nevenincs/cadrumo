"""``aeat sync resolve-divergence`` — approve or reject a PENDING record."""

from __future__ import annotations

from enum import StrEnum

import typer
from rich.console import Console

from aeat.cli._observability import cli_run_context
from aeat.config import load_settings
from aeat.sync import (
    DivergenceRepositoryError,
    JsonFileDivergenceRepository,
    ResolutionState,
)

_CONSOLE = Console()


class ResolutionAction(StrEnum):
    """Operator-facing resolution action for a divergence record."""

    APPROVE = "approve"
    REJECT = "reject"


_ACTION_TO_STATE: dict[ResolutionAction, ResolutionState] = {
    ResolutionAction.APPROVE: ResolutionState.HUMAN_APPROVED,
    ResolutionAction.REJECT: ResolutionState.REJECTED,
}


def resolve_divergence(
    record_id: str = typer.Argument(..., help="The divergence record id."),
    action: ResolutionAction = typer.Option(
        ...,
        "--action",
        help="Resolution action: approve or reject.",
    ),
    notes: str | None = typer.Option(
        None,
        "--notes",
        help="Optional operator notes describing the resolution.",
    ),
) -> None:
    """Transition a divergence record to HUMAN_APPROVED or REJECTED."""
    arguments = {"record_id": record_id, "action": action, "notes": notes}
    with cli_run_context(entrypoint="aeat sync resolve-divergence", arguments=arguments):
        settings = load_settings()
        repo = JsonFileDivergenceRepository(settings.aeat_sync_divergence_file_dir)
        try:
            updated = repo.update_resolution(
                record_id,
                resolution_state=_ACTION_TO_STATE[action],
                notes=notes,
            )
        except DivergenceRepositoryError as exc:
            _CONSOLE.print(f"[red]{exc}[/red]")
            raise typer.Exit(code=1) from exc
        _CONSOLE.print(f"[green]record {updated.record_id} -> {updated.resolution_state.value}[/green]")
