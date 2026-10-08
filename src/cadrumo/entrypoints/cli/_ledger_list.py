"""Render admitted ledger pages as CLI rows and text without opening custody."""

from __future__ import annotations

from dataclasses import dataclass

from ...application.ledger.id_resolution import compute_display_id_width
from ...application.ledger.list_operation import LedgerListProjection as LedgerListSnapshot
from ...application.ledger.transaction_projection import LedgerTransactionReviewProjection
from ...core.i18n.render import tr
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


def project_ledger_list(page: LedgerListSnapshot) -> LedgerListProjection:
    """Render the admitted immutable page without opening profile custody."""
    bucket_id = str(page.profile_id)
    results = page.rows
    total = page.total
    truncated = page.truncated
    offset = page.offset
    limit = page.limit
    rows, lines = _ledger_list_rows_and_lines(
        results=results,
        all_transaction_ids=tuple(result.transaction.transaction_id for result in results),
        by_group=page.by_group,
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
    results: tuple[LedgerTransactionReviewProjection, ...],
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
        if by_group and (not first_group_seen or result.group_label != current_group):
            current_group = result.group_label
            first_group_seen = True
            lines.append(f"# {current_group or ungrouped}")
        review_status = result.review_status
        review_payload = transaction
        display_id = transaction.transaction_id[:display_width]
        # D2: project the review payload (which carries review_status, the
        # non-negative amount + direction, and the D6 timestamps) plus the three
        # id/group keys into the typed list-row schema.
        rows.append(
            LedgerListRowPayload.model_validate(
                {
                    **review_payload.model_dump(mode="json"),
                    "review_status": review_status,
                    "full_id": transaction.transaction_id,
                    "display_id": display_id,
                    "group_label": result.group_label,
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
