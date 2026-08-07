"""Dialect normalization against the bundled operator tabular exports.

The nine bundled exports span every axis normalization must detect rather than
assume: four delimiters, both decimal conventions, a UTF-8 BOM, metadata
preambles up to seven lines deep, appended summary rows, and a newline inside a
quoted field. The baseline they replace is measured, not asserted — driving the
product's statement auto-detection over this same corpus imported one file.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ...tests import FIXTURES_DIR
from ..tabular import TabularSourceError, normalize_tabular_bytes, normalize_tabular_text

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_FIXTURES = FIXTURES_DIR / "financial" / "tabular-dialects"

#: Every bundled operator export, with the dialect facts each one exists to
#: exercise. All nine must normalize; the baseline was one importing.
_BUNDLED_EXPORTS: tuple[tuple[str, str, str, int, int, int, int], ...] = (
    # (filename, delimiter, decimal, columns, header_line, data_rows, summary_rows)
    ("bank_bbva_2026Q1.csv", ";", ",", 8, 6, 12, 0),
    ("bank_caixa_excel_export_2026Q1.csv", ";", ",", 5, 4, 12, 1),
    ("bank_neobank_2026Q1.csv", ",", ".", 8, 1, 12, 0),
    ("bank_statement_2026Q1_Q2.csv", ";", ",", 5, 9, 12, 0),
    ("expenses_app_export_2026.csv", ",", ".", 10, 1, 5, 0),
    ("ledger_erp_export_2026Q1.tsv", "\t", ",", 7, 1, 12, 0),
    ("libro_facturas_expedidas_2025_2026.csv", ",", ".", 10, 1, 8, 0),
    ("libro_facturas_recibidas_2025_2026.csv", "\t", ",", 10, 1, 10, 0),
    ("pos_zreport_20260514.txt", "|", ",", 8, 3, 5, 1),
)


def _bundled_paths() -> tuple[Path, ...]:
    return tuple(_FIXTURES / name for name, *_ in _BUNDLED_EXPORTS)


def test_every_bundled_export_normalizes() -> None:
    """All nine bundled operator exports must resolve into a typed table."""
    for path in _bundled_paths():
        table = normalize_tabular_bytes(path.read_bytes())
        assert table.rows, path.name
        assert table.headers, path.name


@pytest.mark.parametrize(
    ("name", "delimiter", "decimal_separator", "columns", "header_line", "data_rows", "summary_rows"),
    _BUNDLED_EXPORTS,
    ids=[entry[0] for entry in _BUNDLED_EXPORTS],
)
def test_bundled_export_dialect_axes(
    name: str,
    delimiter: str,
    decimal_separator: str,
    columns: int,
    header_line: int,
    data_rows: int,
    summary_rows: int,
) -> None:
    """Each export's delimiter, decimal convention and structure must be detected."""
    table = normalize_tabular_bytes((_FIXTURES / name).read_bytes())
    assert table.dialect.delimiter == delimiter, name
    assert table.dialect.decimal_separator == decimal_separator, name
    assert table.dialect.column_count == columns, name
    assert table.dialect.header_line_number == header_line, name
    assert len(table.rows) == data_rows, name
    assert len(table.summary_rows) == summary_rows, name


def test_utf8_bom_export_decodes_without_a_bom_in_the_header() -> None:
    """A BOM-prefixed export decodes as utf-8-sig, so the first header is clean.

    ``cp1252`` and ``iso-8859-1`` decode any byte sequence at all, so a chain
    reaching them ahead of the BOM check would mojibake this file silently
    rather than fail over to the right codec.
    """
    path = _FIXTURES / "libro_facturas_expedidas_2025_2026.csv"
    assert path.read_bytes().startswith(b"\xef\xbb\xbf")
    table = normalize_tabular_bytes(path.read_bytes())
    assert table.dialect.encoding == "utf-8-sig"
    assert table.headers[0] == "fecha_expedicion"
    assert "﻿" not in table.headers[0]


def test_preamble_rows_are_kept_out_of_the_data_and_reported() -> None:
    """A seven-line metadata preamble is separated from the movements, not read as one."""
    table = normalize_tabular_bytes((_FIXTURES / "bank_statement_2026Q1_Q2.csv").read_bytes())
    assert len(table.preamble) == 7
    assert table.preamble[0].cells[0] == "Banco Peninsular, S.A."
    assert any(notice.code == "preamble_skipped" for notice in table.notices)
    assert all("Banco Peninsular" not in cell for row in table.rows for cell in row.cells)


def test_summary_row_is_excluded_from_movements_and_reported() -> None:
    """An appended ``TOTAL`` row is not a movement, and the operator is told so.

    This is the row that broke the measured baseline: the CaixaBank export
    reached the exact CSV provider and died parsing ``TOTAL`` as a date.
    """
    table = normalize_tabular_bytes((_FIXTURES / "bank_caixa_excel_export_2026Q1.csv").read_bytes())
    assert [row.cells[0] for row in table.summary_rows] == ["TOTAL"]
    assert all(row.cells[0] != "TOTAL" for row in table.rows)
    excluded = [notice for notice in table.notices if notice.code == "summary_row_excluded"]
    assert len(excluded) == 1
    assert excluded[0].source_line_number == table.summary_rows[0].source_line_number


def test_movement_rows_survive_alongside_the_summary_row() -> None:
    """Positive control: excluding the summary row must not cost any movement.

    Without this, a normalizer that dropped the whole data region would satisfy
    the exclusion assertion above for entirely the wrong reason.
    """
    table = normalize_tabular_bytes((_FIXTURES / "bank_caixa_excel_export_2026Q1.csv").read_bytes())
    assert len(table.rows) == 12
    assert table.rows[0].cells[0] == "08/01/2026"
    assert table.rows[-1].cells[0] == "17/02/2026"


def test_newline_inside_a_quoted_field_is_one_row() -> None:
    """A quoted embedded newline stays inside its cell instead of splitting the row."""
    table = normalize_tabular_bytes((_FIXTURES / "expenses_app_export_2026.csv").read_bytes())
    assert len(table.rows) == 5
    notes = [cell for row in table.rows for cell in row.cells if "\n" in cell]
    assert notes == ["Comida de trabajo\ncon cliente Berrocal"]


def test_printed_decimal_forms_are_preserved_verbatim() -> None:
    """Detecting the convention must not rewrite the value it was detected from."""
    table = normalize_tabular_bytes((_FIXTURES / "bank_bbva_2026Q1.csv").read_bytes())
    assert table.dialect.decimal_separator == ","
    amounts = [row.cells[4] for row in table.rows]
    assert "-1.500,00" in amounts
    assert all("1500.00" not in cell for cell in amounts)


def test_ragged_row_is_carried_and_reported_not_dropped() -> None:
    """A row of the wrong width is imported with a notice; the file is never refused whole."""
    source = "Fecha;Concepto;Importe\n01/02/2026;Compra;-10,00\n02/02/2026;Corta\n"
    table = normalize_tabular_text(source, encoding="utf-8")
    assert len(table.rows) == 2
    ragged = [notice for notice in table.notices if notice.code == "ragged_row"]
    assert len(ragged) == 1
    assert ragged[0].source_line_number == 3


def test_source_with_no_delimited_rectangle_refuses() -> None:
    """A file carrying no table at all is refused rather than invented into one."""
    with pytest.raises(TabularSourceError, match="no delimited rectangle"):
        normalize_tabular_text("just one line of prose\nand another\n", encoding="utf-8")


def test_non_utf8_export_decodes_through_the_fallback_and_reports_it() -> None:
    """A cp1252 export normalizes, and the operator is told UTF-8 was not the codec.

    ``iso-8859-1`` maps all 256 byte values, so the tail of the fallback chain
    always succeeds and no real source is undecodable. That makes the reported
    fallback the only signal that the preferred codec did not fit, which is why
    the notice is asserted rather than treated as incidental.
    """
    source = "Fecha;Concepto;Importe\n01/02/2026;Café Aranda, gestión;-10,50\n"
    table = normalize_tabular_bytes(source.encode("cp1252"))
    assert table.dialect.encoding in {"cp1252", "iso-8859-1"}
    assert len(table.rows) == 1
    assert any(notice.code == "encoding_fallback" for notice in table.notices)


def test_utf8_export_reports_no_encoding_fallback() -> None:
    """Positive control: a UTF-8 source must not raise the fallback notice.

    Without this, a normalizer reporting the fallback unconditionally would
    satisfy the assertion above while telling the operator nothing.
    """
    source = "Fecha;Concepto;Importe\n01/02/2026;Café Aranda, gestión;-10,50\n"
    table = normalize_tabular_bytes(source.encode("utf-8"))
    assert table.dialect.encoding == "utf-8"
    assert table.rows[0].cells[1] == "Café Aranda, gestión"
    assert not any(notice.code == "encoding_fallback" for notice in table.notices)
