"""Projection helpers for the ``aeat app ledger list`` CLI command.

The CLI parser turns ``--filter`` clauses into
:class:`LedgerReviewFilterSpec`, asks
:func:`query_ledger_review_rows` for review-derived
rows, and emits :class:`LedgerListRowPayload`
instances.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import override

from ...adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ...application.ledger.actions_manual import (
    ledger_transaction_review_payload,
    list_manual_transactions,
    query_ledger_review_rows,
)
from ...application.ledger.id_resolution import compute_display_id_width
from ...application.ledger.models import LedgerReviewQuery, ManualLedgerTransactionResult
from ...application.ledger.review_projection import ledger_transaction_review_status
from ...application.review.filter import LedgerReviewFilterSpec
from ...core import LedgerSortField, LedgerSortOrder
from ...core.i18n import tr
from ...domain.buckets import BucketEventHistoryCatalogue, BucketEventObjectType, BucketEventType
from ...domain.transactions import Transaction, TransactionCatalogueRepositoryProtocol
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


def _sort_field_value(transaction: Transaction, field: LedgerSortField) -> str:
    """Return a comparable string for ``field`` on ``transaction``.

    Every axis is projected to a single ``str`` type so the sort never raises
    on mixed-type comparison. Optional business axes still yield the empty
    string; the caller pairs it with a *missing* flag so absent keys always sort
    last regardless of order.
    """
    raw = transaction.raw
    if field is LedgerSortField.DATE:
        return (raw.value_date or raw.booked_date).isoformat()
    if field is LedgerSortField.VALUE_DATE:
        return raw.value_date.isoformat() if raw.value_date is not None else ""
    if field is LedgerSortField.AMOUNT:
        # Zero-pad the integer part so lexical order matches numeric order over
        # the non-negative magnitudes (e.g. "9.00" must sort before "10.00").
        magnitude = raw.amount
        return f"{magnitude:020.2f}"
    if field is LedgerSortField.DESCRIPTION:
        return raw.description
    if field is LedgerSortField.CREATED_AT:
        return transaction.created_at.isoformat()
    if field is LedgerSortField.MODIFIED_AT:
        return transaction.modified_at.isoformat()
    if field is LedgerSortField.CLASSIFIED_AT:
        return transaction.classified_at.isoformat() if transaction.classified_at is not None else ""
    if field is LedgerSortField.LIFECYCLE_STATE:
        return transaction.lifecycle_state.value
    return transaction.business_classification.value


class _DescStr:
    """A ``str`` wrapper whose ordering is reversed, for descending sort.

    Lets a single composite sort key express "primary descending, tie-break
    ``transaction_id`` *ascending*" without ``reverse=True`` (which would also
    flip the tie-break). Equality/ordering delegate to the wrapped string with
    the comparison inverted.
    """

    __slots__ = ("value",)

    def __init__(self, value: str) -> None:
        self.value = value

    def __lt__(self, other: _DescStr) -> bool:
        return self.value > other.value

    @override
    def __eq__(self, other: object) -> bool:
        return isinstance(other, _DescStr) and self.value == other.value

    @override
    def __hash__(self) -> int:
        return hash(self.value)


def _sort_results(
    results: tuple[ManualLedgerTransactionResult, ...],
    *,
    sort_by: LedgerSortField,
    sort_order: LedgerSortOrder,
) -> tuple[ManualLedgerTransactionResult, ...]:
    """Stably sort ``results`` by ``sort_by`` with a ``transaction_id`` tie-break.

    Deterministic and single-pass over one composite key
    ``(missing, primary, transaction_id)``: a missing key always sorts last
    (under both ascending and descending) because the *missing* flag is never
    inverted; the primary value is wrapped for descending order; and the
    content-addressed ``transaction_id`` tie-break is *always ascending* so
    equal-key rows have a fixed order across runs (replacing the meaningless
    hash-keyed ``--by-group`` secondary).
    """
    descending = sort_order is LedgerSortOrder.DESC

    def composite_key(
        result: ManualLedgerTransactionResult,
    ) -> tuple[int, _DescStr | str, str]:
        value = _sort_field_value(result.transaction, sort_by)
        missing = 1 if value == "" else 0  # present (0) before absent (1), both orders
        primary: _DescStr | str = _DescStr(value) if descending else value
        return (missing, primary, result.transaction.transaction_id)

    return tuple(sorted(results, key=composite_key))


# The two terminal LLM decisions on a row: an accepted (applied) classification or
# a rejection. The most recent of the two is the standing LLM decision. Canonical
# home, shared by the ledger-view rejection notice so the two surfaces cannot drift.
LLM_DECISION_EVENT_TYPES = (
    BucketEventType.LEDGER_TRANSACTION_CLASSIFIED,
    BucketEventType.LEDGER_TRANSACTION_LLM_SUGGESTION_REJECTED,
)


def latest_llm_decision_is_rejection(event_catalogue: BucketEventHistoryCatalogue, transaction_id: str) -> bool:
    """Return True when the row's most recent LLM decision was a rejection.

    Reads :class:`BucketEventHistoryCatalogue` entries whose
    type belongs to :data:`LLM_DECISION_EVENT_TYPES`.
    The standing LLM decision is the latest of {classified, llm-suggestion-rejected}
    for the transaction. A row whose latest such event is a rejection has been
    reviewed-and-declined and should drop out of the pending review queue when the
    operator filters it out. Reads events only; never consults ``review_status``
    (which stays a pure projection of the classification).
    """
    decisions = [
        event
        for event in event_catalogue.for_object(
            object_type=BucketEventObjectType.LEDGER_TRANSACTION,
            object_id=transaction_id,
        )
        if event.event_type in LLM_DECISION_EVENT_TYPES
    ]
    if not decisions:
        return False
    decisions.sort(key=lambda event: event.occurred_at)
    return decisions[-1].event_type is BucketEventType.LEDGER_TRANSACTION_LLM_SUGGESTION_REJECTED


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
    if exclude_llm_rejected:
        event_catalogue = BucketEventHistoryRepository().load()
        all_results = tuple(
            result
            for result in all_results
            if not latest_llm_decision_is_rejection(event_catalogue, result.transaction.transaction_id)
        )
    if group is not None:
        wanted = group.strip() or None
        all_results = tuple(result for result in all_results if result.transaction.group_label == wanted)
    if sort_by is not None:
        all_results = _sort_results(all_results, sort_by=sort_by, sort_order=sort_order)
    if by_group:
        # Group partitioning is the outer order; a stable sort preserves the
        # sort_by ordering established above within each group block. The
        # group key uses a high sentinel so ungrouped rows trail named groups,
        # with transaction_id only as the residual tie-break when no sort_by
        # was supplied.
        all_results = tuple(
            sorted(
                all_results,
                key=lambda result: (
                    result.transaction.group_label or "\uffff",
                    result.transaction.transaction_id if sort_by is None else "",
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


def ledger_review_query_for_spec(
    spec: LedgerReviewFilterSpec,
    *,
    bucket_id: str,
    transaction_id: str | None = None,
) -> LedgerReviewQuery:
    """Project one parsed operator filter spec onto its :class:`LedgerReviewQuery`.

    The single home for the spec-to-query field mapping, shared by ``ledger
    list``'s review-spec narrowing and the ``ledger review`` verb, so the two
    surfaces cannot resolve the same ``--filter`` clauses differently.
    """
    return LedgerReviewQuery(
        bucket_id=bucket_id,
        transaction_id=transaction_id,
        period=spec.period,
        status=spec.status.value if spec.status is not None else None,
        issue=spec.issue.value if spec.issue is not None else None,
        import_id=spec.import_id,
        classification=spec.classification.value if spec.classification is not None else None,
        text=spec.text,
        direction=spec.direction.value if spec.direction is not None else None,
    )


def _filter_results_by_review_spec(
    *,
    bucket_id: str,
    transaction_repository: TransactionCatalogueRepositoryProtocol,
    spec: LedgerReviewFilterSpec,
    results: tuple[ManualLedgerTransactionResult, ...],
) -> tuple[ManualLedgerTransactionResult, ...]:
    matching = query_ledger_review_rows(
        ledger_review_query_for_spec(spec, bucket_id=bucket_id),
        transaction_repository=transaction_repository,
    )
    matching_ids = {row.id for row in matching.rows}
    return tuple(result for result in results if result.transaction.transaction_id in matching_ids)


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
