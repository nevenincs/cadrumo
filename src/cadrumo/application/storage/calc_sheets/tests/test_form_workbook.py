"""Negative controls for the shared registry form projection."""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

import pytest

from cadrumo.application.modelo.work_form_models import ModeloFormRepeatingRow
from cadrumo.domain.calculations.registry.schema_base import CasillaDataType
from cadrumo.domain.calculations.registry.schema_form_layouts import (
    FormCell,
    FormFieldBlock,
    FormGridBlock,
    FormGridColumn,
    FormGridRow,
    FormLayoutDefinition,
    FormPageDefinition,
    FormPlacementDefinition,
    FormRepeatingColumn,
    FormRepeatingGroupBlock,
    FormSectionDefinition,
)
from cadrumo.domain.calculations.registry.schema_formula import FormulaExpression
from cadrumo.domain.calculations.registry.tests.published_authority import published_snapshot

from ..engine import build_export_plan
from ..errors import CalcSheetsEngineError
from ..export_tables import export_identity_stamps
from ..form_workbook import _FormBuilder, add_form_workbook
from ..human_workbook import human_workbook
from ..records import (
    SheetCellAddress,
    SheetEvidenceFacet,
    SheetEvidenceManualEntry,
    SheetRowSet,
    SheetRowSetColumn,
    TabName,
)
from ..theme import StyleRole
from ..workbook_cells import plan_value_blocks

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


@pytest.fixture
def form_source():
    snapshot = published_snapshot("130", filing_year=2025, period="4T")
    # Deliberately synthetic layout: tests exercise projection contracts, not
    # the reviewed accuracy of any official form.
    layout = FormLayoutDefinition(
        id="test-layout",
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
                        id="section",
                        heading_key="test.section",
                        official_heading="Liquidación",
                        blocks=tuple(
                            FormFieldBlock(id=f"field-{i}", casilla_id=c.id)
                            for i, c in enumerate(snapshot.revision.casillas)
                        ),
                    ),
                ),
            ),
        ),
        placements=tuple(
            FormPlacementDefinition(
                casilla_id=c.id, kind="on_form", box_number=c.number if c.number.isdigit() else None
            )
            for c in snapshot.revision.casillas
        ),
    )
    snapshot = snapshot.model_copy(
        update={"revision": snapshot.revision.model_copy(update={"form_layouts": (layout,)})}
    )
    return snapshot, build_export_plan(snapshot)


def test_blank_inputs_remain_live_without_becoming_zero(form_source):
    snapshot, plan = form_source
    rendered = add_form_workbook(plan, snapshot)
    assert rendered.tabs[0] is TabName.FORM
    source = next(c for c in plan.value_cells if c.casilla_id and c.value is None)
    projected = next(
        c for c in rendered.formula_cells if c.address.tab is TabName.FORM and c.casilla_id == source.casilla_id
    )
    assert projected.formula == f'IF(ISBLANK({source.address.qualified()}),"Sin dato",{source.address.qualified()})'
    assert [c for c in rendered.value_cells if c.role in ("operator_input", "parameter_value")] == [
        c for c in plan.value_cells if c.role in ("operator_input", "parameter_value")
    ]
    assert any("pendiente de revisión" in str(c.value) for c in rendered.value_cells)


def _with_transport_control(snapshot):
    revision = snapshot.revision
    control = next(c for c in revision.casillas if c.input_kind.value == "manual").model_copy(
        update={
            "id": "file-control",
            "number": "file-control",
            "form_number": None,
            "data_type": CasillaDataType.TEXT,
            "binding": None,
        }
    )
    layout = revision.form_layouts[0]
    placement = FormPlacementDefinition(
        casilla_id=control.id,
        kind="working_figure",
        workbook_exclusion="transport_control",
        workbook_exclusion_reason="Synthetic file framing control with no financial dependency.",
    )
    return snapshot.model_copy(
        update={
            "revision": revision.model_copy(
                update={
                    "casillas": (*revision.casillas, control),
                    "form_layouts": (layout.model_copy(update={"placements": (*layout.placements, placement)}),),
                }
            )
        }
    )


def test_transport_exclusion_preserves_financial_cells_and_does_not_mutate_source(form_source):
    snapshot, _ = form_source
    snapshot = _with_transport_control(snapshot)
    plan = build_export_plan(snapshot)
    assert any(c.casilla_id == "file-control" for c in plan.value_cells)
    rendered = add_form_workbook(plan, snapshot)
    assert not any(c.casilla_id == "file-control" for c in (*rendered.value_cells, *rendered.formula_cells))
    assert any(c.id == "file-control" for c in snapshot.revision.casillas)
    assert [c for c in rendered.value_cells if c.role == "operator_input"] == [
        c for c in plan.value_cells if c.role == "operator_input" and c.casilla_id != "file-control"
    ]
    assert "file-control" not in "\n".join(str(c.value) for c in rendered.value_cells)


@pytest.mark.parametrize("financial", [True, False])
def test_transport_exclusion_refuses_financial_values_or_formula_dependencies(form_source, financial):
    snapshot, _ = form_source
    snapshot = _with_transport_control(snapshot)
    revision = snapshot.revision
    if financial:
        casillas = tuple(
            c.model_copy(update={"data_type": CasillaDataType.MONEY}) if c.id == "file-control" else c
            for c in revision.casillas
        )
        revision = revision.model_copy(update={"casillas": casillas})
    else:
        formula = revision.formulas[0]
        formula = formula.model_copy(update={"expression": FormulaExpression(casilla_id="file-control")})
        revision = revision.model_copy(update={"formulas": (formula, *revision.formulas[1:])})
    snapshot = snapshot.model_copy(update={"revision": revision})
    with pytest.raises(CalcSheetsEngineError, match="transport exclusion"):
        human_workbook(build_export_plan(snapshot), snapshot)


@pytest.mark.parametrize("reference_kind", ["qualified", "unquoted", "lowercase", "local", "range", "dynamic"])
def test_transport_exclusion_refuses_additional_sheet_formula(form_source, reference_kind):
    snapshot, _ = form_source
    snapshot = _with_transport_control(snapshot)
    plan = build_export_plan(snapshot)
    source = next(c for c in plan.value_cells if c.casilla_id == "file-control")
    text = {
        "qualified": source.address.qualified(),
        "unquoted": source.address.tab.value + "!" + source.address.a1,
        "lowercase": (source.address.tab.value + "!" + source.address.a1).lower(),
        "local": source.address.a1,
        "range": f"SUM('{source.address.tab.value}'!D1:D1000)",
        "dynamic": f'INDIRECT("{source.address.qualified()}")',
    }[reference_kind]
    address = (
        SheetCellAddress.at(source.address.tab, 500, 4) if reference_kind == "local" else plan.formula_cells[0].address
    )
    formula = plan.formula_cells[0].model_copy(update={"formula": text, "address": address})
    plan = plan.model_copy(update={"formula_cells": (formula, *plan.formula_cells[1:])})
    with pytest.raises(CalcSheetsEngineError, match="referenced by a sheet formula"):
        human_workbook(plan, snapshot)


def test_human_surfaces_remove_machine_identity_preserving_financial_dependencies(form_source):
    snapshot, plan = form_source
    plan = plan.model_copy(
        update={
            "protected_ranges": tuple(
                region.model_copy(update={"description": plan.metadata.registry_sha})
                for region in plan.protected_ranges
            )
        }
    )
    rendered = add_form_workbook(plan, snapshot)
    text = "\n".join(str(value) for block in plan_value_blocks(rendered) for value in block.values)
    assert plan.metadata.registry_sha not in text
    assert "Registry SHA" not in text
    assert "Snapshot fingerprint" not in text
    assert all(binding.id not in text for binding in snapshot.revision.bindings)
    assert all(parameter.id not in text for parameter in snapshot.revision.parameters)
    assert export_identity_stamps(rendered) == ()
    for original, projected in zip(plan.formula_cells, rendered.formula_cells, strict=False):
        assert projected.address == original.address
        assert projected.rounding_rule == original.rounding_rule
        assert projected.formula == original.formula or projected.formula.endswith(f',"Sin dato",{original.formula})')
    assert any("boe.es" in str(value) for block in plan_value_blocks(rendered) for value in block.values)
    assert all("Refs:" not in c.grounding_message() for c in rendered.cell_constraints)
    assert all(plan.metadata.registry_sha not in region.description for region in rendered.protected_ranges)


def test_unresolved_technical_note_is_refused(form_source):
    snapshot, plan = form_source
    source = next(c for c in plan.value_cells if c.role == "operator_input")
    cells = tuple(
        c.model_copy(update={"note": plan.metadata.registry_sha}) if c == source else c for c in plan.value_cells
    )
    with pytest.raises(CalcSheetsEngineError, match="technical presentation"):
        add_form_workbook(plan.model_copy(update={"value_cells": cells}), snapshot)


def test_human_presentation_refuses_a_different_authority(form_source):
    snapshot, plan = form_source
    changed = snapshot.model_copy(update={"filing_year": snapshot.filing_year + 1})
    with pytest.raises(CalcSheetsEngineError, match="calculation authority"):
        human_workbook(plan, changed)


def test_manual_evidence_keeps_meaning_and_explanation(form_source):
    snapshot, plan = form_source
    casilla = snapshot.revision.casillas[0]
    evidence = SheetEvidenceFacet(
        manual_entries=(
            SheetEvidenceManualEntry(
                casilla_id=casilla.id,
                value="125.50",
                kind="casilla_input",
                note="Ajuste confirmado con el justificante",
                legal_refs=tuple(casilla.legal_refs),
                source_refs=tuple(casilla.source_refs),
            ),
        )
    )
    rendered = add_form_workbook(plan.model_copy(update={"evidence": evidence}), snapshot)
    values = [value for block in plan_value_blocks(rendered) for value in block.values]
    assert "125.50" in values
    assert "Ajuste confirmado con el justificante" in values
    assert "Dato introducido" in values
    assert "casilla_input" not in values
    evidence_filter = next(item for item in rendered.auto_filters if item.tab is TabName.EVIDENCIA)
    assert (evidence_filter.start_row, evidence_filter.end_row) == (1, 2)
    assert evidence_filter.end_column == 14
    assert next(item for item in rendered.frozen_views if item.tab is TabName.EVIDENCIA).frozen_rows == 1
    last_reference_row = max(
        cell.address.row for cell in rendered.value_cells if cell.address.tab is TabName.PROVENANCE
    )
    for facets in (rendered.auto_filters, rendered.protected_ranges):
        region = next(item for item in facets if item.tab is TabName.PROVENANCE)
        assert (region.start_row, region.end_row, region.end_column) == (1, last_reference_row, 3)


def test_unlabelled_row_input_is_refused_instead_of_renamed(form_source):
    snapshot, plan = form_source
    casilla = snapshot.revision.casillas[0]
    row_set = SheetRowSet(
        grouping="unknown",
        tab=TabName.DETALLE,
        header_row=1,
        first_data_row=2,
        columns=(
            SheetRowSetColumn(
                binding="unknown-input",
                header_address=SheetCellAddress.at(TabName.DETALLE, 1, 1),
                header_label="unknown-input",
                legal_refs=tuple(casilla.legal_refs),
            ),
        ),
        legal_refs=tuple(casilla.legal_refs),
        source_refs=tuple(casilla.source_refs),
    )
    with pytest.raises(CalcSheetsEngineError, match="authored label"):
        add_form_workbook(plan.model_copy(update={"row_sets": (row_set,)}), snapshot)


def test_declared_binding_field_has_a_live_source_reference(form_source):
    snapshot, plan = form_source
    binding_ids = {binding.id for binding in snapshot.revision.bindings}
    source = next(
        cell
        for cell in plan.value_cells
        if cell.address.tab is TabName.ENTRADAS and cell.address.column == 3 and cell.value in binding_ids
    )
    layout = snapshot.revision.form_layouts[0]
    page = layout.pages[0]
    section = page.sections[0]
    section = section.model_copy(
        update={"blocks": (*section.blocks, FormFieldBlock(id="binding-field", binding_id=str(source.value)))}
    )
    layout = layout.model_copy(update={"pages": (page.model_copy(update={"sections": (section,)}),)})
    snapshot = snapshot.model_copy(
        update={"revision": snapshot.revision.model_copy(update={"form_layouts": (layout,)})}
    )
    rendered = add_form_workbook(build_export_plan(snapshot), snapshot)
    reference = SheetCellAddress.at(TabName.ENTRADAS, source.address.row, 4).qualified()
    assert any(cell.casilla_id is None and reference in cell.formula for cell in rendered.formula_cells)


def _grid_snapshot(snapshot, width, *, binding_id=None, missing_heading=False):
    casillas = snapshot.revision.casillas[:width]
    rows = [
        FormGridRow(
            key="activity",
            heading_key="test.activity",
            official_heading="Actividad económica",
            cells=tuple(FormCell(kind="casilla", casilla_id=casilla.id) for casilla in casillas),
        )
    ]
    if binding_id is not None:
        rows.append(
            FormGridRow(
                key="binding",
                heading_key="test.binding",
                official_heading="Dato de la actividad",
                cells=(
                    FormCell(kind="binding_input", binding_id=binding_id),
                    FormCell(kind="design_constant", literal="020", literal_decimals=2),
                    *(FormCell(kind="blank") for _ in range(width - 2)),
                ),
            )
        )
    grid = FormGridBlock(
        id="activity-grid",
        columns=tuple(
            FormGridColumn(
                key=f"column-{index}",
                heading_key=f"test.column-{index}",
                official_heading=None if missing_heading else f"Concepto de la columna {index}",
            )
            for index in range(1, width + 1)
        ),
        rows=tuple(rows),
    )
    layout = snapshot.revision.form_layouts[0]
    page = layout.pages[0]
    section = page.sections[0]
    section = section.model_copy(update={"blocks": (grid, *section.blocks[width:])})
    layout = layout.model_copy(update={"pages": (page.model_copy(update={"sections": (section,)}),)})
    return snapshot.model_copy(update={"revision": snapshot.revision.model_copy(update={"form_layouts": (layout,)})})


@pytest.mark.parametrize("width", (4, 7))
def test_wide_grid_keeps_all_columns_on_one_row_and_expands_canvas(form_source, width):
    snapshot, _ = form_source
    snapshot = _grid_snapshot(snapshot, width)
    source = build_export_plan(snapshot)
    rendered = add_form_workbook(source, snapshot)
    ids = {casilla.id for casilla in snapshot.revision.casillas[:width]}
    cells = [cell for cell in rendered.formula_cells if cell.address.tab is TabName.FORM and cell.casilla_id in ids]
    assert len(cells) == width
    assert len({cell.address.row for cell in cells}) == 1
    assert [cell.address.column for cell in cells] == [7 + 2 * index for index in range(width)]
    headings = [
        cell
        for cell in rendered.value_cells
        if cell.address.tab is TabName.FORM and str(cell.value).startswith("Concepto de la columna")
    ]
    assert len(headings) == width
    assert len({cell.address.row for cell in headings}) == 1
    protection = next(region for region in rendered.protected_ranges if region.tab is TabName.FORM)
    assert protection.end_column == 6 + 2 * width
    widths = [item for item in rendered.column_widths if item.tab is TabName.FORM]
    assert len(widths) == protection.end_column
    assert widths[-1].width == 3
    for original, projected in zip(source.formula_cells, rendered.formula_cells, strict=False):
        assert projected.address == original.address
        assert projected.formula == original.formula or projected.formula.endswith(f',"Sin dato",{original.formula})')


def test_supporting_calculations_guard_missing_inputs_without_changing_arithmetic(form_source):
    snapshot, plan = form_source
    rendered = add_form_workbook(plan, snapshot)
    original = next(cell for cell in plan.formula_cells if cell.casilla_id == "03")
    projected = next(cell for cell in rendered.formula_cells if cell.address == original.address)
    inputs = {
        cell.casilla_id: cell.address.qualified()
        for cell in plan.value_cells
        if cell.role == "operator_input" and cell.casilla_id in ("01", "02")
    }
    assert len(inputs) == 2
    for address in inputs.values():
        assert f"ISBLANK({address})" in projected.formula
    assert projected.formula.startswith("IF(")
    assert projected.formula.endswith(f',"Sin dato",{original.formula})')


def test_grid_binding_input_links_to_the_real_input_and_retains_constant(form_source):
    snapshot, source = form_source
    binding_ids = {binding.id for binding in snapshot.revision.bindings}
    label = next(
        cell
        for cell in source.value_cells
        if cell.address.tab is TabName.ENTRADAS and cell.address.column == 3 and cell.value in binding_ids
    )
    snapshot = _grid_snapshot(snapshot, 4, binding_id=label.value)
    rendered = add_form_workbook(build_export_plan(snapshot), snapshot)
    address = SheetCellAddress.at(TabName.ENTRADAS, label.address.row, 4).qualified()
    formula = next(
        cell for cell in rendered.formula_cells if cell.address.tab is TabName.FORM and cell.casilla_id is None
    )
    assert formula.address.column == 6
    assert formula.formula == f'IF(ISBLANK({address}),"Sin dato",{address})'
    constant = next(
        cell
        for cell in rendered.value_cells
        if cell.address.tab is TabName.FORM and cell.address.row == formula.address.row and cell.address.column == 8
    )
    assert str(constant.value) == "0.20"


def test_grid_refuses_unknown_binding_and_missing_headings(form_source):
    snapshot, _ = form_source
    unknown = _grid_snapshot(snapshot, 4, binding_id="unknown-binding")
    with pytest.raises(CalcSheetsEngineError, match="not declared by the revision"):
        add_form_workbook(build_export_plan(unknown), unknown)
    unnamed = _grid_snapshot(snapshot, 4, missing_heading=True)
    with pytest.raises(CalcSheetsEngineError, match="authored column heading"):
        add_form_workbook(build_export_plan(unnamed), unnamed)


def test_missing_layout_refused(form_source):
    snapshot, plan = form_source
    snapshot = snapshot.model_copy(update={"revision": snapshot.revision.model_copy(update={"form_layouts": ()})})
    with pytest.raises(CalcSheetsEngineError, match="exactly one"):
        add_form_workbook(plan, snapshot)


def test_duplicate_block_placement_refused(form_source):
    snapshot, plan = form_source
    layout = snapshot.revision.form_layouts[0]
    page = layout.pages[0]
    section = page.sections[0]
    section = section.model_copy(update={"blocks": (*section.blocks, section.blocks[0])})
    page = page.model_copy(update={"sections": (section,)})
    layout = layout.model_copy(update={"pages": (page,)})
    snapshot = snapshot.model_copy(
        update={"revision": snapshot.revision.model_copy(update={"form_layouts": (layout,)})}
    )
    with pytest.raises(CalcSheetsEngineError, match="duplicate"):
        add_form_workbook(plan, snapshot)


def test_real_saved_review_is_refused_without_recalculation(form_source):
    from ..review_workbook import build_review_workbook
    from .review_fixture import review_label, review_snapshot

    snapshot, _ = form_source
    baseline = build_review_workbook(
        review_snapshot(amount="99.75"),
        publication_id=UUID(int=2),
        exported_at=datetime(2026, 10, 5, tzinfo=UTC),
        label=review_label,
    )
    assert not baseline.formula_cells
    original_values = baseline.value_cells
    with pytest.raises(CalcSheetsEngineError, match="verified registry identity"):
        add_form_workbook(baseline, snapshot)
    assert baseline.value_cells == original_values


def test_computed_form_guards_transitive_blank_inputs(form_source):
    snapshot, plan = form_source
    rendered = add_form_workbook(plan, snapshot)
    computed = {c.casilla_id for c in plan.formula_cells}
    cells = [c for c in rendered.formula_cells if c.address.tab is TabName.FORM and c.casilla_id in computed]
    assert cells
    assert all("ISBLANK('Entradas'!" in c.formula for c in cells)


def test_other_revision_metadata_refused(form_source):
    snapshot, plan = form_source
    plan = plan.model_copy(update={"metadata": plan.metadata.model_copy(update={"modelo_id": "303"})})
    with pytest.raises(CalcSheetsEngineError, match="coordinate"):
        add_form_workbook(plan, snapshot)


def test_missing_placement_refused(form_source):
    snapshot, plan = form_source
    layout = snapshot.revision.form_layouts[0]
    layout = layout.model_copy(update={"placements": layout.placements[:-1]})
    snapshot = snapshot.model_copy(
        update={"revision": snapshot.revision.model_copy(update={"form_layouts": (layout,)})}
    )
    with pytest.raises(CalcSheetsEngineError, match="every revision casilla"):
        add_form_workbook(plan, snapshot)


def test_same_coordinate_different_registry_content_refused(form_source):
    snapshot, plan = form_source
    layout = snapshot.revision.form_layouts[0].model_copy(update={"generator_version": 2})
    snapshot = snapshot.model_copy(
        update={"revision": snapshot.revision.model_copy(update={"form_layouts": (layout,)})}
    )
    with pytest.raises(CalcSheetsEngineError, match="registry identity"):
        add_form_workbook(plan, snapshot)


def test_result_accent_uses_declared_settlement_not_last_auxiliary_row(form_source):
    from cadrumo.application.modelo.settlement_casilla import declaration_result_casillas

    snapshot, plan = form_source
    rendered = add_form_workbook(plan, snapshot)
    result = declaration_result_casillas(snapshot.modelo.id, snapshot.revision)
    assert result is not None
    expected = set(result.casilla_ids)
    highlighted_rows = {
        r.start_row for r in rendered.styled_ranges if r.tab is TabName.FORM and r.role is StyleRole.FORM_RESULT
    }
    highlighted = {
        c.casilla_id
        for c in rendered.formula_cells
        if c.address.tab is TabName.FORM and c.address.row in highlighted_rows
    }
    assert highlighted == expected


def test_printed_box_numbers_preserve_leading_zero_as_text(form_source):
    snapshot, plan = form_source
    rendered = add_form_workbook(plan, snapshot)
    box = next(c for c in rendered.value_cells if c.address.tab is TabName.FORM and c.value == "01")
    directives = [f for f in rendered.number_formats if f.address == box.address]
    assert directives[-1].data_type == "text"
    assert directives[-1].pattern == "@"


@pytest.mark.parametrize("width", [2, 4])
def test_repeated_grids_use_each_saved_record_without_scalar_leakage(form_source, width):
    snapshot, plan = form_source
    casillas = snapshot.revision.casillas[: width + 1]
    grid = FormGridBlock(
        id="calendar",
        columns=tuple(
            FormGridColumn(key=f"month-{i}", heading_key=f"test.month-{i}", official_heading=f"Mes {i}")
            for i in range(width)
        ),
        rows=(
            FormGridRow(
                key="amount",
                heading_key="test.amount",
                official_heading="Cotización",
                cells=tuple(FormCell(kind="casilla", casilla_id=c.id) for c in casillas[1:]),
            ),
        ),
    )
    block = FormRepeatingGroupBlock(
        id="members",
        row_source="export_record",
        export_record_id="members",
        columns=tuple(
            FormRepeatingColumn(
                key=f"field-{i}", heading_key=f"test.field-{i}", official_heading=f"Campo {i}", casilla_id=c.id
            )
            for i, c in enumerate(casillas)
        ),
        grids=(grid,),
    )
    layout = snapshot.revision.form_layouts[0]
    section = layout.pages[0].sections[0].model_copy(update={"blocks": (block,)})
    layout = layout.model_copy(update={"pages": (layout.pages[0].model_copy(update={"sections": (section,)}),)})
    rows = (
        ModeloFormRepeatingRow(index=1, values=("000123", Decimal(0), None, *([Decimal(12)] * (width - 2)))),
        ModeloFormRepeatingRow(index=2, values=("000456", Decimal("7.25"), Decimal(9), *([Decimal(34)] * (width - 2)))),
    )
    builder = _FormBuilder(
        plan, snapshot.revision, "130", plan.metadata.period, layout, lambda _: None, lambda _: (True, rows)
    )
    builder.repeating(block)
    cells = {(c.address.row, c.address.column): c.value for c in builder.values}
    assert cells[3, 9] == "000123"
    assert cells[5, 7] == Decimal(0)
    assert cells[5, 9] == "Sin dato"
    assert cells[7, 9] == "000456"
    assert cells[9, 7] == Decimal("7.25")
    assert cells[9, 9] == Decimal(9)
    assert not builder.formulas
    assert [c.value for c in builder.values].count("Cotización") == 2
    assert all(c.address.column < len(builder.column_widths) for c in builder.values)
    assert len([c for c in builder.values if c.value == "Campo 1"]) == 0
    original = next(c for c in plan.value_cells if c.casilla_id == casillas[1].id)
    source_formats = [f for f in plan.number_formats if f.address == original.address]
    assert source_formats
    assert any(
        f.address.row == 5 and f.address.column == 7 and f.pattern == source_formats[0].pattern for f in builder.formats
    )
