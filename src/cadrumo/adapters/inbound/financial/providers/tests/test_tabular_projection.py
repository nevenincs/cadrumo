"""Projection copies cells; it never touches a value.

The central guarantee of the tabular lane is that deciding what a column means
may be a judgement, while moving a value is not. These tests assert that as
**byte** equality between a projected value and its source cell. Semantic
equality would be the wrong property: a projection that normalized
``1.234,56`` into ``1234.56`` satisfies "equal after normalization" while
committing exactly the defect the guarantee exists to prevent.
"""

from __future__ import annotations

import csv
import io
import itertools

import pytest

from ......core.field_role import FieldRole
from ......core.tabular import normalize_tabular_bytes, normalize_tabular_text
from ......tests import FIXTURES_DIR
from .._tabular_projection import ColumnRoleMapping, project_table

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]

_FIXTURES = FIXTURES_DIR / "financial" / "tabular-dialects"

_BUNDLED_EXPORTS = (
    "bank_bbva_2026Q1.csv",
    "bank_caixa_excel_export_2026Q1.csv",
    "bank_neobank_2026Q1.csv",
    "bank_statement_2026Q1_Q2.csv",
    "expenses_app_export_2026.csv",
    "ledger_erp_export_2026Q1.tsv",
    "libro_facturas_expedidas_2025_2026.csv",
    "libro_facturas_recibidas_2025_2026.csv",
    "pos_zreport_20260514.txt",
)

#: Cell shapes a projection would be tempted to "tidy". Every one of these must
#: survive the copy byte for byte: European and English decimals, an ambiguous
#: thousands token, a currency symbol, accounting parentheses, a trailing
#: minus, surrounding whitespace, an embedded quote and an embedded newline.
_ADVERSARIAL_CELLS: tuple[str, ...] = (
    "1.234,56",
    "1234.56",
    "1.234",
    "-469,52 EUR",
    "(902,79)",
    "141,23-",
    "  espacio  ",
    'con "nota" entre comillas',
    "dos\nlineas",
    "0,00",
    "20260108",
    "08/01/2026",
    "",
    "ñÁçüö",
)

_ALL_ROLES = tuple(role for role in FieldRole if role is not FieldRole.UNMAPPED)


def _mapping_for(column_count: int) -> ColumnRoleMapping:
    """Map every column to a distinct real role, cycling the vocabulary as needed."""
    roles = tuple(itertools.islice(itertools.cycle(_ALL_ROLES), column_count))
    return ColumnRoleMapping(roles=roles)


@pytest.mark.parametrize("name", _BUNDLED_EXPORTS)
def test_projected_values_are_byte_equal_to_source_cells(name: str) -> None:
    """Every projected value must be byte-identical to the cell it came from."""
    table = normalize_tabular_bytes((_FIXTURES / name).read_bytes())
    projected = project_table(table, _mapping_for(len(table.headers)))
    assert len(projected.rows) == len(table.rows), name
    compared = 0
    for source_row, projected_row in zip(table.rows, projected.rows, strict=True):
        assert projected_row.source_line_number == source_row.source_line_number, name
        for cell in projected_row.cells:
            expected = source_row.cells[cell.column_index]
            assert cell.value.encode("utf-8") == expected.encode("utf-8"), (name, cell.column_index)
            compared += 1
    assert compared > 0, name


def test_every_adversarial_cell_shape_survives_projection_byte_for_byte() -> None:
    """A property over the shapes a projection would be tempted to normalize.

    The cells are written out as a real CSV, read back through the real
    normalizer, and projected — so the property is asserted end to end over the
    production path rather than against a hand-built table.
    """
    header = [f"col_{index}" for index in range(len(_ADVERSARIAL_CELLS))]
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, delimiter=";", lineterminator="\n")
    writer.writerow(header)
    for rotation in range(len(_ADVERSARIAL_CELLS)):
        writer.writerow(_ADVERSARIAL_CELLS[rotation:] + _ADVERSARIAL_CELLS[:rotation])

    table = normalize_tabular_text(buffer.getvalue(), encoding="utf-8")
    projected = project_table(table, _mapping_for(len(table.headers)))
    assert len(projected.rows) == len(_ADVERSARIAL_CELLS)

    for rotation, projected_row in enumerate(projected.rows):
        expected_row = _ADVERSARIAL_CELLS[rotation:] + _ADVERSARIAL_CELLS[:rotation]
        for cell in projected_row.cells:
            expected = expected_row[cell.column_index]
            assert cell.value.encode("utf-8") == expected.encode("utf-8"), (rotation, cell.column_index)


def test_projection_carries_every_adversarial_shape_rather_than_dropping_them() -> None:
    """Positive control: the byte-equality property must range over real cells.

    A projection emitting no cells at all vacuously satisfies "every projected
    value is byte-equal to its source". This pins the count and the presence of
    the shapes that matter most.
    """
    header = [f"col_{index}" for index in range(len(_ADVERSARIAL_CELLS))]
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, delimiter=";", lineterminator="\n")
    writer.writerow(header)
    writer.writerow(_ADVERSARIAL_CELLS)
    table = normalize_tabular_text(buffer.getvalue(), encoding="utf-8")
    projected = project_table(table, _mapping_for(len(table.headers)))

    values = [cell.value for cell in projected.rows[0].cells]
    assert len(values) == len(_ADVERSARIAL_CELLS)
    for shape in ("1.234,56", "  espacio  ", 'con "nota" entre comillas', "dos\nlineas"):
        assert shape in values, shape


def test_unmapped_columns_are_reported_and_never_copied() -> None:
    """An unknown column is surfaced, not imported — and the file is not refused."""
    source = "Fecha;Concepto;Importe;Departamento\n01/02/2026;Compra;-10,00;Logistica\n"
    table = normalize_tabular_text(source, encoding="utf-8")
    mapping = ColumnRoleMapping(
        roles=(FieldRole.INVOICE_DATE, FieldRole.NOTES, FieldRole.GRAND_TOTAL, FieldRole.UNMAPPED),
    )
    projected = project_table(table, mapping)

    assert [column.header for column in projected.unmapped_columns] == ["Departamento"]
    assert [column.column_index for column in projected.unmapped_columns] == [3]
    assert projected.rows, "the row carrying an unknown column must still import"
    assert "Logistica" not in [cell.value for cell in projected.rows[0].cells]
    assert projected.rows[0].value_for(FieldRole.GRAND_TOTAL) == "-10,00"


def test_a_role_claimed_by_two_columns_is_reported_not_guessed() -> None:
    """A debit/credit split claims one role twice; the ambiguity surfaces."""
    source = "Fecha;Concepto;Debe;Haber\n01/02/2026;Compra;10,00;\n"
    table = normalize_tabular_text(source, encoding="utf-8")
    mapping = ColumnRoleMapping(
        roles=(FieldRole.INVOICE_DATE, FieldRole.NOTES, FieldRole.GRAND_TOTAL, FieldRole.GRAND_TOTAL),
    )
    projected = project_table(table, mapping)

    assert len(projected.ambiguous_roles) == 1
    ambiguity = projected.ambiguous_roles[0]
    assert ambiguity.role is FieldRole.GRAND_TOTAL
    assert ambiguity.column_indexes == (2, 3)
    assert ambiguity.headers == ("Debe", "Haber")
    assert len(projected.rows[0].cells) == 4


def test_an_unambiguous_mapping_reports_no_ambiguity() -> None:
    """Positive control for the ambiguity report: one column per role stays quiet."""
    source = "Fecha;Concepto;Importe\n01/02/2026;Compra;-10,00\n"
    table = normalize_tabular_text(source, encoding="utf-8")
    mapping = ColumnRoleMapping(roles=(FieldRole.INVOICE_DATE, FieldRole.NOTES, FieldRole.GRAND_TOTAL))
    projected = project_table(table, mapping)

    assert projected.ambiguous_roles == ()
    assert projected.unmapped_columns == ()


def test_a_ragged_row_projects_the_cells_it_carries() -> None:
    """A short row yields its own cells rather than being padded or refused."""
    source = "Fecha;Concepto;Importe\n01/02/2026;Compra;-10,00\n02/02/2026;Corta\n"
    table = normalize_tabular_text(source, encoding="utf-8")
    mapping = ColumnRoleMapping(roles=(FieldRole.INVOICE_DATE, FieldRole.NOTES, FieldRole.GRAND_TOTAL))
    projected = project_table(table, mapping)

    assert len(projected.rows) == 2
    assert len(projected.rows[1].cells) == 2
    assert projected.rows[1].value_for(FieldRole.GRAND_TOTAL) is None
    assert projected.rows[1].value_for(FieldRole.NOTES) == "Corta"
