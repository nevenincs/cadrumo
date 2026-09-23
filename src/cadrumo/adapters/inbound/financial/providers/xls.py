"""Legacy Excel 97-2003 (``.xls``) financial provider.

Implements :class:`XlsProvider`, the ``.xls`` counterpart of
:class:`~adapters.inbound.financial.providers.xlsx.XlsxProvider`. The workbook
is read by :func:`~core.legacy_workbook.read_legacy_workbook`, which marks
formula cells the way ``openpyxl`` does, and the worksheet and header row are
chosen and parsed by :mod:`adapters.inbound.financial.providers.workbook_layout`.
An ``.xls`` and an ``.xlsx`` export of the same bank statement therefore select
the same layout, refuse the same formula cells and store the same worksheet
row numbers as provenance.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import override

from .....core.external_constants import XLS_EXTENSION
from .....core.legacy_workbook import LegacyWorksheet, read_legacy_workbook
from .....core.tabular import TabularSourceError
from .....core.workbook import FORMULA_CELL_REFUSAL, first_formula_cell_column
from .....domain.transactions.raw_transaction import SourceFormat
from .base import (
    FinancialProvider,
    InvalidFinancialSourceError,
    ParsedLedgerRow,
    ProviderValidation,
    default_currency,
)
from .csv import find_column
from .workbook_layout import (
    LAYOUT_SAMPLE_ROWS,
    MIN_LAYOUT_SCORE,
    WorksheetLayoutMatch,
    best_layout_match,
    iter_worksheet_rows,
)

__all__ = ["XlsProvider"]


@dataclass(frozen=True, slots=True)
class _SelectedWorksheet:
    """The worksheet whose opening rows best match a known bank layout."""

    name: str
    rows: tuple[tuple[object, ...], ...]
    match: WorksheetLayoutMatch


class XlsProvider(FinancialProvider):
    """Ingest raw transactions from legacy ``.xls`` bank statement exports.

    Every worksheet's first rows are scored against the bank-layout catalogue,
    and the best-scoring worksheet and header row are read. A formula cell in a
    data row below the header refuses the source rather than trusting its
    cached value.
    """

    name = "XLS provider"
    supported_extensions = frozenset({XLS_EXTENSION})
    source_format = SourceFormat.XLS
    # The fixtures are synthetic workbooks generated from the same published
    # bank export column schemas as the XLSX corpus; no operator .xls specimen
    # has been parsed yet.
    verification_source = "synthetic_from_bank_published_text"
    provisional_pending_specimen = True

    @override
    def validate_source(self, path: Path) -> ProviderValidation:
        """Validate that ``path`` is a readable ``.xls`` workbook with a known bank layout and data rows."""
        try:
            selected = self._select_worksheet(path)
        except InvalidFinancialSourceError as exc:
            return ProviderValidation(is_valid=False, warnings=(str(exc),))
        match = selected.match
        if len(selected.rows) <= match.header_index + 1:
            return ProviderValidation(
                is_valid=False,
                warnings=(f"{match.layout.bank_name} worksheet has no data rows after the header",),
            )
        warnings: tuple[str, ...] = ()
        if not find_column(match.lookup, match.layout.columns.currency):
            warnings = (
                f"{match.layout.bank_name} worksheet has no currency column; falling back to {default_currency()}",
            )
        return ProviderValidation(
            is_valid=True,
            warnings=warnings,
            detected_encoding=None,
            detected_dialect=f"worksheet={selected.name},header_row={match.header_index + 1}",
        )

    @override
    def ingest(self, path: Path) -> Iterator[ParsedLedgerRow]:
        """Yield :class:`ParsedLedgerRow` records (magnitude + direction) from the best-matching worksheet."""
        source_sha256 = self._compute_sha256(self._read_source_bytes(path))
        selected = self._select_worksheet(path)
        yield from iter_worksheet_rows(
            provider=self,
            path=path,
            source_sha256=source_sha256,
            rows=selected.rows,
            match=selected.match,
            sheet_name=selected.name,
        )

    def _select_worksheet(self, path: Path) -> _SelectedWorksheet:
        """Read the workbook, choose its best worksheet and refuse formula cells in its data rows."""
        try:
            worksheets = read_legacy_workbook(self._read_source_bytes(path))
        except TabularSourceError as exc:
            raise InvalidFinancialSourceError(f"could not open legacy workbook {path.name}: {exc}") from exc
        best: tuple[LegacyWorksheet, WorksheetLayoutMatch] | None = None
        for worksheet in worksheets:
            candidate = best_layout_match([cell.value for cell in row] for row in worksheet.rows[:LAYOUT_SAMPLE_ROWS])
            if candidate is not None and (best is None or candidate.score > best[1].score):
                best = (worksheet, candidate)
        if best is None or best[1].score < MIN_LAYOUT_SCORE:
            raise InvalidFinancialSourceError("Workbook does not contain a supported bank-statement header row")
        worksheet, match = best
        _refuse_formula_data_rows(worksheet, header_index=match.header_index)
        return _SelectedWorksheet(
            name=worksheet.name,
            rows=tuple(tuple(cell.value for cell in row) for row in worksheet.rows),
            match=match,
        )


def _refuse_formula_data_rows(worksheet: LegacyWorksheet, *, header_index: int) -> None:
    """Refuse a formula cell anywhere below the header, as the ``.xlsx`` provider does."""
    for row_number, cells in enumerate(worksheet.rows, start=1):
        if row_number <= header_index + 1:
            continue
        column_number = first_formula_cell_column(cells)
        if column_number is not None:
            raise InvalidFinancialSourceError(
                f"worksheet {worksheet.name!r} contains formula cell at row {row_number}, "
                f"column {column_number}; {FORMULA_CELL_REFUSAL}",
            )
