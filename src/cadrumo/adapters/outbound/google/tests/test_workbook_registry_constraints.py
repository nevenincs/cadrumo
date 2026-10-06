"""Shared text constraints reach both transports without development dependencies."""

from datetime import UTC, datetime
from io import BytesIO

import pytest
from openpyxl import load_workbook

from .....application.storage.calc_sheets.records import (
    SheetCellAddress,
    SheetCellConstraint,
    SheetExportPlan,
    SheetGuideContent,
    SheetTemplatePreviewMetadata,
    SheetValueCell,
    TabName,
)
from ...workbook.calc_sheets_xlsx import materialize_export_plan
from .._calc_sheets_apply_formatting import build_cell_constraint_requests

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


@pytest.mark.parametrize("allowed,limit", [(("A", "B"), None), (("B",), None), (None, 24)])
def test_unknown_input_keeps_identical_strict_constraint_in_both_transports(allowed, limit) -> None:
    address = SheetCellAddress.at(TabName.ENTRADAS, 2, 4)
    constraint = SheetCellConstraint(
        address=address,
        casilla_id="input",
        legal_refs=("test:source",),
        allowed_values=allowed,
        max_length=limit,
    )
    plan = SheetExportPlan[SheetTemplatePreviewMetadata](
        metadata=SheetTemplatePreviewMetadata(
            kind="template_preview",
            modelo_id="188",
            revision_id="2022",
            preview_year=2022,
            preview_period="0A",
            template_digest="a" * 64,
            engine_version="test",
            title="Ejemplo ficticio",
            exported_at=datetime(2026, 10, 6, tzinfo=UTC),
        ),
        human_presentation=True,
        tabs=(TabName.ENTRADAS,),
        value_cells=(SheetValueCell(address=address, value=None, role="operator_input"),),
        cell_constraints=(constraint,),
        guide=SheetGuideContent(title="Ejemplo ficticio", paragraphs=("No válido para presentar.",)),
    )
    requests = build_cell_constraint_requests(plan.cell_constraints, sheet_id_by_tab={"Entradas": 101})
    rule = requests[0]["setDataValidation"]["rule"]
    assert rule["strict"] and rule["condition"]["type"] == "CUSTOM_FORMULA"
    workbook = load_workbook(BytesIO(materialize_export_plan(plan)), data_only=False)
    assert workbook["Entradas"]["D2"].value is None
    validation = next(v for v in workbook["Entradas"].data_validations.dataValidation if "D2" in v.sqref)
    assert validation.type == "custom" and validation.errorStyle == "stop"
    formula = validation.formula1
    assert rule["condition"]["values"][0]["userEnteredValue"] == "=" + formula
    assert "ISBLANK(D2)" in formula
    if allowed:
        assert all(f'EXACT(D2,"{value}")' in formula for value in allowed)
    if limit:
        assert "LEN(D2)<=24" in formula
