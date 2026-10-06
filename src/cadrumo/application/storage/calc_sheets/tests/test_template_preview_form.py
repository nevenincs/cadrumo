"""Fictional form projection shares geometry, never production context readers."""

from decimal import Decimal

import pytest

from cadrumo.core.filing_producer_key import FilingProducerKey
from cadrumo.domain.calculations.registry.export_semantics import ExportDraftAttribute
from cadrumo.domain.calculations.registry.schema_form_layouts import FormRepeatingGroupBlock

from ..engine import build_template_preview_plan
from ..errors import CalcSheetsEngineError
from ..export_tables import export_identity_stamps
from ..form_workbook import add_template_preview_form
from ..records import SheetGuideContent, TabName
from ..template_source import WorkbookTemplateSource
from .test_form_context_fields import _with_context
from .test_form_workbook import form_source as form_source

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _preview(snapshot):
    source = WorkbookTemplateSource(
        modelo_id=snapshot.modelo.id,
        revision=snapshot.revision,
        preview_frame=snapshot.filing_period,
        source_ref=next(iter(snapshot.sources)),
        legal=snapshot.legal,
        sources=snapshot.sources,
    )
    plan = build_template_preview_plan(
        source, guide=SheetGuideContent(title="Ejemplo ficticio", paragraphs=("Datos de prueba.",))
    )
    return source, plan


def test_preview_retains_live_missing_input_guards_and_hides_technical_identity(form_source):
    snapshot, _ = form_source
    source, plan = _preview(snapshot)
    rendered = add_template_preview_form(plan, source)
    assert rendered.human_presentation
    assert rendered.tabs[0] is TabName.FORM
    assert export_identity_stamps(rendered) == ()
    assert any("EJEMPLO FICTICIO" in str(cell.value) for cell in rendered.value_cells)
    assert all(source.template_digest not in str(cell.value) for cell in rendered.value_cells)
    assert [cell for cell in rendered.value_cells if cell.role == "operator_input"] == [
        cell for cell in plan.value_cells if cell.role == "operator_input"
    ]
    blank = next(cell for cell in plan.value_cells if cell.casilla_id and cell.value is None)
    projected = next(
        cell
        for cell in rendered.formula_cells
        if cell.address.tab is TabName.FORM and cell.casilla_id == blank.casilla_id
    )
    ref = blank.address.qualified()
    assert projected.formula == f'IF(ISBLANK({ref}),"Sin dato",{ref})'
    with pytest.raises(CalcSheetsEngineError, match="already contains"):
        add_template_preview_form(rendered, source)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("modelo_id", "303"),
        ("revision_id", "other"),
        ("preview_year", 2024),
        ("preview_period", "1T"),
        ("template_digest", "0" * 64),
    ],
)
def test_preview_refuses_every_coordinate_or_content_mismatch(form_source, field, value):
    snapshot, _ = form_source
    source, plan = _preview(snapshot)
    plan = plan.model_copy(update={"metadata": plan.metadata.model_copy(update={field: value})})
    with pytest.raises(CalcSheetsEngineError, match="preview identity"):
        add_template_preview_form(plan, source)


@pytest.mark.parametrize(
    ("producer", "draft", "expected"),
    [
        (None, ExportDraftAttribute.FILING_YEAR, Decimal(2025)),
        (None, ExportDraftAttribute.PERIOD_CODE, "4T"),
        (FilingProducerKey.TAXPAYER_TAX_ID, None, "Sin dato"),
    ],
)
def test_preview_reads_only_illustrative_frame_not_producer_facts(form_source, monkeypatch, producer, draft, expected):
    snapshot, _ = form_source
    snapshot, _ = _with_context(snapshot, producer=producer, draft=draft)
    source, plan = _preview(snapshot)

    def forbidden(*args, **kwargs):
        pytest.fail("fictional template invoked a production context reader")

    monkeypatch.setattr("cadrumo.application.storage.calc_sheets.form_workbook.form_context_value", forbidden)
    rendered = add_template_preview_form(plan, source)
    label = next(
        cell for cell in rendered.value_cells if cell.address.tab is TabName.FORM and cell.value == "Dato declarado"
    )
    value = next(
        cell.value
        for cell in rendered.value_cells
        if cell.address.tab is TabName.FORM and cell.address.row == label.address.row and cell.address.column == 9
    )
    assert value == expected


def test_preview_repeating_rows_are_unknown_and_never_read_saved_revision(form_source, monkeypatch):
    snapshot, _ = form_source
    layout = snapshot.revision.form_layouts[0]
    page = layout.pages[0]
    section = page.sections[0]
    block = FormRepeatingGroupBlock(
        id="unpopulated-records", row_source="export_record", export_record_id="test-record"
    )
    section = section.model_copy(update={"blocks": (*section.blocks, block)})
    layout = layout.model_copy(update={"pages": (page.model_copy(update={"sections": (section,)}),)})
    snapshot = snapshot.model_copy(
        update={"revision": snapshot.revision.model_copy(update={"form_layouts": (layout,)})}
    )
    source, plan = _preview(snapshot)

    def forbidden(*args, **kwargs):
        pytest.fail("fictional template invoked saved revision reader")

    monkeypatch.setattr("cadrumo.application.storage.calc_sheets.form_workbook.saved_form_records", forbidden)
    rendered = add_template_preview_form(plan, source)
    values = [cell.value for cell in rendered.value_cells if cell.address.tab is TabName.FORM]
    assert "Sin registros aportados a esta vista. Consulte el detalle de origen." in values
    assert "No hay registros en el detalle guardado." not in values
