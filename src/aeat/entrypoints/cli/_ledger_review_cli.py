"""Review command registration for ``aeat app ledger``."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import typer

from ...application.ledger import (
    LedgerReviewQuery,
    LedgerReviewQueryResult,
    LedgerReviewRow,
    compute_display_id_width,
    query_ledger_review_rows,
)
from ...application.review import FilterParseError, LedgerReviewFilterSpec
from ...core.i18n import tr
from ._common import _bad, _emit_envelope, _filter_canonical_period, _state, _tx_repo

ResolveTransactionId = Callable[[Any, str], str]


def register_ledger_review_command(app: typer.Typer, *, resolve_transaction_id: ResolveTransactionId) -> None:
    @app.command("review", help=tr("cli.ledger.review.help"))
    def ledger_review(
        ctx: typer.Context,
        filters: list[str] = typer.Option([], "--filter", help=tr("cli.ledger.review.filter_help")),
        record_id: str | None = typer.Option(None, "--id", help=tr("cli.ledger.review.id_help")),
        verbose: bool = typer.Option(False, "--verbose", help=tr("cli.ledger.review.verbose_help")),
    ) -> None:
        """Render rows or a single row using the typed filter spec."""
        spec = _ledger_review_filter_spec(filters)
        transaction_repository = _tx_repo(_state())
        result = query_ledger_review_rows(
            _ledger_review_query(
                transaction_repository,
                spec=spec,
                record_id=record_id,
                resolve_transaction_id=resolve_transaction_id,
            ),
            transaction_repository=transaction_repository,
        )
        _emit_ledger_review_result(ctx, record_id=record_id, verbose=verbose, result=result)


def _ledger_review_filter_spec(filters: list[str]) -> LedgerReviewFilterSpec:
    try:
        return LedgerReviewFilterSpec.from_strings(filters)
    except FilterParseError as exc:
        raise _bad(tr("cli.ledger.errors.filter_parse_error", reason=exc.reason, token=exc.safe_token)) from exc


def _ledger_review_query(
    transaction_repository: Any,
    *,
    spec: LedgerReviewFilterSpec,
    record_id: str | None,
    resolve_transaction_id: ResolveTransactionId,
) -> LedgerReviewQuery:
    resolved_record_id = resolve_transaction_id(transaction_repository, record_id) if record_id is not None else None
    return LedgerReviewQuery(
        bucket_id=transaction_repository.bucket_id,
        transaction_id=resolved_record_id,
        period=(
            _filter_canonical_period(spec.period, year=spec.year)
            if spec.period is not None and spec.year is not None
            else None
        ),
        status=spec.status.value if spec.status is not None else None,
        issue=spec.issue.value if spec.issue is not None else None,
        import_id=spec.import_id,
        classification=spec.classification.value if spec.classification is not None else None,
        text=spec.text,
        direction=spec.direction.value if spec.direction is not None else None,
    )


def _ledger_review_empty_payload(result: LedgerReviewQueryResult) -> dict[str, object]:
    return {"rows": [], "filters": list(result.filters)}


def _ledger_review_detail_payload(row: LedgerReviewRow, *, verbose: bool) -> dict[str, object]:
    return {
        "id": row.id,
        "date": row.date,
        "amount": row.amount,
        "description": row.description,
        "review_status": row.status,
        "transaction": row.transaction.model_dump(mode="json") if row.transaction is not None else None,
        "verbose": verbose,
    }


def _ledger_review_detail_lines(row: LedgerReviewRow) -> list[str]:
    return [
        f"{tr('cli.ledger.labels.id')}\t{row.id}",
        f"{tr('cli.ledger.labels.date')}\t{row.date}",
        f"{tr('cli.ledger.labels.amount')}\t{row.amount}",
        f"{tr('cli.ledger.labels.description')}\t{row.description}",
    ]


def _ledger_review_list_payload(result: LedgerReviewQueryResult) -> dict[str, object]:
    return {
        "rows": [row.model_dump(mode="json", exclude_none=True) for row in result.rows],
        "filters": list(result.filters),
    }


def _ledger_review_list_lines(result: LedgerReviewQueryResult) -> list[str]:
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
    result: LedgerReviewQueryResult,
) -> None:
    from ._ledger_payloads import LedgerReviewResult

    if record_id is not None:
        if not result.rows:
            _emit_envelope(
                ctx,
                command="ledger.review",
                result=LedgerReviewResult.model_validate(_ledger_review_empty_payload(result)),
                lines=[tr("cli.ledger.review.header"), tr("cli.ledger.review.no_rows")],
            )
            return
        row = result.rows[0]
        _emit_envelope(
            ctx,
            command="ledger.review",
            result=LedgerReviewResult.model_validate(_ledger_review_detail_payload(row, verbose=verbose)),
            lines=_ledger_review_detail_lines(row),
        )
        return
    _emit_envelope(
        ctx,
        command="ledger.review",
        result=LedgerReviewResult.model_validate(_ledger_review_list_payload(result)),
        lines=_ledger_review_list_lines(result),
    )


__all__ = ["register_ledger_review_command"]
