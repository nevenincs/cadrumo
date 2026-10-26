"""Real synthetic Excel 97-2003 (``.xls``) bytes shared by workbook-import tests.

No maintained library writes BIFF8, so tests build the smallest workbook that
Excel and ``xlrd`` both accept: a globals substream with the fonts and cell
formats ``xlrd`` resolves cell types from, one substream per worksheet, and an
OLE2 compound document around the ``Workbook`` stream. Text cells are
``LABEL`` records, numbers ``NUMBER`` records, dates ``NUMBER`` records under
the built-in date format, and :class:`XlsFormula` cells real ``FORMULA``
records carrying a cached numeric result.
"""

from __future__ import annotations

import struct
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

__all__ = ["XlsFormula", "xls_workbook_bytes"]

_ENDOFCHAIN = 0xFFFFFFFE
_FREESECT = 0xFFFFFFFF
_FATSECT = 0xFFFFFFFD
_NOSTREAM = 0xFFFFFFFF
_SECTOR = 512
_MIN_REGULAR_STREAM = 4096
_GENERAL_XF = 15
_DATE_XF = 16
_EXCEL_EPOCH = datetime(1899, 12, 30)


@dataclass(frozen=True, slots=True)
class XlsFormula:
    """A formula cell whose cached result is ``cached``; the formula is the constant itself."""

    cached: int


def _record(code: int, payload: bytes) -> bytes:
    return struct.pack("<HH", code, len(payload)) + payload


def _bof(kind: int) -> bytes:
    return _record(0x0809, struct.pack("<HHHHII", 0x0600, kind, 0x0DBB, 0x07CC, 0, 0x06))


def _short_string(text: str, *, length_bytes: int) -> bytes:
    raw = text.encode("latin-1")
    return struct.pack("<B" if length_bytes == 1 else "<H", len(text)) + b"\x00" + raw


def _globals_head() -> bytes:
    fonts = b"".join(
        _record(
            0x0031,
            struct.pack("<HHHHHBBBB", 200, 0, 0x7FFF, 400, 0, 0, 0, 0, 0) + _short_string("Arial", length_bytes=1),
        )
        for _ in range(5)
    )
    style_xfs = b"".join(
        _record(0x00E0, struct.pack("<HHHBBBBIIH", 0, 0, 0xFFF5, 0x20, 0, 0, 0, 0, 0, 0x20C0)) for _ in range(15)
    )
    cell_xfs = b"".join(
        _record(0x00E0, struct.pack("<HHHBBBBIIH", 0, format_index, 0x0001, 0x20, 0, 0, 0, 0, 0, 0x20C0))
        for format_index in (0, 14)
    )
    return _bof(0x0005) + _record(0x0042, struct.pack("<H", 1200)) + fonts + style_xfs + cell_xfs


def _cell(row: int, column: int, value: object) -> bytes:
    if value is None:
        return b""
    if isinstance(value, XlsFormula):
        return _record(
            0x0006,
            struct.pack("<HHHd", row, column, _GENERAL_XF, float(value.cached))
            + struct.pack("<HIH", 0, 0, 3)
            + bytes((0x1E,))
            + struct.pack("<H", value.cached),
        )
    if isinstance(value, (date, datetime)):
        moment = value if isinstance(value, datetime) else datetime(value.year, value.month, value.day)
        serial = (moment - _EXCEL_EPOCH).total_seconds() / 86400
        return _record(0x0203, struct.pack("<HHHd", row, column, _DATE_XF, serial))
    if isinstance(value, (int, float, Decimal)) and not isinstance(value, bool):
        return _record(0x0203, struct.pack("<HHHd", row, column, _GENERAL_XF, float(value)))
    return _record(0x0204, struct.pack("<HHH", row, column, _GENERAL_XF) + _short_string(str(value), length_bytes=2))


def _worksheet(rows: Sequence[Sequence[object]]) -> bytes:
    width = max((len(row) for row in rows), default=0)
    body = _bof(0x0010) + _record(0x0200, struct.pack("<IIHHH", 0, len(rows), 0, width, 0))
    body += b"".join(
        _cell(row_index, column, value) for row_index, row in enumerate(rows) for column, value in enumerate(row)
    )
    return body + _record(0x000A, b"")


def _workbook_stream(sheets: Sequence[tuple[str, Sequence[Sequence[object]]]]) -> bytes:
    head = _globals_head()
    bodies = [_worksheet(rows) for _, rows in sheets]
    entries = [_short_string(name, length_bytes=1) for name, _ in sheets]
    offset = len(head) + sum(len(_record(0x0085, b"\x00" * 6 + entry)) for entry in entries) + len(_record(0x000A, b""))
    boundsheets = b""
    for entry, body in zip(entries, bodies, strict=True):
        boundsheets += _record(0x0085, struct.pack("<IBB", offset, 0, 0) + entry)
        offset += len(body)
    return head + boundsheets + _record(0x000A, b"") + b"".join(bodies)


def _compound_document(stream: bytes) -> bytes:
    padded_length = max(_MIN_REGULAR_STREAM, -(-len(stream) // _SECTOR) * _SECTOR)
    padded = stream.ljust(padded_length, b"\x00")
    data_sectors = padded_length // _SECTOR
    fat = [_FATSECT, _ENDOFCHAIN, *range(3, 2 + data_sectors), _ENDOFCHAIN]
    if len(fat) > _SECTOR // 4:
        raise ValueError("synthetic xls fixture exceeds one FAT sector")
    fat += [_FREESECT] * (_SECTOR // 4 - len(fat))
    header = (
        b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
        + b"\x00" * 16
        + struct.pack("<HHHHH", 0x003E, 0x0003, 0xFFFE, 9, 6)
        + b"\x00" * 6
        + struct.pack("<IIIIIIIII", 0, 1, 1, 0, _MIN_REGULAR_STREAM, _ENDOFCHAIN, 0, _ENDOFCHAIN, 0)
        + struct.pack("<109I", 0, *([_FREESECT] * 108))
    )

    def entry(name: str, kind: int, child: int, start: int, size: int) -> bytes:
        encoded = (name + "\x00").encode("utf-16-le") if name else b""
        return (
            encoded.ljust(64, b"\x00")
            + struct.pack("<HBB", len(encoded), kind, 1)
            + struct.pack("<III", _NOSTREAM, _NOSTREAM, child)
            + b"\x00" * 20
            + b"\x00" * 16
            + struct.pack("<III", start, size, 0)
        )

    directory = (
        entry("Root Entry", 5, 1, _ENDOFCHAIN, 0)
        + entry("Workbook", 2, _NOSTREAM, 2, padded_length)
        + entry("", 0, _NOSTREAM, 0, 0) * 2
    )
    return header + struct.pack(f"<{_SECTOR // 4}I", *fat) + directory + padded


def xls_workbook_bytes(sheets: Sequence[tuple[str, Sequence[Sequence[object]]]]) -> bytes:
    """Return a BIFF8 ``.xls`` workbook with one worksheet per ``(name, rows)`` entry.

    Cells may be ``None`` (absent), ``str``, a number, a ``date``/``datetime``
    (stored under the built-in date format), or :class:`XlsFormula`.
    """
    return _compound_document(_workbook_stream(sheets))
