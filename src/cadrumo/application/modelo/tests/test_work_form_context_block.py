"""The canonical work-form walker admits declared context without editing addresses."""

import pytest

from cadrumo.domain.calculations.registry.export import derive_export_layouts_from_bindings
from cadrumo.domain.calculations.registry.export_semantics import ExportDraftAttribute
from cadrumo.domain.calculations.registry.schema_form_layouts import FormContextFieldBlock

from ..work_form_models import ModeloFormContextFieldBlock, section_fields
from .test_work_form import _form, _layout
from .test_work_form import snapshot as snapshot

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_walker_projects_declared_year_without_a_false_casilla(snapshot, operation):
    export, record, field = next(
        (layout, record, field)
        for layout in derive_export_layouts_from_bindings(snapshot.revision)
        for record in layout.records
        for field in record.fields
        if field.draft_attribute is ExportDraftAttribute.FILING_YEAR and record.repeat is None
    )
    block = FormContextFieldBlock(
        id="year",
        export_layout_id=export.id,
        export_record_id=record.id,
        export_field_id=field.id,
        heading_key="test.form.year",
        official_heading="Ejercicio",
    )
    layout = _layout(snapshot)
    page = layout.pages[0]
    section = page.sections[0].model_copy(update={"blocks": (block, *page.sections[0].blocks)})
    page = page.model_copy(update={"sections": (section, *page.sections[1:])})
    layout = layout.model_copy(update={"pages": (page, *layout.pages[1:])})
    form = _form(snapshot, operation, layout=layout)
    projected = form.pages[0].sections[0].blocks[0]
    assert isinstance(projected, ModeloFormContextFieldBlock)
    assert projected.value == snapshot.filing_year
    assert projected.label.text == "Ejercicio"
    assert "address" not in projected.model_dump()
    assert all(item.address.kind != "context_field" for item in section_fields(form.pages[0].sections[0]))


def test_walker_projects_summary_as_readonly_unknown_without_edit_address(snapshot, operation):
    from cadrumo.application.storage.calc_sheets.tests.test_form_context_fields import snapshot_with_binding_context

    snapshot = snapshot.model_copy(
        update={"revision": snapshot.revision.model_copy(update={"form_layouts": (_layout(snapshot),)})}
    )
    snapshot, _block, _binding = snapshot_with_binding_context(snapshot)
    form = _form(snapshot, operation, layout=snapshot.revision.form_layouts[0])
    projected = form.pages[0].sections[0].blocks[0]
    assert isinstance(projected, ModeloFormContextFieldBlock)
    assert projected.value is None
    assert projected.label.text == "[02] Importe total"
    assert "address" not in projected.model_dump()
