"""Build a paged Ledger request from the browser's controls."""

from __future__ import annotations

from collections.abc import Callable
from uuid import UUID

from pydantic import ValidationError
from textual.widgets import Checkbox, Input, Select

from ....application.ledger.list_operation import LedgerListRequest
from ....core.i18n.render import tr
from ....core.ledger_sort import LedgerSortField, LedgerSortOrder
from .entries_browse_model import BROWSE_PAGE_SIZE
from .entries_common import read_period, selected_value


def form_request(
    *,
    profile_id: UUID,
    select: Callable[[str], Select[str]],
    text: Callable[[str], str],
    checkbox: Callable[[str], bool],
) -> LedgerListRequest:
    """Build one list request from the visible controls in order."""
    filters: list[str] = []
    for key, selector in (
        ("status", "#entries-browse-status"),
        ("direction", "#entries-browse-direction"),
        ("classification", "#entries-browse-classification"),
        ("issue", "#entries-browse-issue"),
    ):
        value = selected_value(select(selector))
        if value is not None:
            filters.append(f"{key}={value}")
    period = read_period(text("#entries-browse-year"), selected_value(select("#entries-browse-period")))
    if period is not None:
        filters.extend((f"period={period.code}", f"year={period.filing_year}"))
    for key, selector in (
        ("text", "#entries-browse-text"),
        ("import", "#entries-browse-import"),
        ("account", "#entries-browse-account"),
    ):
        value = text(selector)
        if value:
            filters.append(f"{key}={value}")
    sort = selected_value(select("#entries-browse-sort"))
    try:
        return LedgerListRequest(
            profile_id=profile_id,
            filters=tuple(filters),
            group=text("#entries-browse-group") or None,
            by_group=checkbox("#entries-browse-by-group"),
            limit=BROWSE_PAGE_SIZE,
            offset=0,
            sort_by=None if sort is None else LedgerSortField(sort),
            sort_order=LedgerSortOrder(str(select("#entries-browse-order").value)),
            exclude_llm_rejected=checkbox("#entries-browse-hide-rejected"),
        )
    except ValidationError:
        # The request's own grammar refused a clause; its message would echo the typed value.
        raise ValueError(tr("tui.ledger.entry_tools.browse.filters_invalid")) from None


def show_request(
    request: LedgerListRequest,
    *,
    select: Callable[[str], Select[str]],
    input_field: Callable[[str], Input],
    checkbox: Callable[[str], Checkbox],
) -> None:
    """Restore the admitted filter request into the visible controls."""
    clauses: dict[str, str] = {}
    for clause in request.filters:
        key, _, value = clause.partition("=")
        clauses[key] = value
    for key, selector in (
        ("status", "#entries-browse-status"),
        ("direction", "#entries-browse-direction"),
        ("classification", "#entries-browse-classification"),
        ("issue", "#entries-browse-issue"),
        ("period", "#entries-browse-period"),
    ):
        if key in clauses:
            select(selector).value = clauses[key]
    for key, selector in (
        ("year", "#entries-browse-year"),
        ("text", "#entries-browse-text"),
        ("import", "#entries-browse-import"),
        ("account", "#entries-browse-account"),
    ):
        input_field(selector).value = clauses.get(key, "")
    input_field("#entries-browse-group").value = request.group or ""
    if request.sort_by is not None:
        select("#entries-browse-sort").value = request.sort_by.value
    select("#entries-browse-order").value = request.sort_order.value
    checkbox("#entries-browse-by-group").value = request.by_group
    checkbox("#entries-browse-hide-rejected").value = request.exclude_llm_rejected
