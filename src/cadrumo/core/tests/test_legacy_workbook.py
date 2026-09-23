"""The legacy ``.xls`` reader marks formula cells and refuses what it cannot scan."""

from __future__ import annotations

from datetime import date, datetime

import pytest

from ...tests.xls_fixtures import XlsFormula, xls_workbook_bytes
from ..legacy_workbook import read_legacy_workbook
from ..tabular import TabularSourceError
from ..workbook import first_formula_cell_column

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_cells_carry_openpyxl_values_and_type_codes() -> None:
    (sheet,) = read_legacy_workbook(
        xls_workbook_bytes([("Book", [["label", 12.5, date(2025, 3, 11)], [None, XlsFormula(7), "tail"]])])
    )

    assert sheet.name == "Book"
    assert [[(cell.value, cell.data_type) for cell in row] for row in sheet.rows] == [
        [("label", "s"), (12.5, "n"), (datetime(2025, 3, 11), "n")],
        [(None, "n"), (7.0, "f"), ("tail", "s")],
    ]


def test_formula_cells_are_attributed_to_their_own_worksheet() -> None:
    first, second = read_legacy_workbook(
        xls_workbook_bytes([("First", [["a", "b"], ["c", "d"]]), ("Second", [["x", XlsFormula(3)]])])
    )

    assert [first_formula_cell_column(row) for row in first.rows] == [None, None]
    assert [first_formula_cell_column(row) for row in second.rows] == [2]


def test_bytes_that_are_not_an_ole2_workbook_are_refused() -> None:
    with pytest.raises(TabularSourceError, match="not an OLE2 compound document"):
        read_legacy_workbook(b"date,amount\n2025-03-11,1.00\n")


def test_a_truncated_workbook_is_refused_without_printing_reader_warnings(capsys: pytest.CaptureFixture[str]) -> None:
    truncated = xls_workbook_bytes([("Book", [["a"]])])[:600]

    with pytest.raises(TabularSourceError, match="could not be read"):
        read_legacy_workbook(truncated)

    assert capsys.readouterr().out == ""
