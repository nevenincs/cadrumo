"""A binding-derived page is suppressed only when it carries nothing at all.

Modelo 131's 2026 page 1 files casilla fields and binding-derived fields into one
fixed record. Deriving the binding coordinates requires the record to declare
``binding_record``, and the emptiness test for such a record once consulted the
binding channel alone.

That is wrong for any page mixing the two channels. A declarant with casilla data
but no binding value would have the page dropped -- and for a ``required`` record
the drop does not even degrade to a silent omission: the export refuses outright.

These tests pin the three states apart against the real bundled registry record,
not a synthetic stand-in, so a future edit to the record or to the derivation is
measured by them too.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from cadrumo.domain.calculations.registry.tests.published_authority import published_revision

from ....domain.calculations.registry.export import derive_export_layouts_from_bindings
from ....domain.calculations.registry.schema_exports import ExportRecordDefinition
from ..record_renderer import record_render_rows

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_MODELO = "131"
_REVISION = "2026"
_RECORD_ID = "modelo-131-page-01"


@pytest.fixture(scope="module")
def mixed_page() -> ExportRecordDefinition:
    """The real, binding-resolved Modelo 131 page 1 record."""
    revision = published_revision(_MODELO, _REVISION)
    record = next(
        candidate
        for layout in derive_export_layouts_from_bindings(revision)
        for candidate in layout.records
        if candidate.id == _RECORD_ID
    )
    # Guard the premise: without these the test would pass vacuously.
    assert record.binding_record is not None
    assert record.repeat is None
    return record


def _a_casilla_id(record: ExportRecordDefinition) -> str:
    return next(field.casilla_id for field in record.fields if field.casilla_id is not None)


def _a_binding_id(record: ExportRecordDefinition) -> str:
    return next(field.binding for field in record.fields if field.binding is not None)


def test_casillas_alone_keep_the_page(mixed_page: ExportRecordDefinition) -> None:
    """Casilla data with no binding value still files the page."""
    rows = record_render_rows(
        mixed_page,
        {},
        {_a_casilla_id(mixed_page): Decimal("1234.56")},
    )

    assert len(rows) == 1


def test_bindings_alone_keep_the_page(mixed_page: ExportRecordDefinition) -> None:
    """The binding channel on its own is still sufficient, as before."""
    rows = record_render_rows(
        mixed_page,
        {(_a_binding_id(mixed_page), None): "G"},
        {},
    )

    assert len(rows) == 1


def test_a_page_carrying_neither_is_left_out(mixed_page: ExportRecordDefinition) -> None:
    """Suppression still happens; only its condition narrowed.

    Without this the fix would read as "always emit", which would put a page of
    bare identifier constants into every fichero.
    """
    rows = record_render_rows(mixed_page, {}, {})

    assert rows == ()


def test_an_empty_string_is_not_a_value(mixed_page: ExportRecordDefinition) -> None:
    """An empty casilla is absence, matching the binding channel's own test."""
    rows = record_render_rows(mixed_page, {}, {_a_casilla_id(mixed_page): ""})

    assert rows == ()
