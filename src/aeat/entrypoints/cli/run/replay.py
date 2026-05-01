"""``aeat run replay`` command implementation.

Re-executes a recorded run after recomputing the corpus fingerprint
and refuses on any drift via
:exc:`aeat.core.observability.AeatCorpusDriftError`.
"""

from __future__ import annotations

import typer
from rich.console import Console

from ....core.observability import (
    AeatCorpusDriftError,
    AeatObservabilityError,
    replay_run,
)

_CONSOLE = Console()


def _invoke_root_cli(argv: list[str]) -> None:
    """Re-enter the root CLI with ``argv`` for replay re-execution."""
    from .. import app

    app(argv, standalone_mode=False)


def replay_cmd(
    run_id: str = typer.Argument(..., help="The run identifier to replay."),
) -> None:
    """Replay a persisted run after recomputing the corpus fingerprint.

    Args:
        run_id: Identifier of the run to re-execute.

    Raises:
        typer.Exit: Code ``2`` on corpus drift
            (:exc:`AeatCorpusDriftError`) or any other observability
            failure (:exc:`AeatObservabilityError`).
    """
    try:
        trace = replay_run(run_id, invoke=_invoke_root_cli)
    except AeatCorpusDriftError as exc:
        _CONSOLE.print(
            f"[red]corpus drift:[/red] {exc} (recorded={exc.recorded[:12]}... observed={exc.observed[:12]}...)"
        )
        raise typer.Exit(code=2) from exc
    except AeatObservabilityError as exc:
        _CONSOLE.print(f"[red]replay refused:[/red] {exc}")
        raise typer.Exit(code=2) from exc
    _CONSOLE.print(f"[green]replay OK[/green]: run_id={trace.run_id} entrypoint={trace.entrypoint}")
