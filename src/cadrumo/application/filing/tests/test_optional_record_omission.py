"""Repeated lease records require invoice rows; fixed records retain their policy.

Modelo 347's inmueble record is filed by the lessor of business premises alone
(RD 1065/2007 art. 34.1.d: "el arrendador consignará [...] las referencias
catastrales y los datos necesarios para la localización de los inmuebles
arrendados"). It repeats once per lease row the invoice lease facts produce, so
a return without a lease files no inmueble record and one with two leased
premises files two.

The repeated-record policy is independent of fixed records: a fixed record
without a binding-record suppression declaration retains its occurrence even
when optional. Operator casillas alone do not create an invoice lease row.
The records are the real bundled declarations, so an edit to either revision's
layout or to the renderer is measured here too. The optional records whose
content arrives through projections, or that carry producer headers alone, keep
their single occurrence.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from ....core.casilla_id import CasillaId
from ....domain.calculations.export_field_kind import CasillaFieldKind
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.ids import BindingId
from ....domain.calculations.registry.schema_exports import ExportRecordDefinition
from ..record_renderer import record_render_rows

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_M347_REVISIONS = ("2025-y-siguientes", "2011-2024")
_IMPORTE: BindingId = "modelo-347-inmueble-row-importe"


def _record(
    operation: PinnedAuthorityOperation, modelo: str, revision_id: str, record_id: str
) -> ExportRecordDefinition:
    return next(
        candidate
        for layout in operation.revision_with_export_layouts(modelo, revision_id).export_layouts
        for candidate in layout.records
        if candidate.id == record_id
    )


def _inmueble(operation: PinnedAuthorityOperation, revision_id: str) -> ExportRecordDefinition:
    record = _record(operation, "347", revision_id, "m347-inmueble")
    # Guard the premise: an optional record repeating once per lease row.
    assert record.required is False
    assert record.repeat == "binding_rows" and record.binding_record is None
    return record


def _fixed(operation: PinnedAuthorityOperation, revision_id: str) -> ExportRecordDefinition:
    """The inmueble record declared without repetition: what the shared fixed-record rule judges."""
    return _inmueble(operation, revision_id).model_copy(update={"repeat": None})


def _casilla_id(record: ExportRecordDefinition, casilla: str) -> CasillaId:
    return next(
        field.casilla_id for field in record.fields if field.casilla_id == casilla and field.casilla_id is not None
    )


@pytest.mark.parametrize("revision_id", _M347_REVISIONS)
def test_an_inmueble_record_without_lease_rows_is_left_out(
    operation: PinnedAuthorityOperation, revision_id: str
) -> None:
    assert record_render_rows(_inmueble(operation, revision_id), {}, {}) == ()


@pytest.mark.parametrize("revision_id", _M347_REVISIONS)
def test_each_lease_row_files_its_own_inmueble_record(operation: PinnedAuthorityOperation, revision_id: str) -> None:
    rows = record_render_rows(
        _inmueble(operation, revision_id),
        {(_IMPORTE, 1): Decimal("12100.00"), (_IMPORTE, 2): Decimal("7260.00")},
        {},
    )

    assert [row.row_index for row in rows] == [1, 2]


@pytest.mark.parametrize("revision_id", _M347_REVISIONS)
def test_a_fixed_optional_record_without_binding_suppression_keeps_its_occurrence(
    operation: PinnedAuthorityOperation, revision_id: str
) -> None:
    assert len(record_render_rows(_fixed(operation, revision_id), {}, {})) == 1


@pytest.mark.parametrize("revision_id", _M347_REVISIONS)
def test_an_empty_string_is_not_operator_data(operation: PinnedAuthorityOperation, revision_id: str) -> None:
    assert record_render_rows(_inmueble(operation, revision_id), {(_IMPORTE, 1): ""}, {}) == ()


@pytest.mark.parametrize("revision_id", _M347_REVISIONS)
def test_operator_casillas_alone_do_not_create_a_lease_row(
    operation: PinnedAuthorityOperation, revision_id: str
) -> None:
    record = _inmueble(operation, revision_id)

    assert record_render_rows(record, {}, {_casilla_id(record, "inmueble.representante-legal-nif"): "12345678Z"}) == ()


@pytest.mark.parametrize("revision_id", _M347_REVISIONS)
def test_a_required_fixed_record_keeps_its_occurrence(operation: PinnedAuthorityOperation, revision_id: str) -> None:
    """Required and optional fixed records both retain their structural occurrence."""
    record = _fixed(operation, revision_id).model_copy(update={"required": True})

    assert len(record_render_rows(record, {}, {})) == 1


def test_an_optional_record_with_projection_fields_keeps_its_occurrence(operation: PinnedAuthorityOperation) -> None:
    """Its content arrives through projections, so empty casillas say nothing about it."""
    record = _record(operation, "303", "2025", "m303-exonerado-390")
    kinds = {field.kind for field in record.fields}
    assert record.required is False and record.binding_record is None
    assert {CasillaFieldKind.CASILLA, CasillaFieldKind.PROJECTION} <= kinds

    assert len(record_render_rows(record, {}, {})) == 1


def test_an_optional_record_of_producer_headers_keeps_its_occurrence(operation: PinnedAuthorityOperation) -> None:
    record = _record(operation, "303", "2025", "m303-domiciliacion")
    assert record.required is False and record.binding_record is None
    assert not any(field.kind is CasillaFieldKind.CASILLA for field in record.fields)

    assert len(record_render_rows(record, {}, {})) == 1
