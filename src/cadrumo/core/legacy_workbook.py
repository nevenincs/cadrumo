"""Read legacy Excel 97-2003 (``.xls``) workbooks under the shared formula policy.

The BIFF8 reader returns only the result a formula last computed: a formula
cell arrives as an ordinary number or string, with no trace of the formula
itself. Reading ``.xls`` that way would admit exactly the stale cached figure
:mod:`core.workbook` refuses for ``.xlsx``. So this module walks the
workbook's own record stream as well and marks every cell a ``FORMULA``
record defines, giving each cell the same ``data_type`` code ``openpyxl``
uses (``"f"`` for a formula). The workbook readers can then apply
:func:`~core.workbook.first_formula_cell_column` to either format unchanged.

Only BIFF8, the Excel 97-2003 format stored in an OLE2 compound document,
is read. Earlier BIFF versions and bare record streams are refused, because
their sheet and record layout is not what the formula scan understands, and
a scan that silently found nothing would defeat the policy.

``xlrd`` is imported lazily so resolving this module never pulls a
spreadsheet engine into a layer that only needs its types.
"""

from __future__ import annotations

import io
import struct
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

from .tabular import TabularSourceError

if TYPE_CHECKING:
    from xlrd.book import Book
    from xlrd.sheet import Sheet

__all__ = [
    "LegacyCell",
    "LegacyWorksheet",
    "read_legacy_workbook",
]

_OLE2_SIGNATURE: Final[bytes] = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
_BIFF8_VERSION: Final[int] = 80
_RECORD_BOF: Final[int] = 0x0809
_RECORD_EOF: Final[int] = 0x000A
_RECORD_BOUNDSHEET: Final[int] = 0x0085
_RECORD_FORMULA: Final[int] = 0x0006
_BOUNDSHEET_WORKSHEET: Final[int] = 0x00
_RECORD_HEADER = struct.Struct("<HH")


@dataclass(frozen=True, slots=True)
class LegacyCell:
    """One ``.xls`` cell value with the ``openpyxl`` type code the formula policy reads.

    Attributes:
        value: ``None`` for an empty cell, ``str`` for text, ``float`` for a
            number, ``datetime`` for a date-formatted number, ``bool`` for a
            boolean, and the error literal (for example ``#N/A``) for an error
            cell, matching what ``openpyxl`` yields for the same ``.xlsx`` cell.
        data_type: ``"f"`` when a ``FORMULA`` record defines the cell,
            otherwise ``"n"`` (number, date or empty), ``"s"`` (text),
            ``"b"`` (boolean) or ``"e"`` (error).
    """

    value: object
    data_type: str


@dataclass(frozen=True, slots=True)
class LegacyWorksheet:
    """One worksheet of a legacy workbook, in row order.

    Attributes:
        name: The worksheet's tab name.
        rows: Every row up to the last used one, each padded to the sheet's
            used width, so ``rows[i][j]`` is 0-based row ``i``, column ``j``.
    """

    name: str
    rows: tuple[tuple[LegacyCell, ...], ...]


def read_legacy_workbook(source_bytes: bytes) -> tuple[LegacyWorksheet, ...]:
    """Read every worksheet of a BIFF8 workbook with formula cells marked.

    Args:
        source_bytes: The complete ``.xls`` file.

    Returns:
        The worksheets in workbook order, the same order Excel shows the tabs.

    Raises:
        TabularSourceError: The bytes are not an OLE2 compound document
            holding a BIFF8 workbook, the workbook cannot be read, or its
            record stream does not describe the same worksheets ``xlrd`` read.
    """
    import xlrd
    from xlrd.biffh import XLRDError
    from xlrd.compdoc import CompDoc, CompDocError

    if not source_bytes.startswith(_OLE2_SIGNATURE):
        raise TabularSourceError("legacy workbook is not an OLE2 compound document")
    try:
        # xlrd reports structural warnings by printing them; a CLI whose stdout
        # carries a JSON envelope must never receive them.
        book = xlrd.open_workbook(file_contents=source_bytes, on_demand=False, logfile=io.StringIO())
        stream = CompDoc(source_bytes).get_named_stream("Workbook")
    except (XLRDError, CompDocError, struct.error, ValueError, IndexError, KeyError) as exc:
        raise TabularSourceError(f"legacy workbook could not be read: {type(exc).__name__}") from exc
    if book.biff_version != _BIFF8_VERSION or stream is None:
        raise TabularSourceError("only Excel 97-2003 (BIFF8) legacy workbooks are read")
    formula_cells = _formula_cells_by_worksheet(stream)
    if len(formula_cells) != book.nsheets:
        raise TabularSourceError("legacy workbook record stream does not match its worksheets")
    return tuple(_worksheet(book, book.sheet_by_index(index), formula_cells[index]) for index in range(book.nsheets))


def _records(stream: bytes, offset: int) -> list[tuple[int, int, bytes]]:
    """Return ``(code, offset, payload)`` for one BOF..EOF substream, nested substreams included."""
    records: list[tuple[int, int, bytes]] = []
    depth = 0
    position = offset
    while True:
        if position + _RECORD_HEADER.size > len(stream):
            raise TabularSourceError("legacy workbook record stream ends inside a substream")
        code, length = _RECORD_HEADER.unpack_from(stream, position)
        payload_start = position + _RECORD_HEADER.size
        if payload_start + length > len(stream):
            raise TabularSourceError("legacy workbook record overruns its stream")
        if position == offset and code != _RECORD_BOF:
            raise TabularSourceError("legacy workbook substream does not start with BOF")
        records.append((code, position, stream[payload_start : payload_start + length]))
        position = payload_start + length
        if code == _RECORD_BOF:
            depth += 1
        elif code == _RECORD_EOF:
            depth -= 1
            if depth == 0:
                return records


def _formula_cells_by_worksheet(stream: bytes) -> list[frozenset[tuple[int, int]]]:
    """Locate each worksheet substream from its BOUNDSHEET entry and collect its FORMULA cells.

    ``xlrd`` keeps only BOUNDSHEET entries of type worksheet, in order, so the
    same filter here yields the same sheet numbering. Only records at the
    worksheet's own nesting level count: a chart embedded in a sheet carries
    its own BOF..EOF substream, whose records are not the sheet's cells.
    """
    worksheet_offsets = [
        struct.unpack_from("<I", payload, 0)[0]
        for code, _position, payload in _records(stream, 0)
        if code == _RECORD_BOUNDSHEET and len(payload) >= 6 and payload[5] == _BOUNDSHEET_WORKSHEET
    ]
    sheets: list[frozenset[tuple[int, int]]] = []
    for offset in worksheet_offsets:
        cells: set[tuple[int, int]] = set()
        depth = 0
        for code, _position, payload in _records(stream, offset):
            if code == _RECORD_BOF:
                depth += 1
            elif code == _RECORD_EOF:
                depth -= 1
            elif code == _RECORD_FORMULA and depth == 1:
                if len(payload) < 4:
                    raise TabularSourceError("legacy workbook FORMULA record is truncated")
                row, column = struct.unpack_from("<HH", payload, 0)
                cells.add((row, column))
        sheets.append(frozenset(cells))
    return sheets


def _worksheet(book: Book, sheet: Sheet, formula_cells: frozenset[tuple[int, int]]) -> LegacyWorksheet:
    return LegacyWorksheet(
        name=sheet.name,
        rows=tuple(
            tuple(_cell(book, sheet, row, column, formula_cells) for column in range(sheet.ncols))
            for row in range(sheet.nrows)
        ),
    )


def _cell(book: Book, sheet: Sheet, row: int, column: int, formula_cells: frozenset[tuple[int, int]]) -> LegacyCell:
    import xlrd
    from xlrd.xldate import XLDateError, xldate_as_datetime

    cell_type = sheet.cell_type(row, column)
    value: object = sheet.cell_value(row, column)
    if cell_type in {xlrd.XL_CELL_EMPTY, xlrd.XL_CELL_BLANK}:
        value, data_type = None, "n"
    elif cell_type == xlrd.XL_CELL_TEXT:
        data_type = "s"
    elif cell_type == xlrd.XL_CELL_DATE:
        try:
            value = xldate_as_datetime(float(sheet.cell_value(row, column)), book.datemode)
        except XLDateError as exc:
            raise TabularSourceError(
                f"legacy workbook date cell at row {row + 1}, column {column + 1} is out of range"
            ) from exc
        data_type = "n"
    elif cell_type == xlrd.XL_CELL_BOOLEAN:
        value, data_type = bool(value), "b"
    elif cell_type == xlrd.XL_CELL_ERROR:
        value, data_type = xlrd.error_text_from_code.get(int(sheet.cell_value(row, column)), "#ERR!"), "e"
    else:
        data_type = "n"
    return LegacyCell(value=value, data_type="f" if (row, column) in formula_cells else data_type)
