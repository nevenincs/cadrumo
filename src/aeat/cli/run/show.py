"""``aeat run show`` — pretty-print a persisted run trace and its events."""

from __future__ import annotations

import typer
from rich.console import Console
from rich.json import JSON

from aeat.observability import (
    AeatObservabilityError,
    load_events,
    load_trace,
)

_CONSOLE = Console()


def show_cmd(
    run_id: str = typer.Argument(..., help="The run identifier to load."),
) -> None:
    """Pretty-print the :class:`RunTrace` and stream its event log."""
    try:
        trace = load_trace(run_id)
        events = load_events(run_id)
    except AeatObservabilityError as exc:
        _CONSOLE.print(f"[red]not found:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    _CONSOLE.print(JSON(trace.model_dump_json(indent=2)))
    _CONSOLE.print(f"[bold]events ({len(events)})[/bold]")
    for event in events:
        _CONSOLE.print(JSON(event.model_dump_json()))
