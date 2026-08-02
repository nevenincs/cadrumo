"""Unit tests for the casilla-value spreadsheet parser."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import pytest
from openpyxl import Workbook, load_workbook

from .._action_errors import ModeloLocalObservationError
from .._local_observation_spreadsheet import parse_casilla_value_spreadsheet

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _write_xlsx_with_stale_formula_cache(path: Path) -> None:
    """Create a real workbook whose formula and cached amount contradict."""
    workbook = Workbook()
    sheet = workbook.active
    assert sheet is not None
    sheet.append(["casilla_code", "value"])
    sheet.append(["01", 1])
    workbook.save(path)
    workbook.close()

    worksheet_member = "xl/worksheets/sheet1.xml"
    original_cell = b'<c r="B2" t="n"><v>1</v></c>'
    formula_cell_with_stale_cache = b'<c r="B2"><f>1+1</f><v>9999</v></c>'
    with ZipFile(path) as source_archive:
        members = {member.filename: source_archive.read(member) for member in source_archive.infolist()}
    assert members[worksheet_member].count(original_cell) == 1
    members[worksheet_member] = members[worksheet_member].replace(original_cell, formula_cell_with_stale_cache)
    with ZipFile(path, mode="w", compression=ZIP_DEFLATED) as destination_archive:
        for filename, contents in members.items():
            destination_archive.writestr(filename, contents)


def test_parse_csv_with_header_row(tmp_path: Path) -> None:
    """A CSV with an explicit ``casilla_code,value`` header parses by column name."""
    path = tmp_path / "m130-2025q4.csv"
    path.write_text(
        "casilla_code,value\n01,1234.56\n03,789.10\n",
        encoding="utf-8",
    )

    values = parse_casilla_value_spreadsheet(path)

    assert values == {"01": Decimal("1234.56"), "03": Decimal("789.10")}


def test_parse_csv_positional_headerless(tmp_path: Path) -> None:
    """A headerless two-column CSV falls back to positional column mapping."""
    path = tmp_path / "sheet.csv"
    path.write_text("01,100\n02,200.5\n", encoding="utf-8")

    values = parse_casilla_value_spreadsheet(path)

    assert values == {"01": Decimal("100"), "02": Decimal("200.5")}


def test_parse_csv_with_alias_headers(tmp_path: Path) -> None:
    """Header aliases (casilla / valor) are recognised, case-insensitively."""
    path = tmp_path / "sheet.csv"
    path.write_text("Casilla,Valor\n05,10.00\n06,-3.25\n", encoding="utf-8")

    values = parse_casilla_value_spreadsheet(path)

    assert values == {"05": Decimal("10.00"), "06": Decimal("-3.25")}


def test_parse_xlsx_with_header_row(tmp_path: Path) -> None:
    """An XLSX workbook with a header row parses identically to CSV."""
    path = tmp_path / "sheet.xlsx"
    workbook = Workbook()
    sheet = workbook.active
    assert sheet is not None
    sheet.append(["casilla_code", "value"])
    sheet.append(["01", 1234.56])
    sheet.append(["03", 789.10])
    workbook.save(path)

    values = parse_casilla_value_spreadsheet(path)

    assert values == {"01": Decimal("1234.56"), "03": Decimal("789.1")}


def test_parse_xlsx_refuses_stale_formula_cache_before_value_materialisation(tmp_path: Path) -> None:
    """A cached amount that contradicts its formula cannot become prefill evidence."""
    path = tmp_path / "stale-formula.xlsx"
    _write_xlsx_with_stale_formula_cache(path)

    formula_workbook = load_workbook(filename=path, read_only=True, data_only=False)
    cached_workbook = load_workbook(filename=path, read_only=True, data_only=True)
    try:
        formula_sheet = formula_workbook.active
        cached_sheet = cached_workbook.active
        assert formula_sheet is not None
        assert cached_sheet is not None
        assert formula_sheet["B2"].value == "=1+1"
        assert cached_sheet["B2"].value == 9999
    finally:
        formula_workbook.close()
        cached_workbook.close()

    with pytest.raises(ModeloLocalObservationError, match=r"formula cell at row 2, column 2") as exc_info:
        parse_casilla_value_spreadsheet(path)

    assert "formula cached values are not accepted" in str(exc_info.value)
    assert exc_info.value.context == {"path": str(path), "row": "2", "column": "2"}


def test_parse_csv_rejects_duplicate_casilla_rows_before_last_writer_wins(tmp_path: Path) -> None:
    """Two amounts for one casilla are ambiguous; row order cannot select one."""
    path = tmp_path / "duplicate.csv"
    path.write_text("casilla_code,value\n01,1000.00\n01,1.00\n", encoding="utf-8")

    with pytest.raises(ModeloLocalObservationError) as exc_info:
        parse_casilla_value_spreadsheet(path)

    assert "row 2: duplicate casilla_code '01' (first declared on row 1)" in str(exc_info.value)
    assert exc_info.value.context == {"path": str(path), "malformed_row_count": "1"}


def test_parse_xlsx_rejects_duplicate_casilla_rows_even_when_values_match(tmp_path: Path) -> None:
    """Coordinate uniqueness applies independently of coincidentally equal values."""
    path = tmp_path / "duplicate.xlsx"
    workbook = Workbook()
    sheet = workbook.active
    assert sheet is not None
    sheet.append(["casilla_code", "value"])
    sheet.append(["01", 1000])
    sheet.append(["01", 1000])
    workbook.save(path)

    with pytest.raises(ModeloLocalObservationError) as exc_info:
        parse_casilla_value_spreadsheet(path)

    assert "row 2: duplicate casilla_code '01' (first declared on row 1)" in str(exc_info.value)
    assert exc_info.value.context == {"path": str(path), "malformed_row_count": "1"}


def test_parse_rejects_non_numeric_value(tmp_path: Path) -> None:
    """A non-numeric value raises, naming the offending row and casilla."""
    path = tmp_path / "sheet.csv"
    path.write_text("casilla_code,value\n01,not-a-number\n", encoding="utf-8")

    with pytest.raises(ModeloLocalObservationError, match="not-a-number"):
        parse_casilla_value_spreadsheet(path)


def test_parse_rejects_incomplete_row(tmp_path: Path) -> None:
    """A row with a casilla code but no value raises, naming the row."""
    path = tmp_path / "sheet.csv"
    path.write_text("casilla_code,value\n01,\n02,50\n", encoding="utf-8")

    with pytest.raises(ModeloLocalObservationError, match="incomplete"):
        parse_casilla_value_spreadsheet(path)


def test_parse_rejects_missing_file(tmp_path: Path) -> None:
    """A nonexistent path raises a typed refusal rather than an OS error."""
    with pytest.raises(ModeloLocalObservationError, match="does not exist"):
        parse_casilla_value_spreadsheet(tmp_path / "missing.csv")


def test_parse_rejects_empty_file(tmp_path: Path) -> None:
    """A spreadsheet with no rows at all raises."""
    path = tmp_path / "sheet.csv"
    path.write_text("", encoding="utf-8")

    with pytest.raises(ModeloLocalObservationError, match="no rows"):
        parse_casilla_value_spreadsheet(path)


def test_parse_rejects_header_only_file(tmp_path: Path) -> None:
    """A spreadsheet carrying only a header row (no data) raises."""
    path = tmp_path / "sheet.csv"
    path.write_text("casilla_code,value\n", encoding="utf-8")

    with pytest.raises(ModeloLocalObservationError, match="no usable"):
        parse_casilla_value_spreadsheet(path)


def test_parse_skips_blank_rows(tmp_path: Path) -> None:
    """Fully-blank rows between data rows are skipped, not treated as malformed."""
    path = tmp_path / "sheet.csv"
    path.write_text("casilla_code,value\n01,100\n\n02,200\n", encoding="utf-8")

    values = parse_casilla_value_spreadsheet(path)

    assert values == {"01": Decimal("100"), "02": Decimal("200")}


def test_parse_accepts_quoted_comma_decimal_separator(tmp_path: Path) -> None:
    """A quoted Spanish comma-decimal value (e.g. ``"1234,56"``) is coerced correctly."""
    path = tmp_path / "sheet.csv"
    path.write_text('casilla_code,value\n01,"1234,56"\n', encoding="utf-8")

    values = parse_casilla_value_spreadsheet(path)

    assert values == {"01": Decimal("1234.56")}


def test_parse_accepts_european_thousands_and_decimal_separators(tmp_path: Path) -> None:
    """A Spanish-formatted amount remains its full amount, not a malformed Decimal."""
    path = tmp_path / "sheet.csv"
    path.write_text('casilla_code,value\n01,"1.234,56"\n', encoding="utf-8")

    values = parse_casilla_value_spreadsheet(path)

    assert values == {"01": Decimal("1234.56")}


@pytest.mark.parametrize("raw_value", ("NaN", "Infinity", "-Infinity"))
def test_parse_rejects_non_finite_value(tmp_path: Path, raw_value: str) -> None:
    """Decimal spellings that evade numeric parsing cannot enter a casilla observation."""
    path = tmp_path / "sheet.csv"
    path.write_text(f"casilla_code,value\n01,{raw_value}\n", encoding="utf-8")

    with pytest.raises(ModeloLocalObservationError, match="must be finite"):
        parse_casilla_value_spreadsheet(path)
