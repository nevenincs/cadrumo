"""``aeat submission show`` — pretty-print a persisted SubmittedFiling.

Read-only inspection surface backed by
:meth:`aeat.adapters.outbound.aeat.export.SubmissionEngine.load_submission`.
"""

from __future__ import annotations

import typer
from rich.console import Console
from rich.json import JSON

from ....adapters.outbound.aeat.export import SubmissionError
from .._observability import cli_run_context
from ._helpers import build_engine

_CONSOLE = Console()


def show_cmd(
    submission_id: str = typer.Argument(..., help="The submission id to load."),
) -> None:
    """Load and pretty-print a persisted :class:`SubmittedFiling`.

    Args:
        submission_id: The submission id to load.

    Raises:
        typer.Exit: With code ``1`` when no record exists for the given
            id.
    """
    arguments = {"submission_id": submission_id}
    with cli_run_context(
        entrypoint="aeat submission show",
        arguments=arguments,
        positional=("submission_id",),
    ):
        engine = build_engine()
        try:
            filing = engine.load_submission(submission_id)
        except SubmissionError as exc:
            _CONSOLE.print(f"[red]not found:[/red] {exc}")
            raise typer.Exit(code=1) from exc
        _CONSOLE.print(JSON(filing.model_dump_json(indent=2)))
