"""``aeat submission dry-run`` — walk the portal up to but not including submit."""

from __future__ import annotations

import asyncio

import typer
from rich.console import Console

from .._observability import cli_run_context
from ._helpers import build_engine, load_draft, resolve_draft_path

_CONSOLE = Console()


def dry_run_cmd(
    draft_ref: str = typer.Argument(..., help="Draft id or path to a persisted filing draft JSON."),
) -> None:
    """Dry-run the submission engine against ``draft_ref``."""
    arguments = {"draft_ref": draft_ref}
    with cli_run_context(
        entrypoint="aeat submission dry-run",
        arguments=arguments,
        positional=("draft_ref",),
    ):
        draft_path = resolve_draft_path(draft_ref)
        draft = load_draft(draft_path)
        engine = build_engine()
        filing = asyncio.run(engine.submit_draft(draft, dry_run=True))
        _CONSOLE.print(f"[green]dry-run OK[/green]: submission_id={filing.submission_id} status={filing.status.value}")
