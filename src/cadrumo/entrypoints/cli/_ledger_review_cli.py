"""Review behavior handlers for ``aeat app ledger``.

The command renders the canonical review result admitted by the profile worker.
"""

from __future__ import annotations

import typer

from ...application.ledger.id_resolution import compute_display_id_width
from ...application.ledger.review_operation import LedgerReviewProjection, LedgerReviewRowProjection
from ...application.review.errors import FilterParseError
from ...application.review.filter import LedgerReviewFilterSpec
from ...core.i18n.render import tr
from ._ledger_support import ledger_cli_no_recovery
from .common import emit_envelope
from .runtime_ledger_review import read_ledger_review_for_cli


def ledger_review(
    ctx: typer.Context, filters: tuple[str, ...] = (), record_id: str | None = None, verbose: bool = False
) -> None:
    """Render rows or a single row using the typed filter spec."""
    spec = _ledger_review_filter_spec(list(filters))
    result = read_ledger_review_for_cli(ctx, spec=spec, record_id=record_id)
    _emit_ledger_review_result(ctx, record_id=record_id, verbose=verbose, result=result)


def _ledger_review_filter_spec(filters: list[str]) -> LedgerReviewFilterSpec:
    try:
        return LedgerReviewFilterSpec.from_strings(filters)
    except FilterParseError as exc:
        from ...application.cli_exception_preconditions import CliExceptionPrecondition

        raise ledger_cli_no_recovery(
            exc,
            condition=CliExceptionPrecondition.LEDGER_FILTER_VALID,
            facts={"ledger_filter_valid": False, "reason": exc.reason},
        ) from None


def _ledger_review_empty_payload(result: LedgerReviewProjection) -> dict[str, object]:
    return {"rows": [], "filters": list(result.filters)}


def _ledger_review_detail_payload(row: LedgerReviewRowProjection, *, verbose: bool) -> dict[str, object]:
    return {
        "id": row.id,
        "date": row.date,
        "amount": row.amount,
        "description": row.description,
        "review_status": row.status,
        "transaction": row.transaction.model_dump(mode="json") if row.transaction is not None else None,
        "verbose": verbose,
    }


def _ledger_review_detail_lines(row: LedgerReviewRowProjection) -> list[str]:
    return [
        f"{tr('cli.ledger.labels.id')}\t{row.id}",
        f"{tr('cli.ledger.labels.date')}\t{row.date}",
        f"{tr('cli.ledger.labels.amount')}\t{row.amount}",
        f"{tr('cli.ledger.labels.description')}\t{row.description}",
    ]


def _ledger_review_list_payload(result: LedgerReviewProjection) -> dict[str, object]:
    return {
        "rows": [row.model_dump(mode="json", exclude_none=True) for row in result.rows],
        "filters": list(result.filters),
    }


def _ledger_review_list_lines(result: LedgerReviewProjection) -> list[str]:
    lines: list[str] = [tr("cli.ledger.review.header")]
    review_ids = tuple(row.id for row in result.rows)
    review_width = compute_display_id_width(review_ids)
    lines.extend(
        f"{row.id[:review_width]}\t{row.id}\t{row.date}\t{row.amount}\t{row.description}\t{row.status}"
        for row in result.rows
    )
    if not result.rows:
        lines.append(tr("cli.ledger.review.no_rows"))
    return lines


def _emit_ledger_review_result(
    ctx: typer.Context,
    *,
    record_id: str | None,
    verbose: bool,
    result: LedgerReviewProjection,
) -> None:
    from ._ledger_payloads import LedgerReviewResult

    if record_id is not None:
        if not result.rows:
            emit_envelope(
                ctx,
                command="ledger.review",
                result=LedgerReviewResult.model_validate(_ledger_review_empty_payload(result)),
                lines=[tr("cli.ledger.review.header"), tr("cli.ledger.review.no_rows")],
            )
            return
        row = result.rows[0]
        emit_envelope(
            ctx,
            command="ledger.review",
            result=LedgerReviewResult.model_validate(_ledger_review_detail_payload(row, verbose=verbose)),
            lines=_ledger_review_detail_lines(row),
        )
        return
    emit_envelope(
        ctx,
        command="ledger.review",
        result=LedgerReviewResult.model_validate(_ledger_review_list_payload(result)),
        lines=_ledger_review_list_lines(result),
    )


__all__ = ["ledger_review"]
