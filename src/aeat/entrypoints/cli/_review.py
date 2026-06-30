from __future__ import annotations

import typer

from ...application.review import (
    ReviewError,
    ReviewQueueReport,
    ReviewQueueRow,
    ReviewState,
    project_review_item,
    project_review_queue,
)
from ...core.errors import resolve_error_message
from ...core.i18n import tr
from ._common import _bad, _emit_envelope
from ._review_payloads import ReviewQueueResult, ReviewQueueRowPayload, ReviewViewResult


def _row_to_payload(row: ReviewQueueRow) -> ReviewQueueRowPayload:
    """Project the application-side ``ReviewQueueRow`` onto the typed CLI payload.

    Keeps the CLI JSON contract pinned to the registered
    :class:`~aeat.entrypoints.cli._review_payloads.ReviewQueueRowPayload`
    shape; downstream JSON consumers
    rely on the registry rather than the application-side record.
    """
    return ReviewQueueRowPayload(
        item_id=row.item_id,
        kind=row.kind,
        source_kind=row.source_kind,
        affected_object_id=row.affected_object_id,
        bucket_id=row.bucket_id,
        modelo=row.modelo,
        period=row.period,
        severity=row.severity.value,
        state=row.state.value,
        blocking=row.blocking,
        reason=row.reason,
        current_owner_surface=row.current_owner_surface,
        canonical_next_command=row.canonical_next_command,
        since=row.since.isoformat(),
        summary=row.summary,
        legal_refs=tuple(row.legal_refs),
    )


app = typer.Typer(
    name="review",
    help=tr("cli.review.app_help"),
    no_args_is_help=True,
)


@app.command("queue", help=tr("cli.review.queue.help"))
def review_queue(
    ctx: typer.Context,
    kinds: list[str] = typer.Option([], "--kind", help=tr("cli.review.queue.kind_help")),
    source_kinds: list[str] = typer.Option([], "--source-kind", help=tr("cli.review.queue.source_kind_help")),
    state: str = typer.Option(ReviewState.PENDING.value, "--state", help=tr("cli.review.queue.state_help")),
    modelo: str | None = typer.Option(None, "--modelo", help=tr("cli.review.queue.modelo_help")),
    explain: bool = typer.Option(
        False,
        "--explain",
        help=tr(
            "cli.review.queue.explain_help",
            default=(
                "Include the legal_refs that ground each finding in the text "
                "output. The JSON payload always carries them."
            ),
        ),
    ),
) -> None:
    """List read-only review queue rows."""
    try:
        resolved_state = ReviewState(state.strip().lower())
        report = project_review_queue(kinds=kinds, source_kinds=source_kinds, state=resolved_state, modelo=modelo)
    except ValueError as exc:
        raise _bad(tr("cli.review.errors.invalid_state", state=state)) from exc
    except ReviewError as exc:
        raise _bad(resolve_error_message(exc)) from exc
    typed_result = ReviewQueueResult(
        rows=tuple(_row_to_payload(row) for row in report.rows),
    )
    _emit_envelope(
        ctx,
        command="review.queue",
        result=typed_result,
        lines=_queue_lines(report, explain=explain),
    )


@app.command("view", help=tr("cli.review.show.help"))
def review_show(
    ctx: typer.Context,
    item_id: str = typer.Argument(..., help=tr("cli.review.show.id_help")),
    explain: bool = typer.Option(
        False,
        "--explain",
        help=tr(
            "cli.review.show.explain_help",
            default=(
                "Include the legal_refs that ground this finding in the text "
                "output. The JSON payload always carries them."
            ),
        ),
    ),
) -> None:
    """View one read-only review queue item."""
    try:
        row = project_review_item(item_id)
    except ReviewError as exc:
        raise _bad(resolve_error_message(exc)) from exc
    typed_result = ReviewViewResult(row=_row_to_payload(row))
    lines = [
        f"{tr('cli.review.labels.id')}\t{row.item_id}",
        f"{tr('cli.review.labels.kind')}\t{row.kind}",
        f"{tr('cli.review.labels.source_kind')}\t{row.source_kind or ''}",
        f"{tr('cli.review.labels.affected_object_id')}\t{row.affected_object_id}",
        f"{tr('cli.review.labels.severity')}\t{row.severity.value}",
        f"{tr('cli.review.labels.next')}\t{row.canonical_next_command}",
    ]
    if explain and row.legal_refs:
        lines.append(f"{tr('cli.review.labels.legal_refs', default='legal_refs')}\t{', '.join(row.legal_refs)}")
    _emit_envelope(ctx, command="review.view", result=typed_result, lines=lines)


def _queue_lines(report: ReviewQueueReport, *, explain: bool = False) -> list[str]:
    """Render the review queue as tab-separated text.

    When ``explain`` is True (per the --explain convention ADR), the
    table grows a trailing ``legal_refs`` column carrying the
    grounding citations for each finding.
    """
    header = (
        f"{tr('cli.review.labels.id')}\t"
        f"{tr('cli.review.labels.kind')}\t"
        f"{tr('cli.review.labels.source_kind')}\t"
        f"{tr('cli.review.labels.affected_object_id')}\t"
        f"{tr('cli.review.labels.period')}\t"
        f"{tr('cli.review.labels.severity')}\t"
        f"{tr('cli.review.labels.next')}"
    )
    if explain:
        header = f"{header}\t{tr('cli.review.labels.legal_refs', default='legal_refs')}"
    lines = [header]
    for row in report.rows:
        base = (
            f"{row.item_id}\t{row.kind}\t{row.source_kind or ''}\t{row.affected_object_id}\t"
            f"{row.period or ''}\t{row.severity.value}\t{row.canonical_next_command}"
        )
        if explain:
            base = f"{base}\t{', '.join(row.legal_refs)}"
        lines.append(base)
    if not report.rows:
        lines.append(tr("cli.review.queue.empty"))
    return lines
