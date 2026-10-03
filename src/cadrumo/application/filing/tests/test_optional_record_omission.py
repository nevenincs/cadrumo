"""An optional record without a binding record is filed only when it carries operator data.

Modelo 347's inmueble record is filed by the lessor of business premises alone
(RD 1065/2007 art. 34.1.d: "el arrendador consignará [...] las referencias
catastrales y los datos necesarios para la localización de los inmuebles
arrendados"). Its operator fields are casillas and it links no binding record,
so ``required = false`` is the only declaration it can carry. A return without
a lease must not file a blank inmueble record, and one with lease data must.

The records are the real bundled declarations, so an edit to either revision's
layout or to the renderer is measured here too. The optional records whose
content arrives through projections, or that carry producer headers alone, keep
their single occurrence.
"""

from __future__ import annotations

import pytest

from cadrumo.domain.calculations.registry.tests.published_authority import published_revision

from ....domain.calculations.export_field_kind import CasillaFieldKind
from ....domain.calculations.registry.export import derive_export_layouts_from_bindings
from ....domain.calculations.registry.schema_exports import ExportRecordDefinition
from ..record_renderer import record_render_rows

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_M347_REVISIONS = ("2025-y-siguientes", "2011-2024")


def _record(modelo: str, revision_id: str, record_id: str) -> ExportRecordDefinition:
    return next(
        candidate
        for layout in derive_export_layouts_from_bindings(published_revision(modelo, revision_id))
        for candidate in layout.records
        if candidate.id == record_id
    )


def _inmueble(revision_id: str) -> ExportRecordDefinition:
    record = _record("347", revision_id, "m347-inmueble")
    # Guard the premise: an optional, fixed record whose operator data is all casillas.
    assert record.required is False
    assert record.repeat is None and record.binding_record is None
    assert {field.kind for field in record.fields} & {CasillaFieldKind.BINDING, CasillaFieldKind.PROJECTION} == set()
    return record


def _casilla_id(record: ExportRecordDefinition, casilla: str) -> str:
    return next(str(field.casilla_id) for field in record.fields if str(field.casilla_id) == casilla)


@pytest.mark.parametrize("revision_id", _M347_REVISIONS)
def test_an_inmueble_record_without_lease_data_is_left_out(revision_id: str) -> None:
    assert record_render_rows(_inmueble(revision_id), {}, {}) == ()


@pytest.mark.parametrize("revision_id", _M347_REVISIONS)
def test_an_empty_string_is_not_lease_data(revision_id: str) -> None:
    record = _inmueble(revision_id)

    assert record_render_rows(record, {}, {_casilla_id(record, "inmueble.arrendatario-nif"): ""}) == ()


@pytest.mark.parametrize("revision_id", _M347_REVISIONS)
def test_one_lease_casilla_files_the_record(revision_id: str) -> None:
    record = _inmueble(revision_id)

    rows = record_render_rows(
        record, {}, {_casilla_id(record, "inmueble.referencia-catastral"): "9872023VH5797S0001WX"}
    )

    assert len(rows) == 1


@pytest.mark.parametrize("revision_id", _M347_REVISIONS)
def test_requiredness_is_what_lets_the_record_go(revision_id: str) -> None:
    """The same record declared required keeps its occurrence, so the omission keys on the declaration."""
    record = _inmueble(revision_id).model_copy(update={"required": True})

    assert len(record_render_rows(record, {}, {})) == 1


def test_an_optional_record_with_projection_fields_keeps_its_occurrence() -> None:
    """Its content arrives through projections, so empty casillas say nothing about it."""
    record = _record("303", "2025", "m303-exonerado-390")
    kinds = {field.kind for field in record.fields}
    assert record.required is False and record.binding_record is None
    assert {CasillaFieldKind.CASILLA, CasillaFieldKind.PROJECTION} <= kinds

    assert len(record_render_rows(record, {}, {})) == 1


def test_an_optional_record_of_producer_headers_keeps_its_occurrence() -> None:
    record = _record("303", "2025", "m303-domiciliacion")
    assert record.required is False and record.binding_record is None
    assert not any(field.kind is CasillaFieldKind.CASILLA for field in record.fields)

    assert len(record_render_rows(record, {}, {})) == 1
