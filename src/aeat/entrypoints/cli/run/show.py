"""``aeat run show`` command implementation.

Pretty-prints a persisted :class:`aeat.core.observability.RunTrace`
and incrementally streams its event log via :func:`iter_events` so a
long-running trace's log is rendered without ever being fully held in
memory.
"""

from __future__ import annotations

import typer
from rich.console import Console
from rich.json import JSON

from ....core.observability import (
    AeatObservabilityError,
    iter_events,
    load_trace,
)

_CONSOLE = Console()


def show_cmd(
    run_id: str = typer.Argument(..., help="The run identifier to load."),
) -> None:
    """Pretty-print the :class:`RunTrace` and stream its event log.

    Streams events via :func:`iter_events` so a long-running run's log
    is rendered incrementally and never materialised in memory.

    Args:
        run_id: Identifier of the persisted run trace to load.

    Raises:
        typer.Exit: Code ``1`` when the trace cannot be loaded or the
            event log is corrupt mid-stream.
    """
    try:
        trace = load_trace(run_id)
    except AeatObservabilityError as exc:
        _CONSOLE.print(f"[red]not found:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    _CONSOLE.print(JSON(trace.model_dump_json(indent=2)))
    count = 0
    try:
        for event in iter_events(run_id):
            _CONSOLE.print(JSON(event.model_dump_json()))
            count += 1
    except AeatObservabilityError as exc:
        # Mid-stream validation failure: surface it cleanly with the
        # count of events rendered so far.
        _CONSOLE.print(f"[red]events.jsonl corrupt after {count} record(s):[/red] {exc}")
        raise typer.Exit(code=1) from exc
    _CONSOLE.print(f"[bold]events ({count})[/bold]")
