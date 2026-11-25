"""Statement header matching and row parsing shared by the spreadsheet statement providers.

A spreadsheet statement is a grid of typed cells whatever file format carries
it. Once each format's reader has produced that grid, choosing the worksheet
and header row, and turning each data row into a
:class:`~adapters.inbound.financial.providers.base.ParsedLedgerRow`, is the same
work. It is done here once, against the bank-neutral statement vocabulary and
parse rules of :mod:`adapters.inbound.financial.providers.csv`, so ``.xlsx``
and ``.xls`` exports of the same statement read identically.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from .....core.logging import get_logger
from .base import (
    FinancialProvider,
    FinancialValidationError,
    InvalidFinancialSourceError,
    ParsedLedgerRow,
    archive_cell_text,
)
from .csv import (
    ParsedTabularTransactionRow,
    StatementConventions,
    build_provider_row,
    check_summary_totals,
    header_lookup,
    infer_statement_conventions,
    layout_score,
    parse_tabular_transaction_row,
    row_is_blank,
    summary_row_positions,
)

__all__ = [
    "LAYOUT_SAMPLE_ROWS",
    "MIN_LAYOUT_SCORE",
    "WorksheetLayoutMatch",
    "best_layout_match",
    "iter_worksheet_rows",
]

_logger = get_logger(__name__)

#: A header row further down than this is not a statement header.
LAYOUT_SAMPLE_ROWS = 10

#: The fewest matching column aliases that identify a statement header row.
MIN_LAYOUT_SCORE = 3


@dataclass(frozen=True, slots=True)
class WorksheetLayoutMatch:
    """The header row of one worksheet that best names the statement columns.

    Attributes:
        score: Number of statement column aliases the header row matched.
        header_index: 0-based index of the header row in the worksheet.
        headers: The header row's cell text.
        lookup: Lower-cased header text mapped back to the header as written.
    """

    score: int
    header_index: int
    headers: list[str]
    lookup: dict[str, str]


def best_layout_match(sample_rows: Iterable[Sequence[object]]) -> WorksheetLayoutMatch | None:
    """Score each non-blank row of ``sample_rows`` against the statement vocabulary and keep the best."""
    best: WorksheetLayoutMatch | None = None
    for index, row in enumerate(sample_rows):
        texts = [archive_cell_text(cell) for cell in row]
        if not any(text.strip() for text in texts):
            continue
        lookup = header_lookup(texts)
        score = layout_score(lookup)
        if best is None or score > best.score:
            best = WorksheetLayoutMatch(score=score, header_index=index, headers=texts, lookup=lookup)
    return best


def _worksheet_typed_fields(headers: Sequence[str], row: Sequence[object]) -> dict[str, object]:
    """Map typed cells to the matched headers, retaining absent trailing columns."""
    return {header: row[index] if index < len(row) else "" for index, header in enumerate(headers)}


def _worksheet_text_fields(headers: Sequence[str], row: Sequence[object]) -> dict[str, str]:
    """Archive each matched cell as text without changing its typed parse value."""
    return {header: archive_cell_text(row[index]) if index < len(row) else "" for index, header in enumerate(headers)}


def _parse_worksheet_transaction(
    conventions: StatementConventions,
    lookup: Mapping[str, str],
    raw_fields: Mapping[str, str],
    typed_fields: Mapping[str, object],
    provider_name: str,
    sheet_name: str,
    source_sha256: str,
    source_row_index: int,
) -> ParsedTabularTransactionRow:
    """Decode one worksheet movement and retain its row-specific refusal wording."""
    try:
        return parse_tabular_transaction_row(
            conventions=conventions,
            lookup=lookup,
            raw_fields=raw_fields,
            typed_fields=typed_fields,
            synthetic_provider_name=f"{provider_name}-{sheet_name}",
            source_sha256=source_sha256,
            source_row_index=source_row_index,
            required_field_context="worksheet row",
        )
    except (ValueError, FinancialValidationError) as exc:
        _logger.warning(
            "%s: parse error row=%d reason=%s",
            provider_name,
            source_row_index,
            "financial_validation" if isinstance(exc, FinancialValidationError) else "invalid_value",
        )
        raise InvalidFinancialSourceError(
            f"worksheet row {source_row_index} could not be parsed: "
            f"{str(exc) if isinstance(exc, FinancialValidationError) else 'invalid field value'}",
        ) from None


def iter_worksheet_rows(
    *,
    provider: FinancialProvider,
    path: Path,
    source_sha256: str,
    rows: Sequence[Sequence[object]],
    match: WorksheetLayoutMatch,
    sheet_name: str,
) -> Iterator[ParsedLedgerRow]:
    """Yield one parsed row per non-blank data row below the matched header.

    ``source_row_index`` is the 1-based worksheet row, header included, so the
    stored provenance names the row an operator sees in a spreadsheet
    application.

    Raises:
        InvalidFinancialSourceError: The worksheet prints dates in both
            orders, or a data row cannot be parsed.
    """
    headers = match.headers
    data_rows = rows[match.header_index + 1 :]
    try:
        conventions = infer_statement_conventions(
            (_worksheet_typed_fields(headers, row) for row in data_rows),
            match.lookup,
        )
    except FinancialValidationError as exc:
        raise InvalidFinancialSourceError(str(exc)) from None
    text_rows = [_worksheet_text_fields(headers, row) for row in data_rows]
    summary = summary_row_positions(text_rows, match.lookup)
    movements: list[ParsedLedgerRow] = []
    for position, (row, raw_fields) in enumerate(zip(data_rows, text_rows, strict=True)):
        source_row_index = match.header_index + 2 + position
        if row_is_blank(raw_fields) or position in summary:
            continue
        typed_fields = _worksheet_typed_fields(headers, row)
        parsed = _parse_worksheet_transaction(
            conventions,
            match.lookup,
            raw_fields,
            typed_fields,
            provider.name,
            sheet_name,
            source_sha256,
            source_row_index,
        )
        movements.append(
            build_provider_row(
                provider=provider,
                path=path,
                source_sha256=source_sha256,
                source_row_index=source_row_index,
                parsed=parsed,
                raw_fields=raw_fields,
            )
        )
    check_summary_totals(
        (text_rows[position] for position in sorted(summary)), match.lookup, conventions, movements, "worksheet"
    )
    yield from movements
