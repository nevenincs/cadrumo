"""Unit test for the Sheets row-set header batch builder.

Guards `_build_row_set_header_data` — the helper that turns each
row-set's column declarations into a Sheets `values.batchUpdate`
data entry. Registry-side row-set positioning + column allocation
are tested separately; this test asserts the apply-side handoff
shape (range + label) matches the engine's positions exactly.
"""

from __future__ import annotations

import pytest

from .....application.storage.calc_sheets._records import SheetCellAddress, SheetRowSet, SheetRowSetColumn, TabName
from ..calc_sheets_apply import _build_row_set_header_data

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_TEST_LEGAL_REFS = ("ley-58-2003:art-119",)
_TEST_SOURCE_REFS = ("aeat-dr-190-2025",)


def _column(binding: str, column: int, label: str, *, row: int = 1) -> SheetRowSetColumn:
    return SheetRowSetColumn(
        binding=binding,
        header_address=SheetCellAddress.at(TabName.DETALLE, row, column),
        header_label=label,
        legal_refs=_TEST_LEGAL_REFS,
    )


def test_build_row_set_header_data_emits_one_entry_per_column() -> None:
    row_set = SheetRowSet(
        grouping="per_perceptor_clave",
        tab=TabName.DETALLE,
        header_row=1,
        first_data_row=2,
        columns=(
            _column("modelo-190-perceptor-row-nif", 1, "NIF del perceptor"),
            _column("modelo-190-perceptor-row-name", 2, "Apellidos y nombre del perceptor"),
            _column("modelo-190-perceptor-row-clave", 3, "Clave"),
        ),
        legal_refs=_TEST_LEGAL_REFS,
        source_refs=_TEST_SOURCE_REFS,
    )

    data = _build_row_set_header_data((row_set,))

    assert len(data) == 3
    nif_entry = data[0]
    assert nif_entry["range"] == "'Detalle'!A1"
    assert nif_entry["values"] == [["NIF del perceptor"]]
    assert data[1]["range"] == "'Detalle'!B1"
    assert data[2]["range"] == "'Detalle'!C1"


def test_build_row_set_header_data_handles_multiple_row_sets() -> None:
    """Multiple row-sets stack; each contributes its own header entries."""

    operator_clave_row_set = SheetRowSet(
        grouping="operator_clave",
        tab=TabName.DETALLE,
        header_row=1,
        first_data_row=2,
        columns=(_column("iva-349-operador-row-nif", 1, "NIF de la contraparte"),),
        legal_refs=_TEST_LEGAL_REFS,
        source_refs=_TEST_SOURCE_REFS,
    )
    operator_clave_period_row_set = SheetRowSet(
        grouping="operator_clave_period",
        tab=TabName.DETALLE,
        header_row=53,
        first_data_row=54,
        columns=(
            _column("iva-349-rectificacion-row-nif", 1, "NIF", row=53),
            _column("iva-349-rectificacion-row-ejercicio", 2, "Ejercicio rectificado", row=53),
        ),
        legal_refs=_TEST_LEGAL_REFS,
        source_refs=_TEST_SOURCE_REFS,
    )

    data = _build_row_set_header_data((operator_clave_row_set, operator_clave_period_row_set))

    assert len(data) == 3
    assert data[0]["range"] == "'Detalle'!A1"
    assert data[1]["range"] == "'Detalle'!A53"
    assert data[2]["range"] == "'Detalle'!B53"


def test_build_row_set_header_data_returns_empty_when_no_row_sets() -> None:
    assert _build_row_set_header_data(()) == []
