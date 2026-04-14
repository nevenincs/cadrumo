"""``aeat run replay`` — deterministic dry-run replay of a recorded run."""

from __future__ import annotations

import typer
from rich.console import Console

from aeat.observability import (
    AeatCorpusDriftError,
    AeatObservabilityError,
    replay_run,
)

_CONSOLE = Console()


def replay_cmd(
    run_id: str = typer.Argument(..., help="The run identifier to replay."),
    dry_run: bool = typer.Option(
        True,
        "--dry-run/--no-dry-run",
        help="Dry-run replay (default). --no-dry-run is rejected explicitly.",
    ),
) -> None:
    """Replay a persisted run after recomputing the corpus fingerprint.

    Replay refuses on corpus drift via :class:`AeatCorpusDriftError`
    and rejects ``--no-dry-run`` because live replay is out of scope
    (#99).
    """
    try:
        trace = replay_run(run_id, dry_run=dry_run)
    except AeatCorpusDriftError as exc:
        _CONSOLE.print(f"[red]corpus drift:[/red] {exc} (recorded={exc.recorded[:12]}… observed={exc.observed[:12]}…)")
        raise typer.Exit(code=2) from exc
    except AeatObservabilityError as exc:
        _CONSOLE.print(f"[red]replay refused:[/red] {exc}")
        raise typer.Exit(code=2) from exc
    _CONSOLE.print(f"[green]replay OK[/green]: run_id={trace.run_id} entrypoint={trace.entrypoint}")
