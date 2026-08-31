from __future__ import annotations

from decimal import Decimal

import typer

from ...application.review.enums import ReviewState
from ...application.review.errors import ReviewError
from ...application.review.operator import (
    ReviewQueueReport,
    ReviewQueueRow,
    project_review_item,
    project_review_queue,
)
from ...core.decimal.coercion import coerce_decimal_strict
from ...core.errors.error_codes import resolve_error_message
from ...core.external_constants import OutputLanguage
from ...core.i18n.render import tr
from ...core.unit_proportion import is_unit_proportion
from ._common import _bad, activate_subcommand_output_language, emit_envelope
from ._review_payloads import ReviewQueueResult, ReviewQueueRowPayload, ReviewViewResult


def _row_to_payload(row: ReviewQueueRow) -> ReviewQueueRowPayload:
    """Project the application-side ``ReviewQueueRow`` onto the typed CLI payload.

    Keeps the CLI JSON contract pinned to the registered
    :class:`~entrypoints.cli._review_payloads.ReviewQueueRowPayload`
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
        severity=row.severity,
        state=row.state,
        blocking=row.blocking,
        reason=row.reason,
        current_owner_surface=row.current_owner_surface,
        canonical_next_command=row.canonical_next_command,
        since=row.since,
        summary=row.summary,
        legal_refs=tuple(row.legal_refs),
    )


def _resolve_confidence_threshold(value: float | None) -> Decimal | None:
    """Validate and lift the ``--confidence-below`` option to a Decimal.

    ``classification_confidence`` is a share of one, so a threshold outside
    that range can never match a stored confidence. The bound itself comes from
    :func:`~cadrumo.core.unit_proportion.is_unit_proportion`, the same predicate
    the transaction model's own validator asks; what stays here is the
    localised, instructive refusal that names the accepted range rather than
    silently passing a bad value through.
    """
    if value is None:
        return None
    threshold = coerce_decimal_strict(value)
    if not is_unit_proportion(threshold):
        raise _bad(
            tr(
                "cli.review.errors.invalid_confidence",
                value=str(value),
                default="Confidence threshold %{value} is out of range; supply a value between 0 and 1.",
            ),
        )
    return threshold


def parse_review_state(value: str) -> ReviewState:
    """Parse a review-state token case-insensitively."""
    normalized = value.casefold()
    try:
        return next(state for state in ReviewState if state.value.casefold() == normalized)
    except StopIteration as error:
        choices = ", ".join(state.value for state in ReviewState)
        raise typer.BadParameter(f"expected one of: {choices}") from error


def review_queue(
    ctx: typer.Context,
    kinds: list[str],
    source_kinds: list[str],
    state: ReviewState,
    modelo: str | None = None,
    confidence_below: float | None = None,
    explain: bool = False,
    output_language: OutputLanguage | None = None,
) -> None:
    """List read-only review queue rows."""
    activate_subcommand_output_language(ctx, output_language)
    threshold = _resolve_confidence_threshold(confidence_below)
    try:
        report = project_review_queue(
            kinds=kinds,
            source_kinds=source_kinds,
            state=state,
            modelo=modelo,
            confidence_below=threshold,
        )
    except ReviewError as exc:
        raise _bad(resolve_error_message(exc)) from exc
    typed_result = ReviewQueueResult(
        rows=tuple(_row_to_payload(row) for row in report.rows),
    )
    emit_envelope(
        ctx,
        command="review.queue",
        result=typed_result,
        lines=_queue_lines(report, explain=explain),
    )


def review_view(
    ctx: typer.Context,
    item_id: str,
    explain: bool = False,
    output_language: OutputLanguage | None = None,
) -> None:
    """View one read-only review queue item."""
    activate_subcommand_output_language(ctx, output_language)
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
    emit_envelope(ctx, command="review.view", result=typed_result, lines=lines)


def _queue_lines(report: ReviewQueueReport, *, explain: bool = False) -> list[str]:
    """Render the review queue as tab-separated text.

    When ``explain`` is True, the
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


__all__ = ["parse_review_state", "review_queue", "review_view"]
