"""Historical presentation compiles its own registry amounts into real workbook cells."""

from decimal import Decimal
from io import BytesIO

import pytest
from openpyxl import load_workbook

from cadrumo.adapters.outbound.workbook.calc_sheets_xlsx import materialize_export_plan
from cadrumo.application.storage.calc_sheets.engine import build_export_plan
from cadrumo.application.storage.calc_sheets.form_workbook import add_form_workbook
from cadrumo.application.storage.calc_sheets.records import OperatorInput, OperatorInputs, TabName

from ..workbook_demo import DemoCase, demonstration_snapshot

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]


@pytest.mark.parametrize("year", (2022, 2023))
def test_historical_deduction_rows_keep_live_amounts_and_adjacent_subtotals(year):
    snapshot = demonstration_snapshot(DemoCase("390", str(year), None, None, filing_year=year, period="0A"))
    form = snapshot.revision.form_layouts[0]
    page = next(p for p in form.pages if p.id == "pag-3")
    amounts: dict[str, Decimal] = {}
    for index, section in enumerate(page.sections):
        grid = section.blocks[0]
        assert grid.kind == "grid"
        for row_index, row in enumerate(grid.rows[:4]):
            for column, cell in enumerate(row.cells):
                assert cell.casilla_id is not None
                amounts[cell.casilla_id] = Decimal(index * 100 + row_index * 10 + column)
    assert len(amounts) == 72 and Decimal(0) in amounts.values()
    # One field deliberately remains unknown rather than receiving a fabricated zero.
    missing = next(reversed(amounts))
    del amounts[missing]
    inputs = OperatorInputs(values=tuple(OperatorInput(casilla_id=k, value=v) for k, v in amounts.items()))
    plan = add_form_workbook(build_export_plan(snapshot, operator_inputs=inputs), snapshot)
    workbook = load_workbook(BytesIO(materialize_export_plan(plan)), data_only=False)
    sources = {c.casilla_id: c for c in plan.value_cells if c.role == "operator_input"}
    rendered = {c.casilla_id: c for c in plan.formula_cells if c.address.tab is TabName.FORM}
    for owner in (*amounts, missing):
        source, target = sources[owner], rendered[owner]
        assert source.value == amounts.get(owner)
        assert workbook[source.address.tab.value][source.address.a1].value == amounts.get(owner)
        assert target.formula == f'IF(ISBLANK({source.address.qualified()}),"Sin dato",{source.address.qualified()})'
        assert workbook[TabName.FORM.value][target.address.a1].value == "=" + target.formula
    for section in page.sections:
        grid = section.blocks[0]
        assert grid.kind == "grid"
        for row in grid.rows:
            addresses = [rendered[c.casilla_id].address for c in row.cells]
            assert addresses[0].row == addresses[1].row
            assert addresses[0].column < addresses[1].column
        for column in (0, 1):
            last_rate = rendered[grid.rows[-2].cells[column].casilla_id].address
            subtotal = rendered[grid.rows[-1].cells[column].casilla_id].address
            assert subtotal.row == last_rate.row + 1 and subtotal.column == last_rate.column
