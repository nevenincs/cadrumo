"""Form-only scalar inputs are real typed sources, not decorative empty boxes."""

from datetime import date
from decimal import Decimal

import pytest

from cadrumo.domain.calculations.registry.binding_value_contract import BindingValueChannel
from cadrumo.domain.calculations.registry.schema import BindingDefinition
from cadrumo.domain.calculations.registry.schema_form_layouts import (
    FormBindingInputsBlock,
    FormCell,
    FormFieldBlock,
    FormGridBlock,
    FormGridColumn,
    FormGridRow,
    FormLayoutDefinition,
    FormPageDefinition,
    FormPlacementDefinition,
    FormSectionDefinition,
)
from cadrumo.domain.calculations.registry.tests.published_authority import published_snapshot

from ..engine import build_export_plan
from ..errors import CalcSheetsEngineError
from ..form_workbook import add_form_workbook
from ..layout import plan_layout
from ..records import TabName

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _with_bindings(snapshot, bindings, blocks):
    layout = FormLayoutDefinition(
        id="test-input-layout",
        revision_id=snapshot.revision.id,
        seed_source="authored",
        generator_version=1,
        source_state_digest="a" * 64,
        pages=(
            FormPageDefinition(
                id="page",
                heading_key="test.page",
                sections=(
                    FormSectionDefinition(
                        id="section", heading_key="test.section", official_heading="Datos", blocks=blocks
                    ),
                ),
            ),
        ),
        placements=tuple(
            FormPlacementDefinition(casilla_id=casilla.id, kind="working_figure")
            for casilla in snapshot.revision.casillas
        ),
    )
    return snapshot.model_copy(
        update={
            "revision": snapshot.revision.model_copy(
                update={"bindings": (*snapshot.revision.bindings, *bindings), "form_layouts": (layout,)}
            )
        }
    )


def _manual(snapshot, data_type, *, casilla_id=None):
    casilla = snapshot.revision.casillas[0]
    provider = {"kind": "manual_input", "data_type": data_type}
    if casilla_id is not None:
        provider["casilla_id"] = casilla_id
    else:
        provider.update(record="test-record", field=f"test-{data_type}", offset=1, length=20)
    return BindingDefinition.model_validate(
        {
            "id": f"test-input-{data_type}",
            "provider": provider,
            "value": {"data_type": data_type, "channel": "decimal" if data_type == "money" else data_type},
            "legal_refs": tuple(casilla.legal_refs),
            "source_refs": tuple(casilla.source_refs),
        }
    )


@pytest.mark.parametrize("block_kind", ("field", "grid", "binding_inputs"))
def test_declared_scalar_form_inputs_get_sources_without_moving_formula_operands(block_kind):
    snapshot = published_snapshot("130", filing_year=2025, period="4T")
    binding = _manual(snapshot, "text")
    baseline = plan_layout(snapshot.revision, bracket_filter_date=date(2025, 12, 31))
    if block_kind == "field":
        block = FormFieldBlock(id="manual", binding_id=binding.id)
    elif block_kind == "binding_inputs":
        block = FormBindingInputsBlock(id="manual", binding_ids=(binding.id,))
    else:
        block = FormGridBlock(
            id="manual",
            columns=(
                FormGridColumn(key="input", heading_key="test.input", official_heading="Código"),
                FormGridColumn(key="blank", heading_key="test.blank", official_heading="Observaciones"),
            ),
            rows=(
                FormGridRow(
                    key="row",
                    heading_key="test.row",
                    official_heading="Actividad",
                    cells=(FormCell(kind="binding_input", binding_id=binding.id), FormCell(kind="blank")),
                ),
            ),
        )
    changed = _with_bindings(snapshot, (binding,), (block, FormFieldBlock(id="repeat", binding_id=binding.id)))
    layout = plan_layout(changed.revision, bracket_filter_date=date(2025, 12, 31))
    assert all(layout.binding_cells[key] == address for key, address in baseline.binding_cells.items())
    assert layout.date_binding_cells == baseline.date_binding_cells
    assert len([row for row in layout.binding_rows if row.binding == binding.id]) == 1
    plan = build_export_plan(changed)
    cell = next(cell for cell in plan.value_cells if cell.address == layout.binding_cells[binding.id])
    assert cell.role == "operator_input" and cell.value is None
    assert next(fmt for fmt in plan.number_formats if fmt.address == cell.address).pattern == "@"


@pytest.mark.parametrize(
    ("data_type", "format_type", "value"),
    (
        ("text", "text", "0012"),
        ("date", "date", "2025-10-05"),
        ("boolean", None, False),
        ("money", "money", Decimal("12.34")),
        ("integer", "integer", Decimal("2")),
        ("decimal", "decimal", Decimal("0.125")),
    ),
)
def test_binding_value_contract_controls_format_without_value_coercion(data_type, format_type, value):
    snapshot = published_snapshot("130", filing_year=2025, period="4T")
    binding = _manual(snapshot, data_type)
    changed = _with_bindings(snapshot, (binding,), (FormBindingInputsBlock(id="inputs", binding_ids=(binding.id,)),))
    layout = plan_layout(changed.revision)
    addresses = layout.date_binding_cells if data_type == "date" else layout.binding_cells
    address = addresses[binding.id]
    plan = build_export_plan(changed)
    cell = next(cell for cell in plan.value_cells if cell.address == address)
    seeded = type(cell).model_validate({**dict(cell), "value": value})
    assert seeded.value == value and type(seeded.value) is type(value)
    formats = [fmt for fmt in plan.number_formats if fmt.address == address]
    assert [fmt.data_type for fmt in formats] == ([format_type] if format_type else [])


def test_casilla_manual_binding_reuses_existing_input_and_form_reference():
    snapshot = published_snapshot("130", filing_year=2025, period="4T")
    binding = _manual(snapshot, "money", casilla_id="01")
    changed = _with_bindings(snapshot, (binding,), (FormFieldBlock(id="input", binding_id=binding.id),))
    layout = plan_layout(changed.revision)
    assert layout.binding_cells[binding.id] == layout.entradas_cells["01"]
    assert not any(row.binding == binding.id for row in layout.binding_rows)
    rendered = add_form_workbook(build_export_plan(changed), changed)
    reference = layout.entradas_cells["01"].qualified()
    assert any(
        cell.address.tab is TabName.FORM and cell.casilla_id is None and reference in cell.formula
        for cell in rendered.formula_cells
    )


def test_new_form_input_refuses_nonmanual_provider_and_rowset():
    snapshot = published_snapshot("130", filing_year=2025, period="4T")
    original = next(binding for binding in snapshot.revision.bindings if binding.source != "manual_input")
    unsupported = original.model_copy(update={"id": "test-unreferenced-provider"})
    changed = _with_bindings(snapshot, (unsupported,), (FormFieldBlock(id="input", binding_id=unsupported.id),))
    with pytest.raises(CalcSheetsEngineError, match="manual-input provider"):
        plan_layout(changed.revision)
    manual = _manual(snapshot, "text")
    rowset = manual.model_copy(
        update={"value": manual.value.model_copy(update={"channel": BindingValueChannel.ROW_SET})}
    )
    changed = _with_bindings(snapshot, (rowset,), (FormFieldBlock(id="input", binding_id=rowset.id),))
    with pytest.raises(CalcSheetsEngineError, match="row-set"):
        plan_layout(changed.revision)


@pytest.mark.parametrize("casilla_id", ("03", "unknown"))
def test_manual_binding_cannot_invent_an_input_for_a_computed_or_unknown_casilla(casilla_id):
    snapshot = published_snapshot("130", filing_year=2025, period="4T")
    binding = _manual(snapshot, "money", casilla_id=casilla_id)
    changed = _with_bindings(snapshot, (binding,), (FormFieldBlock(id="input", binding_id=binding.id),))
    with pytest.raises(CalcSheetsEngineError, match="not an editable casilla"):
        plan_layout(changed.revision)
