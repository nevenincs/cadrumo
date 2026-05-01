"""``aeat submission preflight`` — run preflight gates without browser work."""

from __future__ import annotations

from datetime import date

import typer
from rich.console import Console

from ....adapters.outbound.aeat.export import Preflight, SubmissionPreflightError
from .._observability import cli_run_context
from ._helpers import build_engine, load_draft, resolve_draft_path

_CONSOLE = Console()


def preflight_cmd(
    draft_ref: str = typer.Argument(..., help="Draft id or path to a persisted filing draft JSON."),
) -> None:
    """Run preflight on ``draft_ref`` and print the outcome."""
    arguments = {"draft_ref": draft_ref}
    with cli_run_context(
        entrypoint="aeat submission preflight",
        arguments=arguments,
        positional=("draft_ref",),
    ):
        draft_path = resolve_draft_path(draft_ref)
        draft = load_draft(draft_path)
        engine = build_engine()
        checker = Preflight(
            deadline_checker=engine.deadline_checker,
            auth_provider=engine.auth_provider,
        )
        try:
            checker.check(draft, today=date.today())
        except SubmissionPreflightError as exc:
            _CONSOLE.print(f"[red]preflight FAILED:[/red] {exc}")
            raise typer.Exit(code=1) from exc
        _CONSOLE.print(f"[green]preflight OK[/green] for draft {draft.draft_id} ({draft.modelo} {draft.period})")
