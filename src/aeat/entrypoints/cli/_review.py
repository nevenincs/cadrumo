from __future__ import annotations

import typer

from ...application.review import ReviewError, ReviewQueueReport, ReviewState, project_review_item, project_review_queue
from ._common import _bad, _emit
from ._i18n import tr

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
    _emit(
        ctx,
        report.model_dump(mode="json"),
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
    _emit(
        ctx,
        row.model_dump(mode="json"),
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
