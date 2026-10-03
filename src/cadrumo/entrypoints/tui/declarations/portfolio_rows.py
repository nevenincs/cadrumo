"""Pure search, ordering and creation choices over the joined filing portfolio."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from ....application.modelo.declaration_targets import DeclarationTarget
from ....application.modelo.declarations_list import DeclarationListGroup, DeclarationListRow
from ....application.modelo.declarations_workspace import DeclarationsWorkspaceDeclarationRefV1
from ....core.external_constants import OutputLanguage
from ....core.text_fold import fold_for_matching
from ..modelo.workbench.wording import modelo_title, period_words


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


def preferred_creation_target(rows: tuple[DeclarationListRow, ...]) -> DeclarationTarget | None:
    """Prefer the first due row only when it carries a filing period."""
    due = sorted((row for row in rows if row.state == "not_started"), key=lambda row: row.deadline or date.max)
    return DeclarationTarget(due[0].modelo, due[0].period) if due and due[0].period is not None else None


def creation_targets(
    rows: tuple[DeclarationListRow, ...], admitted: tuple[DeclarationTarget, ...]
) -> tuple[DeclarationTarget, ...]:
    """Keep admitted choices, falling back to joined not-started addresses."""
    return admitted or tuple(
        DeclarationTarget(row.modelo, row.period)
        for row in rows
        if row.period is not None and row.state == "not_started"
    )


def existing_declaration(
    rows: tuple[DeclarationListRow, ...], target: DeclarationTarget
) -> DeclarationsWorkspaceDeclarationRefV1 | None:
    """Find an existing declaration at exactly the chosen filing address."""
    return next(
        (
            row.declaration
            for row in rows
            if row.declaration is not None and row.modelo == target.modelo and row.period == target.period
        ),
        None,
    )
