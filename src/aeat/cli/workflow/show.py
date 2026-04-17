"""``aeat workflow show`` — pretty-print a persisted :class:`WorkflowResult`."""

from __future__ import annotations

import typer
from rich.console import Console
from rich.json import JSON

from ...config import load_settings
from ...workflow import WorkflowError, load_run

_CONSOLE = Console()


def show_cmd(
    run_id: str = typer.Argument(..., help="The workflow run id to load."),
    as_json: bool = typer.Option(
        False,
        "--json",
        help="Emit the raw JSON record on stdout instead of the rich view.",
    ),
) -> None:
    """Load and pretty-print a persisted :class:`WorkflowResult`.

    Args:
        run_id: Identifier of the run to load. Matches the file stem
            under ``AEAT_WORKFLOW_RUNS_DIR``.
        as_json: When ``True``, emit compact JSON to stdout.
    """
    settings = load_settings()
    try:
        result = load_run(run_id, runs_dir=settings.aeat_workflow_runs_dir)
    except WorkflowError as exc:
        _CONSOLE.print(f"[red]not found:[/red] {exc}")
        raise typer.Exit(code=1) from exc
    payload = result.model_dump_json(indent=2)
    if as_json:
        typer.echo(payload)
    else:
        _CONSOLE.print(JSON(payload))
