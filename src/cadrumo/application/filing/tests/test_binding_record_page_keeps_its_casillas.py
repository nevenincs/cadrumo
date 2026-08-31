"""A binding-derived page is suppressed only when it carries nothing at all.

Modelo 390's pagina 7 files two independent apartados into one fixed record:
apartado 11 (operaciones especificas) as eleven casillas, and apartado 12
(prorratas) as per-slot manual_input bindings. Deriving the prorrata coordinates
requires the record to declare ``binding_record``, and the emptiness test for
such a record once consulted the binding channel alone.

That is wrong for any page mixing the two channels. A declarant with operaciones
especificas but no prorrata has real apartado 11 data and no binding value, so
the page was dropped -- and because this record is ``required``, the drop did not
even degrade to a silent omission: the export refused outright.

These tests pin the three states apart against the real bundled registry record,
not a synthetic stand-in, so a future edit to the record or to the derivation is
measured by them too.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from ....core.resources._boundary import bundled_path
from ....domain.calculations.registry.export import derive_export_layouts_from_bindings
from ....domain.calculations.registry.loader import load_registry_tree
from ....domain.calculations.registry.schema_exports import ExportRecordDefinition
from .._record_renderer import _record_render_rows

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_REVISION = "2025"


@pytest.fixture(scope="module")
def pagina_siete() -> ExportRecordDefinition:
    """The real, binding-resolved Modelo 390 pagina 7 record."""
    modelos, _catalogues = load_registry_tree(bundled_path("registry", "aeat"))
    revision = next(modelo for modelo in modelos if modelo.id == "390").revisions[_REVISION]
    record = next(
        candidate
        for layout in derive_export_layouts_from_bindings(revision)
        for candidate in layout.records
        if candidate.id == "modelo-390-page-07"
    )
    # Guard the premise: without these the test would pass vacuously.
    assert record.binding_record is not None
    assert record.repeat is None
    return record


def _a_casilla_id(record: ExportRecordDefinition) -> str:
    return next(field.casilla_id for field in record.fields if field.casilla_id is not None)


def _a_binding_id(record: ExportRecordDefinition) -> str:
    return next(field.binding for field in record.fields if field.binding is not None)


def test_apartado_11_casillas_alone_keep_the_page(pagina_siete: ExportRecordDefinition) -> None:
    """Operaciones especificas with no prorrata still files pagina 7."""
    rows = _record_render_rows(
        pagina_siete,
        {},
        {_a_casilla_id(pagina_siete): Decimal("1234.56")},
    )

    assert len(rows) == 1


def test_prorrata_bindings_alone_keep_the_page(pagina_siete: ExportRecordDefinition) -> None:
    """The binding channel on its own is still sufficient, as before."""
    rows = _record_render_rows(
        pagina_siete,
        {(_a_binding_id(pagina_siete), None): "G"},
        {},
    )

    assert len(rows) == 1


def test_a_page_carrying_neither_is_left_out(pagina_siete: ExportRecordDefinition) -> None:
    """Suppression still happens; only its condition narrowed.

    Without this the fix would read as "always emit", which would put a page of
    bare identifier constants into every fichero.
    """
    rows = _record_render_rows(pagina_siete, {}, {})

    assert rows == ()


def test_an_empty_string_is_not_a_value(pagina_siete: ExportRecordDefinition) -> None:
    """An empty casilla is absence, matching the binding channel's own test."""
    rows = _record_render_rows(pagina_siete, {}, {_a_casilla_id(pagina_siete): ""})

    assert rows == ()
