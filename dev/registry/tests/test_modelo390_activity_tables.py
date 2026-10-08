"""Official module and agricultural rows keep independent registry bindings."""

from decimal import Decimal
from io import BytesIO

import pytest
from openpyxl import load_workbook

from cadrumo.adapters.outbound.workbook.calc_sheets_xlsx import materialize_export_plan
from cadrumo.application.storage.calc_sheets.engine import build_export_plan
from cadrumo.application.storage.calc_sheets.form_workbook import add_form_workbook
from cadrumo.application.storage.calc_sheets.layout import plan_layout
from cadrumo.application.storage.calc_sheets.records import TabName

from ..workbook_demo import DemoCase, demonstration_snapshot

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]


@pytest.mark.parametrize("year", (2024, 2025))
def test_activity_tables_preserve_all_58_independent_live_sources(year: int) -> None:
    snapshot = demonstration_snapshot(DemoCase("390", str(year), None, None, filing_year=year, period="0A"))
    page = next(p for p in snapshot.revision.form_layouts[0].pages if p.id == "pag-5")
    assert page.official_ref is not None and "136900" in page.official_ref
    grids = []
    for activity in (1, 2):
        section = next(s for s in page.sections if s.id == f"6-operaciones-reg-simplificado-actividad-{activity}")
        prefix = f"modelo-390.page_5.operaciones-reg-simplificado-actividad-{activity}-"
        identity = section.blocks[0]
        assert identity.kind == "field" and identity.binding_id == prefix + "epigrafe-i-a-e"
        grid = section.blocks[1]
        assert grid.kind == "grid" and len(grid.rows) == 7
        summary_fields = section.blocks[2:]
        assert all(b.kind == "field" and b.binding_id and b.binding_id.startswith(prefix) for b in summary_fields)
        summary_ids = [b.binding_id for b in summary_fields if b.kind == "field"]
        assert prefix + "c-cuota-devengada-operaciones-corrientes" == summary_ids[0]
        assert prefix + f"cuota-derivada-regimen-simplificado-j{activity}" in summary_ids
        reduction = prefix + "reduccion-aplicable-por-actividad-realizada-en-el-termin"
        assert (reduction in summary_ids) == (year == 2024)
        for module, row in enumerate(grid.rows, 1):
            assert [c.binding_id for c in row.cells] == [
                f"modelo-390.page_5.operaciones-reg-simplificado-actividad-{activity}-a-no-unidades-modulo-{module}",
                f"modelo-390.page_5.operaciones-reg-simplificado-actividad-{activity}-b-importe-modulo-{module}",
            ]
        grids.append(grid)
    section = next(s for s in page.sections if s.id == "6-operaciones-reg-simplificado-act-agrico-8df6bd")
    agricultural = section.blocks[0]
    assert agricultural.kind == "grid" and len(agricultural.rows) == 5
    for activity, row in enumerate(agricultural.rows, 1):
        suffixes = (
            "codigo",
            "volumen-ingresos",
            "indice-cuota",
            "cuota-devengada",
            "cuota-soportada",
            "cuota-derivada-regimen-simpl" if activity == 5 else "cuota-derivada-regimen-simplif",
        )
        assert [c.binding_id for c in row.cells] == [
            f"modelo-390.page_5.operaciones-reg-simplificado-act-agricolas-y-ganaderas-actividad-{activity}-{suffix}"
            for suffix in suffixes
        ]
    grids.append(agricultural)
    layout = plan_layout(snapshot.revision)
    seeded = {}
    row_sources = []
    for grid in grids:
        for row in grid.rows:
            addresses = []
            for cell in row.cells:
                assert cell.binding_id is not None
                address = layout.binding_cells[cell.binding_id]
                value = f"0{len(seeded):02}" if cell.binding_id.endswith("-codigo") else Decimal(len(seeded))
                seeded[address] = None if len(seeded) == 57 else value
                addresses.append(address)
            row_sources.append(addresses)
    assert len(seeded) == 58
    source = build_export_plan(snapshot)
    source = source.model_copy(
        update={
            "value_cells": tuple(
                c.model_copy(update={"value": seeded[c.address]}) if c.address in seeded else c
                for c in source.value_cells
            )
        }
    )
    plan = add_form_workbook(source, snapshot)
    workbook = load_workbook(BytesIO(materialize_export_plan(plan)), data_only=False)
    for addresses in row_sources:
        targets = []
        for address in addresses:
            assert workbook[address.tab.value][address.a1].value == seeded[address]
            formula = f'IF(ISBLANK({address.qualified()}),"Sin dato",{address.qualified()})'
            matches = [c for c in plan.formula_cells if c.address.tab is TabName.FORM and c.formula == formula]
            assert len(matches) == 1
            targets.append(matches[0].address)
            assert workbook[TabName.FORM.value][matches[0].address.a1].value == "=" + formula
        assert len({a.row for a in targets}) == 1
        assert len({a.column for a in targets}) == len(addresses)
