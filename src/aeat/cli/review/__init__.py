"""``aeat review`` sub-app — pipeline-decision review surfaces.

Wires the review subcommands per the feature ADRs:

- ``aeat review queue [--kind K]... [--state pending|all] [--modelo M]
  [--format table|json]`` — unified pending-review dashboard
  (#232, [[2026-04-18-unified-review-queue-adr]]).
- ``aeat review history <transaction-id>`` — classification history
  chain for one transaction (#237).
- ``aeat review approve <draft>`` — record an approval for one
  persisted draft (#230).
- ``aeat review unapprove <draft>`` — rescind a stored approval (#230).
- ``aeat review show <draft>`` — show the current review state for
  one draft including any staleness reasons (#230).
- ``aeat review stale`` — list every persisted draft whose approval
  is currently stale (#230).

These commands delegate every domain decision to :mod:`aeat.review`,
:mod:`aeat.financial.transactions`, or :mod:`aeat.filing`; this
module is pure CLI glue.
"""

from __future__ import annotations

import getpass
from pathlib import Path

import typer
from pydantic import ValidationError
from rich.console import Console
from rich.table import Table

from ...config import load_settings
from ...filing import (
    FilingDraft,
    FilingDraftError,
    FilingDraftStatus,
    approval_stale_reasons,
    approve_draft,
    describe_stale_reason,
    refresh_review_status,
    unapprove_draft,
)
from ...filing.runtime import build_runtime_schema_provider
from .history import history_cmd
from .queue import queue_cmd

app = typer.Typer(
    name="review",
    no_args_is_help=True,
    help="Review surfaces: queue (#232), history (#237), draft approve/unapprove/show/stale (#230).",
)

_CONSOLE = Console()


def _drafts_dir() -> Path:
    path = load_settings().aeat_drafts_dir.resolve()
    path.mkdir(parents=True, exist_ok=True)
    return path


def _load_review_draft(path: Path) -> FilingDraft:
    if not path.exists():
        raise typer.BadParameter(f"draft file not found: {path}")
    try:
        draft = FilingDraft.model_validate_json(path.read_text(encoding="utf-8"))
    except (FilingDraftError, ValidationError) as exc:
        raise typer.BadParameter(f"invalid draft in {path}: {exc}") from exc
    refreshed = refresh_review_status(
        draft,
        schema_provider=build_runtime_schema_provider(),
    )
    if refreshed != draft:
        _save_draft(path, refreshed)
    return refreshed


def _save_draft(path: Path, draft: FilingDraft) -> None:
    path.write_text(draft.model_dump_json(indent=2), encoding="utf-8")


def _resolve_approver(approved_by: str | None) -> str:
    if approved_by is not None and approved_by.strip():
        return approved_by.strip()
    username = getpass.getuser().strip()
    if username:
        return username
    return "unknown"


def _status_label(draft: FilingDraft) -> str:
    if draft.approved_at is None:
        return "UNAPPROVED"
    return draft.status.value


@app.command("approve")
def approve_cmd(
    draft_path: Path = typer.Argument(..., help="Path to a persisted draft JSON file."),
    approved_by: str | None = typer.Option(None, "--approved-by", help="Signer recorded on the approval."),
    yes: bool = typer.Option(False, "--yes", help="Skip the interactive confirmation prompt."),
) -> None:
    """Approve one persisted draft."""

    draft = _load_review_draft(draft_path)
    if not yes and not typer.confirm(f"Approve draft {draft.draft_id}?"):
        raise typer.Exit(code=1)
    try:
        approved = approve_draft(
            draft,
            approved_by=_resolve_approver(approved_by),
            schema_provider=build_runtime_schema_provider(),
        )
    except FilingDraftError as exc:
        _CONSOLE.print(f"[red]refusing:[/red] {exc}")
        raise typer.Exit(code=1) from exc
    assert approved.approved_at is not None
    _save_draft(draft_path, approved)
    _CONSOLE.print(
        f"[green]approved[/green] draft {approved.draft_id} "
        f"by {approved.approved_by} at {approved.approved_at.isoformat()}"
    )


@app.command("unapprove")
def unapprove_cmd(
    draft_path: Path = typer.Argument(..., help="Path to a persisted draft JSON file."),
    yes: bool = typer.Option(False, "--yes", help="Skip the interactive confirmation prompt."),
) -> None:
    """Remove the stored approval record from one draft."""

    draft = _load_review_draft(draft_path)
    if draft.approved_at is None:
        _CONSOLE.print(f"[yellow]not approved[/yellow] draft {draft.draft_id}")
        return
    if not yes and not typer.confirm(f"Remove approval from draft {draft.draft_id}?"):
        raise typer.Exit(code=1)
    unapproved = unapprove_draft(draft)
    _save_draft(draft_path, unapproved)
    _CONSOLE.print(f"[green]unapproved[/green] draft {unapproved.draft_id}")


@app.command("show")
def show_cmd(
    draft_path: Path = typer.Argument(..., help="Path to a persisted draft JSON file."),
) -> None:
    """Show the current review state for one draft."""

    draft = _load_review_draft(draft_path)
    reasons = approval_stale_reasons(
        draft,
        schema_provider=build_runtime_schema_provider(),
    )
    table = Table(title=f"Review {draft.draft_id}", show_header=False)
    table.add_row("modelo", draft.modelo)
    table.add_row("period", draft.period)
    table.add_row("status", _status_label(draft))
    table.add_row("draft_status", draft.status.value)
    table.add_row("path", str(draft_path))
    if draft.approved_at is not None:
        table.add_row("approved_at", draft.approved_at.isoformat())
    if draft.approved_by is not None:
        table.add_row("approved_by", draft.approved_by)
    if draft.review_checksum is not None:
        table.add_row("review_checksum", draft.review_checksum)
    if reasons:
        table.add_row("stale_reason", ", ".join(describe_stale_reason(reason) for reason in reasons))
    _CONSOLE.print(table)


@app.command("stale")
def stale_cmd() -> None:
    """List every persisted draft whose approval is stale."""

    drafts_dir = _drafts_dir()
    table = Table(title="Stale draft approvals")
    table.add_column("draft_id")
    table.add_column("modelo")
    table.add_column("period")
    table.add_column("reason", no_wrap=True)
    table.add_column("path")

    stale_count = 0
    for path in sorted(drafts_dir.glob("*.json")):
        try:
            draft = _load_review_draft(path)
        except typer.BadParameter:
            continue
        reasons = approval_stale_reasons(
            draft,
            schema_provider=build_runtime_schema_provider(),
        )
        if draft.status is not FilingDraftStatus.APPROVAL_STALE or not reasons:
            continue
        stale_count += 1
        table.add_row(
            draft.draft_id,
            draft.modelo,
            draft.period,
            ", ".join(describe_stale_reason(reason) for reason in reasons),
            str(path),
        )
    if stale_count == 0:
        _CONSOLE.print("No stale draft approvals found.")
        return
    _CONSOLE.print(table)


app.command(
    name="queue",
    help="List every pending review item across the pipeline in one table.",
)(queue_cmd)
app.command(
    name="history",
    help="Show the classification history chain for one transaction (#237).",
)(history_cmd)


__all__ = ["app"]
