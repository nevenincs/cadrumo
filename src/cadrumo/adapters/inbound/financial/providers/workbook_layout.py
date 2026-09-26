"""Bank-layout matching and row parsing shared by the spreadsheet statement providers.

A spreadsheet statement is a grid of typed cells whatever file format carries
it. Once each format's reader has produced that grid, choosing the worksheet
and header row, and turning each data row into a
:class:`~adapters.inbound.financial.providers.base.ParsedLedgerRow`, is the same
work. It is done here once, against the bank-layout catalogue and parse rules of
:mod:`adapters.inbound.financial.providers.csv`, so ``.xlsx`` and ``.xls``
exports of the same bank read identically.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator, Sequence
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
    CSV_LAYOUTS,
    CsvBankLayout,
    build_provider_row,
    header_lookup,
    layout_score,
    parse_tabular_transaction_row,
    row_is_blank,
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

#: The fewest matching column aliases that identify a known bank layout.
MIN_LAYOUT_SCORE = 3


@dataclass(frozen=True, slots=True)
class WorksheetLayoutMatch:
    """The best bank layout one worksheet's opening rows satisfy.

    Attributes:
        score: Number of the layout's column aliases the header row matched.
        header_index: 0-based index of the header row in the worksheet.
        headers: The header row's cell text.
        lookup: Lower-cased header text mapped back to the header as written.
        layout: The matched bank layout.
    """

    score: int
    header_index: int
    headers: list[str]
    lookup: dict[str, str]
    layout: CsvBankLayout


def best_layout_match(sample_rows: Iterable[Sequence[object]]) -> WorksheetLayoutMatch | None:
    """Score each non-blank row of ``sample_rows`` against every bank layout and keep the best."""
    best: WorksheetLayoutMatch | None = None
    for index, row in enumerate(sample_rows):
        texts = [archive_cell_text(cell) for cell in row]
        if not any(text.strip() for text in texts):
            continue
        lookup = header_lookup(texts)
        for layout in CSV_LAYOUTS:
            score = layout_score(lookup, layout)
            if best is None or score > best.score:
                best = WorksheetLayoutMatch(
                    score=score, header_index=index, headers=texts, lookup=lookup, layout=layout
                )
    return best


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
        InvalidFinancialSourceError: A data row cannot be parsed under the
            matched layout.
    """
    headers = match.headers
    for source_row_index, row in enumerate(rows[match.header_index + 1 :], start=match.header_index + 2):
        raw_fields = {
            header: archive_cell_text(row[index]) if index < len(row) else "" for index, header in enumerate(headers)
        }
        if row_is_blank(raw_fields):
            continue
        typed_fields = {header: row[index] if index < len(row) else "" for index, header in enumerate(headers)}
        try:
            parsed = parse_tabular_transaction_row(
                layout=match.layout,
                lookup=match.lookup,
                raw_fields=raw_fields,
                typed_fields=typed_fields,
                synthetic_provider_name=f"{match.layout.bank_name}-{sheet_name}",
                source_sha256=source_sha256,
                source_row_index=source_row_index,
                required_field_context="worksheet row",
            )
        except (ValueError, FinancialValidationError) as exc:
            _logger.warning(
                "%s: parse error row=%d file=%s",
                provider.name,
                source_row_index,
                path.name,
                exc_info=True,
            )
            raise InvalidFinancialSourceError(
                f"worksheet row {source_row_index} could not be parsed: {exc}",
            ) from exc
        yield build_provider_row(
            provider=provider,
            path=path,
            source_sha256=source_sha256,
            source_row_index=source_row_index,
            parsed=parsed,
            raw_fields=raw_fields,
        )
