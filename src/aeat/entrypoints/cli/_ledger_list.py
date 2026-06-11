"""Projection helpers for the ``aeat app ledger list`` CLI command."""

from __future__ import annotations

from dataclasses import dataclass

from ...application.ledger import (
    LedgerReviewQuery,
    ManualLedgerTransactionResult,
    compute_display_id_width,
    ledger_transaction_review_payload,
    ledger_transaction_review_status,
    list_manual_transactions,
    query_ledger_review_rows,
)
from ...application.review import LedgerReviewFilterSpec
from ...core.i18n import tr
from ...domain.transactions import TransactionCatalogueRepositoryProtocol
from ._common import _filter_canonical_period


@dataclass(frozen=True)
class LedgerListProjection:
    """Rendered payload inputs for ``ledger list``."""

    bucket_id: str
    rows: list[dict[str, object]]
    total: int
    shown: int
    offset: int
    limit: int | None
    truncated: bool
    lines: list[str]


def parse_ledger_list_filter_spec(filters: list[str]) -> LedgerReviewFilterSpec:
    """Parse ``ledger list --filter`` clauses and return a :class:`LedgerReviewFilterSpec`."""
    return LedgerReviewFilterSpec.from_strings(filters)


def project_ledger_list(
    *,
    transaction_repository: TransactionCatalogueRepositoryProtocol,
    spec: LedgerReviewFilterSpec,
    group: str | None,
    by_group: bool,
    limit: int | None,
    offset: int,
) -> LedgerListProjection:
    """Project, page, and render one ``ledger list`` result set and return a :class:`LedgerListProjection`."""
    bucket_id = transaction_repository.bucket_id
    all_results = list_manual_transactions(
        bucket_id=bucket_id,
        transaction_repository=transaction_repository,
    )
    if spec.clauses:
        all_results = _filter_results_by_review_spec(
            bucket_id=bucket_id,
            transaction_repository=transaction_repository,
            spec=spec,
            results=all_results,
        )
    if group is not None:
        wanted = group.strip() or None
        all_results = tuple(result for result in all_results if result.transaction.group_label == wanted)
    if by_group:
        all_results = tuple(
            sorted(
                all_results,
                key=lambda result: (
                    result.transaction.group_label or "\uffff",
                    result.transaction.transaction_id,
                ),
            ),
        )

    total = len(all_results)
    window_end = total if limit is None else min(offset + limit, total)
    results = all_results[offset:window_end]
    truncated = (offset > 0) or (window_end < total)
    rows, lines = _ledger_list_rows_and_lines(
        results=results,
        all_transaction_ids=tuple(result.transaction.transaction_id for result in all_results),
        by_group=by_group,
    )
    if truncated:
        lines.append(
            tr(
                "cli.ledger.list.footer_truncated",
                start=offset + 1 if rows else offset,
                end=offset + len(rows),
                total=total,
                offset=offset,
            ),
        )
    return LedgerListProjection(
        bucket_id=bucket_id,
        rows=rows,
        total=total,
        shown=len(rows),
        offset=offset,
        limit=limit,
        truncated=truncated,
        lines=lines,
    )


def _filter_results_by_review_spec(
    *,
    bucket_id: str,
    transaction_repository: TransactionCatalogueRepositoryProtocol,
    spec: LedgerReviewFilterSpec,
    results: tuple[ManualLedgerTransactionResult, ...],
) -> tuple[ManualLedgerTransactionResult, ...]:
    matching = query_ledger_review_rows(
        LedgerReviewQuery(
            bucket_id=bucket_id,
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
        ),
        transaction_repository=transaction_repository,
    )
    matching_ids = {row.id for row in matching.rows}
    return tuple(result for result in results if result.transaction.transaction_id in matching_ids)


def _ledger_list_rows_and_lines(
    *,
    results: tuple[ManualLedgerTransactionResult, ...],
    all_transaction_ids: tuple[str, ...],
    by_group: bool,
) -> tuple[list[dict[str, object]], list[str]]:
    rows: list[dict[str, object]] = []
    lines = [tr("cli.ledger.list.header")]
    display_width = compute_display_id_width(all_transaction_ids)
    current_group: str | None = None
    first_group_seen = False
    ungrouped = tr("cli.ledger.list.ungrouped_label")
    for result in results:
        transaction = result.transaction
        if by_group and (not first_group_seen or transaction.group_label != current_group):
            current_group = transaction.group_label
            first_group_seen = True
            lines.append(f"# {current_group or ungrouped}")
        review_status = ledger_transaction_review_status(transaction)
        review_payload = ledger_transaction_review_payload(transaction)
        display_id = transaction.transaction_id[:display_width]
        rows.append(
            {
                **review_payload.model_dump(mode="python"),
                "full_id": transaction.transaction_id,
                "display_id": display_id,
                "group_label": transaction.group_label,
            },
        )
        lines.append(
            f"{display_id}\t{transaction.transaction_id}\t{review_payload.date}\t"
            f"{review_payload.amount}\t{review_payload.description}\t{review_status}",
        )
    return rows, lines


__all__ = [
    "LedgerListProjection",
    "parse_ledger_list_filter_spec",
    "project_ledger_list",
]
