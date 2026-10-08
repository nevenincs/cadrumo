"""Historical registry cells use shared assembly without a filing snapshot."""

from datetime import date
from decimal import Decimal

import pytest

from cadrumo.application.storage.calc_sheets.engine import build_template_preview_plan
from cadrumo.application.storage.calc_sheets.layout import plan_layout
from cadrumo.application.storage.calc_sheets.records import (
    OperatorInput,
    OperatorInputs,
    SheetGuideContent,
    SheetTemplatePreviewMetadata,
    TabName,
)
from cadrumo.domain.calculations.registry.errors import FilingYearOutsideSupportEnvelopeError
from cadrumo.domain.calculations.registry.governed_fact_scope import validating_governed_facts

from ..compiler.authority import compiled_bundled_authority
from ..workbook_demo_refunds import build_historical_refund_plan, refund_inputs
from ..workbook_template_source import load_workbook_template_source

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]


def test_historical_232_assembly_preserves_real_registry_inputs_without_a_snapshot() -> None:
    authority = compiled_bundled_authority()
    with pytest.raises(FilingYearOutsideSupportEnvelopeError):
        authority.snapshot("232", filing_year=2017, period="0A", revision_id="2016-2017")
    source = load_workbook_template_source(
        "232", revision_id="2016-2017", source_ref="aeat-dr-232-2016", preview_year=2017, preview_period="0A"
    )
    revision = source.revision
    anchor = date(2017, 12, 31)
    with validating_governed_facts(authority):
        layout = plan_layout(revision, bracket_filter_date=anchor)
        plan = build_template_preview_plan(
            source,
            operator_inputs=OperatorInputs(values=(OperatorInput(casilla_id="decl.ejercicio", value=Decimal(2017)),)),
            guide=SheetGuideContent(title="Ejemplo ficticio", paragraphs=("No válido para presentar.",)),
        )
    assert isinstance(plan.metadata, SheetTemplatePreviewMetadata)
    assert plan.metadata.preview_year == 2017
    assert any(cell.casilla_id == "decl.ejercicio" and cell.value == Decimal(2017) for cell in plan.value_cells)
    assert not plan.formula_cells  # The registry declares reported amounts, not arithmetic.
    assert len(layout.binding_cells) >= 140
    assert all(address in plan.all_addresses() for address in layout.binding_cells.values())
    assert any(cell.address.tab is TabName.ENTRADAS and cell.value is None for cell in plan.value_cells)


def test_historical_308_preview_keeps_filing_refusal_and_real_formula() -> None:
    authority = compiled_bundled_authority()
    with pytest.raises(FilingYearOutsideSupportEnvelopeError):
        authority.snapshot("308", filing_year=2018, period="AD-HOC", revision_id="2016-2018")
    source, plan = build_historical_refund_plan()
    values = {v.casilla_id: v.value for v in refund_inputs(2018, historical=True).values}
    assert values["papel-nif"] == "12345678Z"
    assert values["papel-apellidos"] == "Ejemplo"
    assert not source.revision.export_layouts

    declared = next(c for c in plan.value_cells if c.casilla_id == "papel-importe-devolucion")
    assert declared.value == Decimal("250.35")
    assert any(c.casilla_id == declared.casilla_id for c in plan.formula_cells if c.address.tab is TabName.FORM)
    assert not any(c.casilla_id == declared.casilla_id for c in plan.formula_cells if c.address.tab is TabName.CALCULOS)
    assert isinstance(plan.metadata, SheetTemplatePreviewMetadata)
    assert plan.metadata.preview_year == 2018
    assert any(c.casilla_id == "papel-nif" for c in plan.formula_cells if c.address.tab is TabName.FORM)
    assert any(
        c.casilla_id == "decl.req-iva-devolver-17" for c in plan.formula_cells if c.address.tab is TabName.CALCULOS
    )


@pytest.mark.parametrize("year,revision_id", [(2010, "2009-2011-junio"), (2015, "2011-julio-2015")])
def test_old_308_preview_uses_complete_name_and_old_bank_account(year: int, revision_id: str) -> None:
    source, plan = build_historical_refund_plan(year=year)
    assert source.revision.id == revision_id
    assert plan.metadata.preview_year == year
    assert plan.metadata.preview_period == "AD-HOC"
    titles = [
        c.value
        for c in plan.value_cells
        if c.address.tab in (TabName.FORM, TabName.GUIDE)
        and isinstance(c.value, str)
        and c.value.startswith("Modelo 308 ·")
    ]
    assert titles == [f"Modelo 308 · {year}", f"Modelo 308 · {year}"]
    assert any(c.casilla_id == "papel-nombre-completo" and c.value == "Ana Ejemplo" for c in plan.value_cells)
    form_ids = {c.casilla_id for c in plan.formula_cells if c.address.tab is TabName.FORM}
    assert {"papel-nombre-completo", "decl.devolucion-ccc", "decl.req-iva-devolver-17"} <= form_ids
    assert not {"decl.devolucion-iban", "decl.tipo-tributacion", "decl.nombre"} & form_ids
    assert not source.revision.export_layouts
