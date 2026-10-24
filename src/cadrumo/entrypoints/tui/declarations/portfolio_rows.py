"""Pure search and ordering over the joined filing portfolio."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from ....application.modelo.declarations_list import DeclarationListGroup, DeclarationListRow
from ....application.modelo.work_form_wording import modelo_title, period_words
from ....core.external_constants import OutputLanguage
from ....core.text_fold import fold_for_matching


def _sort_portfolio_rows(rows: list[DeclarationListRow], sort: str) -> None:
    """Sort portfolio rows."""
    if sort == "result":
        rows.sort(key=result_sort_key)
    elif sort == "state":
        rows.sort(key=lambda row: (row.state, row.modelo, row.deadline or date.max))
    elif sort == "modelo":
        rows.sort(key=lambda row: (row.modelo, row.deadline or date.max))
    else:
        rows.sort(key=lambda row: (row.deadline or date.max, row.modelo))


def matches_filter(row: DeclarationListRow, selected_filter: str, year: int) -> bool:
    """Apply one closed portfolio filter before word search."""
    if selected_filter == "attention":
        return row.group is DeclarationListGroup.ATTENTION
    if selected_filter == "this_year":
        return row.period is not None and row.period.filing_year == year
    if selected_filter == "recorded":
        return row.group is DeclarationListGroup.RECORDED
    if selected_filter == "not_started":
        return row.state == "not_started"
    return True


def visible_portfolio_rows(
    portfolio: tuple[DeclarationListRow, ...],
    query: str,
    selected_filter: str,
    sort: str,
    year: int,
    language: OutputLanguage,
) -> list[DeclarationListRow]:
    """Apply Unicode AND search and the selected stable ordering."""
    terms = fold_for_matching(query).split()
    rows = []
    for row in portfolio:
        if not matches_filter(row, selected_filter, year):
            continue
        text = modelo_title(row.modelo, language) + " " + (period_words(row.period) if row.period else "")
        if all(term in fold_for_matching(text) for term in terms):
            rows.append(row)
    _sort_portfolio_rows(rows, sort)
    return rows


def result_sort_key(row: DeclarationListRow) -> tuple[bool, Decimal, str]:
    """Keep unknown results after known signed values and break ties by Modelo."""
    summary = None if row.declaration is None else row.declaration.summary
    value = None if summary is None or summary.result is None else summary.result.value
    return (value is None, value if value is not None else Decimal(0), row.modelo)
