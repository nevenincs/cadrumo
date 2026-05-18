from __future__ import annotations

import typer

from ...application.review import ReviewError, ReviewQueueReport, ReviewState, project_review_item, project_review_queue
from ...application.review._operator import ReviewQueueRow
from ._common import _bad, _emit
from ...core.i18n import tr
from ._review_payloads import ReviewQueueResult, ReviewQueueRowPayload, ReviewViewResult


def _row_to_payload(row: ReviewQueueRow) -> ReviewQueueRowPayload:
    """Project the application-side ``ReviewQueueRow`` onto the typed CLI payload.

    Keeps the CLI JSON contract pinned to the registered
    :class:`ReviewQueueRowPayload` shape; downstream JSON consumers
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
) -> None:
    """List read-only review queue rows."""

    try:
        resolved_state = ReviewState(state.strip().lower())
        report = project_review_queue(kinds=kinds, source_kinds=source_kinds, state=resolved_state, modelo=modelo)
    except ValueError as exc:
        raise _bad(tr("cli.review.errors.invalid_state", state=state)) from exc
    except ReviewError as exc:
        raise _bad(str(exc)) from exc
    typed_result = ReviewQueueResult(
        rows=tuple(_row_to_payload(row) for row in report.rows),
    )
    _emit(
        ctx,
        typed_result.model_dump(mode="json"),
        _queue_lines(report),
    )


@app.command("view", help=tr("cli.review.show.help"))
def review_show(
    ctx: typer.Context,
    item_id: str = typer.Argument(..., help=tr("cli.review.show.id_help")),
) -> None:
    """View one read-only review queue item."""

    try:
        row = project_review_item(item_id)
    except ReviewError as exc:
        raise _bad(str(exc)) from exc
    typed_result = ReviewViewResult(row=_row_to_payload(row))
    _emit(
        ctx,
        typed_result.model_dump(mode="json"),
        [
            f"{tr('cli.review.labels.id')}\t{row.item_id}",
            f"{tr('cli.review.labels.kind')}\t{row.kind}",
            f"{tr('cli.review.labels.source_kind')}\t{row.source_kind or ''}",
            f"{tr('cli.review.labels.affected_object_id')}\t{row.affected_object_id}",
            f"{tr('cli.review.labels.bucket')}\t{row.bucket_id}",
            f"{tr('cli.review.labels.severity')}\t{row.severity.value}",
            f"{tr('cli.review.labels.next')}\t{row.canonical_next_command}",
        ],
    )


def _queue_lines(report: ReviewQueueReport) -> list[str]:
    lines = [
        f"{tr('cli.review.labels.id')}\t"
        f"{tr('cli.review.labels.kind')}\t"
        f"{tr('cli.review.labels.source_kind')}\t"
        f"{tr('cli.review.labels.affected_object_id')}\t"
        f"{tr('cli.review.labels.bucket')}\t"
        f"{tr('cli.review.labels.period')}\t"
        f"{tr('cli.review.labels.severity')}\t"
        f"{tr('cli.review.labels.next')}"
    ]
    for row in report.rows:
        lines.append(
            f"{row.item_id}\t{row.kind}\t{row.source_kind or ''}\t{row.affected_object_id}\t"
            f"{row.bucket_id}\t{row.period or ''}\t{row.severity.value}\t{row.canonical_next_command}"
        )
    if not report.rows:
        lines.append(tr("cli.review.queue.empty"))
    return lines
