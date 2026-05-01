"""``aeat review`` Typer sub-app for pipeline-decision review surfaces.

Wires the review subcommands:

- ``aeat review queue`` — unified pending-review dashboard with
  ``--kind``, ``--state``, ``--modelo`` and ``--format`` filters.
- ``aeat review history <transaction-id>`` — classification history
  chain for one transaction.
- ``aeat review approve <draft>`` — record an approval for one
  persisted draft.
- ``aeat review unapprove <draft>`` — rescind a stored approval.
- ``aeat review show <draft>`` — show the current review state for one
  draft, including any staleness reasons.
- ``aeat review stale`` — list every persisted draft whose approval is
  currently stale.

These commands delegate every domain decision to
:mod:`aeat.application.review`, :mod:`aeat.domain.transactions` or
:mod:`aeat.application.filing`; this module is pure CLI glue.
"""

from __future__ import annotations

import getpass
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from ....application.filing import (
    FilingDraft,
    FilingDraftError,
    FilingDraftStatus,
    approval_stale_reasons,
    approve_draft,
    describe_stale_reason,
    refresh_review_status,
    unapprove_draft,
)
from ....application.filing.runtime import build_runtime_schema_provider
from ....core.config import load_settings
from .history import history_cmd
from .queue import queue_cmd

app = typer.Typer(
    name="review",
    no_args_is_help=True,
    help="Review surfaces: queue, history, draft approve/unapprove/show/stale.",
)

_CONSOLE = Console()


def _drafts_dir() -> Path:
    """Return the resolved drafts directory, creating it if absent."""
    path = load_settings().aeat_drafts_dir.resolve()
    path.mkdir(parents=True, exist_ok=True)
    return path


def _resolve_draft_path(draft_ref: str) -> Path:
    """Resolve a draft id (or envelope filename) to a Path on disk."""
    candidate = Path(draft_ref)
    if candidate.exists():
        return candidate
    if candidate.suffix == ".json" or candidate.parent != Path("."):
        raise typer.BadParameter(f"draft file not found: {candidate}")
    envelope_path = _drafts_dir() / f"{draft_ref}.envelope.json"
    if envelope_path.exists():
        return envelope_path
    raise typer.BadParameter(f"no persisted draft found for draft_id={draft_ref!r}")


def _load_review_draft(path: Path) -> FilingDraft:
    """Load a draft envelope through the :class:`FilingDraftRepository`.

    Refreshes the persisted review-status flags so the CLI surface
    always reflects the current state of upstream catalogues.
    """
    from ....domain.filing import FilingDraftRepository

    if not path.exists():
        raise typer.BadParameter(f"draft file not found: {path}")
    if not path.name.endswith(".envelope.json"):
        raise typer.BadParameter(
            f"unrecognised draft file: {path}; expected a <draft_id>.envelope.json file.",
        )
    repository = FilingDraftRepository(store_dir=_drafts_dir())
    draft_id = path.name[: -len(".envelope.json")]
    loaded = repository.load(draft_id)
    if loaded is None:
        raise typer.BadParameter(f"draft envelope not found: {path}")
    refreshed = refresh_review_status(
        loaded,
        schema_provider=build_runtime_schema_provider(),
    )
    if refreshed != loaded:
        _save_draft(refreshed)
    return refreshed


def _save_draft(draft: FilingDraft) -> None:
    """Persist ``draft`` through the :class:`FilingDraftRepository`.

    Writes ciphertext envelopes to disk; plaintext draft contents
    never hit the filesystem outside the encryption layer.
    """
    from ....domain.filing import FilingDraftRepository

    repository = FilingDraftRepository(store_dir=_drafts_dir())
    repository.save(draft)


def _resolve_approver(approved_by: str | None) -> str:
    """Return the explicit approver, the OS username, or ``"unknown"``."""
    if approved_by is not None and approved_by.strip():
        return approved_by.strip()
    username = getpass.getuser().strip()
    if username:
        return username
    return "unknown"


def _status_label(draft: FilingDraft) -> str:
    """Return the human-facing approval label for ``draft``."""
    if draft.approved_at is None:
        return "UNAPPROVED"
    return draft.status.value


def _render_review_next_steps(
    draft: FilingDraft,
    *,
    draft_path: Path,
    reasons: tuple[object, ...] = (),
) -> None:
    """Print the likely next operator commands for the current review state.

    Args:
        draft: The draft whose review state is being rendered.
        draft_path: Path of the draft envelope on disk.
        reasons: Tuple of stale-approval reasons gathered from
            :func:`approval_stale_reasons`; non-empty implies stale.
    """

    if draft.status is FilingDraftStatus.APPROVAL_STALE or reasons:
        _CONSOLE.print(f"Next: aeat filing show {draft_path}")
        _CONSOLE.print(f"Next: aeat review approve {draft.draft_id} --approved-by <you>")
        return
    if draft.approved_at is None:
        _CONSOLE.print(f"Next: aeat review approve {draft.draft_id} --approved-by <you>")
        return
    _CONSOLE.print(f"Next: aeat submission preflight {draft_path}")
    _CONSOLE.print(f"Next: aeat submission export {draft_path}")


@app.command("approve")
def approve_cmd(
    draft_ref: str = typer.Argument(
        ...,
        help="Draft id from `aeat filing build/list`, or a persisted draft JSON path.",
    ),
    approved_by: str | None = typer.Option(None, "--approved-by", help="Signer recorded on the approval."),
    yes: bool = typer.Option(False, "--yes", help="Skip the interactive confirmation prompt."),
) -> None:
    """Approve one persisted draft.

    Args:
        draft_ref: Draft id from ``aeat filing build/list``, or a path
            to a persisted ``<draft_id>.envelope.json`` file.
        approved_by: Optional explicit approver name; defaults to the
            current OS user.
        yes: Skip the interactive confirmation prompt when truthy.

    Raises:
        typer.Exit: When the operator declines confirmation, or when
            :func:`approve_draft` rejects the draft.
    """

    draft_path = _resolve_draft_path(draft_ref)
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
    _save_draft(approved)
    _CONSOLE.print(
        f"[green]approved[/green] draft {approved.draft_id} "
        f"by {approved.approved_by} at {approved.approved_at.isoformat()}"
    )
    _render_review_next_steps(approved, draft_path=draft_path)


@app.command("unapprove")
def unapprove_cmd(
    draft_ref: str = typer.Argument(
        ...,
        help="Draft id from `aeat filing build/list`, or a persisted draft JSON path.",
    ),
    yes: bool = typer.Option(False, "--yes", help="Skip the interactive confirmation prompt."),
) -> None:
    """Remove the stored approval record from one draft.

    Args:
        draft_ref: Draft id, or path to the persisted envelope file.
        yes: Skip the interactive confirmation prompt when truthy.
    """

    draft_path = _resolve_draft_path(draft_ref)
    draft = _load_review_draft(draft_path)
    if draft.approved_at is None:
        _CONSOLE.print(f"[yellow]not approved[/yellow] draft {draft.draft_id}")
        return
    if not yes and not typer.confirm(f"Remove approval from draft {draft.draft_id}?"):
        raise typer.Exit(code=1)
    unapproved = unapprove_draft(draft)
    _save_draft(unapproved)
    _CONSOLE.print(f"[green]unapproved[/green] draft {unapproved.draft_id}")
    _render_review_next_steps(unapproved, draft_path=draft_path)


@app.command("show")
def show_cmd(
    draft_ref: str = typer.Argument(
        ...,
        help="Draft id from `aeat filing build/list`, or a persisted draft JSON path.",
    ),
) -> None:
    """Show the current review state for one draft.

    Args:
        draft_ref: Draft id, or path to the persisted envelope file.
    """

    draft_path = _resolve_draft_path(draft_ref)
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
    _render_review_next_steps(draft, draft_path=draft_path, reasons=reasons)


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
    for path in sorted(drafts_dir.glob("*.envelope.json")):
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
    _CONSOLE.print("Next: aeat review show <draft_id>")
    _CONSOLE.print("Next: aeat review approve <draft_id> --approved-by <you>")


app.command(
    name="queue",
    help="List every pending review item across the pipeline in one table.",
)(queue_cmd)
app.command(
    name="history",
    help="Show the classification history chain for one transaction (#237).",
)(history_cmd)


__all__ = ["app"]
