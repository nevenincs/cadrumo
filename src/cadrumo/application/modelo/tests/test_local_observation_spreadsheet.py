"""Unit tests for the casilla-value spreadsheet parser."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest
from openpyxl import Workbook

from .._action_errors import ModeloLocalObservationError
from .._local_observation_spreadsheet import parse_casilla_value_spreadsheet

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


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
