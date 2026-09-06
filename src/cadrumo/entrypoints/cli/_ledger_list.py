"""Projection helpers for the ``aeat app ledger list`` CLI command.

The CLI parser turns ``--filter`` clauses into
:class:`LedgerReviewFilterSpec`, asks
:func:`query_ledger_review_rows` for review-derived
rows, and emits :class:`LedgerListRowPayload`
instances.
"""

from __future__ import annotations

from dataclasses import dataclass

from ...adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ...application.ledger.actions_manual import (
    ledger_transaction_review_payload,
)
from ...application.ledger.id_resolution import compute_display_id_width
from ...application.ledger.list_query import LedgerTransactionListQuery, query_ledger_transaction_list
from ...application.ledger.models import ManualLedgerTransactionResult
from ...application.ledger.review_projection import ledger_transaction_review_status
from ...application.review.filter import LedgerReviewFilterSpec
from ...core.i18n.render import tr
from ...core.ledger_sort import LedgerSortField, LedgerSortOrder
from ...domain.transactions.protocols import TransactionCatalogueRepositoryProtocol
from ._ledger_payloads import LedgerListRowPayload


@dataclass(frozen=True)
class LedgerListProjection:
    """Rendered :class:`LedgerListRowPayload` inputs for ``ledger list``."""

    bucket_id: str
    rows: list[LedgerListRowPayload]
    total: int
    shown: int
    offset: int
    limit: int | None
    truncated: bool
    lines: list[str]


def project_ledger_list(
    *,
    transaction_repository: TransactionCatalogueRepositoryProtocol,
    spec: LedgerReviewFilterSpec,
    group: str | None,
    by_group: bool,
    limit: int | None,
    offset: int,
    sort_by: LedgerSortField | None = None,
    sort_order: LedgerSortOrder = LedgerSortOrder.ASC,
    exclude_llm_rejected: bool = False,
) -> LedgerListProjection:
    """Project, page, and render one ``ledger list`` result set.

    Returns a :class:`LedgerListProjection`.

    When ``sort_by`` is supplied the result set is stably sorted on that closed
    :class:`LedgerSortField` axis (ascending by default,
    ``sort_order=DESC`` for descending), applied *after* the C6 filter and the
    ``--group`` selection and *before* paging, with a deterministic final
    tie-break on the content-addressed ``transaction_id`` (D5). ``--by-group``
    still partitions rows by group label first; the sort orders within that
    partition. With ``exclude_llm_rejected`` the projection drops every row whose
    latest decision in the :class:`BucketEventHistoryRepository` is an LLM
    rejection.
    """
    bucket_id = transaction_repository.bucket_id
    page = query_ledger_transaction_list(
        LedgerTransactionListQuery(
            spec=spec,
            group=group,
            by_group=by_group,
            limit=limit,
            offset=offset,
            sort_by=sort_by,
            sort_order=sort_order,
            exclude_llm_rejected=exclude_llm_rejected,
        ),
        bucket_id=bucket_id,
        transaction_repository=transaction_repository,
        bucket_event_repository=BucketEventHistoryRepository() if exclude_llm_rejected else None,
    )
    results = page.results
    total = page.total
    truncated = page.truncated
    rows, lines = _ledger_list_rows_and_lines(
        results=results,
        all_transaction_ids=tuple(result.transaction.transaction_id for result in results),
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


def _ledger_list_rows_and_lines(
    *,
    results: tuple[ManualLedgerTransactionResult, ...],
    all_transaction_ids: tuple[str, ...],
    by_group: bool,
) -> tuple[list[LedgerListRowPayload], list[str]]:
    rows: list[LedgerListRowPayload] = []
    lines = [
        tr("cli.ledger.list.header"),
        _ledger_list_column_header(),
    ]
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
        # D2: project the review payload (which carries review_status, the
        # non-negative amount + direction, and the D6 timestamps) plus the three
        # id/group keys into the typed list-row schema.
        rows.append(
            LedgerListRowPayload.model_validate(
                {
                    **review_payload.model_dump(mode="json"),
                    "full_id": transaction.transaction_id,
                    "display_id": display_id,
                    "group_label": transaction.group_label,
                },
            ),
        )
        iva_category = review_payload.iva_category or ""
        lines.append(
            f"{display_id}\t{transaction.transaction_id}\t{review_payload.date}\t"
            f"{review_payload.amount}\t{review_payload.description}\t{iva_category}\t{review_status}",
        )
    return rows, lines


def _ledger_list_column_header() -> str:
    base_header = tr("cli.ledger.list.column_header")
    iva_category_label = tr("cli.ledger.labels.iva_category")
    columns = base_header.split("\t")
    if len(columns) >= 2:
        return "\t".join((*columns[:-1], iva_category_label, columns[-1]))
    return f"{base_header}\t{iva_category_label}"


__all__ = [
    "LedgerListProjection",
    "project_ledger_list",
]
