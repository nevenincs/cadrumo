"""Historical registry cells use shared assembly without a filing snapshot."""

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
from cadrumo.domain.calculations.registry.temporal import RevisionSelectionMetadata
from cadrumo.domain.calculations.registry.tests.authored_editions import authored_revisions, filing_year_envelope

from ..compiler.authority import compiled_bundled_authority
from ..workbook_demo_refunds import build_historical_refund_plan, refund_inputs
from ..workbook_template_source import load_workbook_template_source

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]


def _historical_revisions(modelo: str) -> tuple[RevisionSelectionMetadata, ...]:
    """Return the authored editions that end below the support floor, oldest first."""
    floor = filing_year_envelope().floor
    return tuple(
        revision
        for revision in authored_revisions(modelo)
        if revision.valid_to is not None and revision.valid_to.year < floor
    )


def _last_full_exercise(revision: RevisionSelectionMetadata) -> int:
    """Return the last calendar year one closed edition governs from January to December."""
    assert revision.valid_to is not None
    return (
        revision.valid_to.year
        if (revision.valid_to.month, revision.valid_to.day) == (12, 31)
        else revision.valid_to.year - 1
    )


def test_historical_232_assembly_preserves_real_registry_inputs_without_a_snapshot() -> None:
    authority = compiled_bundled_authority()
    historical = _historical_revisions("232")[-1]
    year = _last_full_exercise(historical)
    revision_id = str(historical.id)
    with pytest.raises(FilingYearOutsideSupportEnvelopeError):
        authority.snapshot("232", filing_year=year, period="0A", revision_id=revision_id)
    source = load_workbook_template_source(
        "232", revision_id=revision_id, source_ref="aeat-dr-232-2016", preview_year=year, preview_period="0A"
    )
    revision = source.revision
    anchor = historical.valid_to
    with validating_governed_facts(authority):
        layout = plan_layout(revision, bracket_filter_date=anchor)
        plan = build_template_preview_plan(
            source,
            operator_inputs=OperatorInputs(values=(OperatorInput(casilla_id="decl.ejercicio", value=Decimal(year)),)),
            guide=SheetGuideContent(title="Ejemplo ficticio", paragraphs=("No válido para presentar.",)),
        )
    assert isinstance(plan.metadata, SheetTemplatePreviewMetadata)
    assert plan.metadata.preview_year == year
    assert any(cell.casilla_id == "decl.ejercicio" and cell.value == Decimal(year) for cell in plan.value_cells)
    assert not plan.formula_cells  # The registry declares reported amounts, not arithmetic.
    assert len(layout.binding_cells) >= 140
    assert all(address in plan.all_addresses() for address in layout.binding_cells.values())
    assert any(cell.address.tab is TabName.ENTRADAS and cell.value is None for cell in plan.value_cells)


def test_historical_308_preview_keeps_filing_refusal_and_real_formula() -> None:
    authority = compiled_bundled_authority()
    historical = _historical_revisions("308")[-1]
    year = _last_full_exercise(historical)
    with pytest.raises(FilingYearOutsideSupportEnvelopeError):
        authority.snapshot("308", filing_year=year, period="0A", revision_id=str(historical.id))
    source, plan = build_historical_refund_plan(year=year)
    values = {v.casilla_id: v.value for v in refund_inputs(year, historical=True).values}
    assert values["papel-nif"] == "12345678Z"
    assert values["papel-apellidos"] == "Ejemplo"
    assert not source.revision.export_layouts

    declared = next(c for c in plan.value_cells if c.casilla_id == "papel-importe-devolucion")
    assert declared.value == Decimal("250.35")
    assert any(c.casilla_id == declared.casilla_id for c in plan.formula_cells if c.address.tab is TabName.FORM)
    assert not any(c.casilla_id == declared.casilla_id for c in plan.formula_cells if c.address.tab is TabName.CALCULOS)
    assert isinstance(plan.metadata, SheetTemplatePreviewMetadata)
    assert plan.metadata.preview_year == year
    assert any(c.casilla_id == "papel-nif" for c in plan.formula_cells if c.address.tab is TabName.FORM)
    assert any(
        c.casilla_id == "decl.req-iva-devolver-17" for c in plan.formula_cells if c.address.tab is TabName.CALCULOS
    )


@pytest.mark.parametrize(
    "year,revision_id",
    # aeat-dr-308-2009 admits only the quarters; the July 2011 design adds 0A.
    [(_last_full_exercise(revision), str(revision.id)) for revision in _historical_revisions("308")[:2]],
)
def test_old_308_preview_uses_complete_name_and_old_bank_account(year: int, revision_id: str) -> None:
    source, plan = build_historical_refund_plan(year=year)
    assert source.revision.id == revision_id
    assert plan.metadata.preview_year == year
    # The preview is the annual return where the edition serves one, and
    # otherwise the edition's first period that year: a quarters-only design
    # never previews a period it does not lay out.
    served = tuple(str(token) for token in source.revision.period_selector.periods_for_year(year))
    period = "0A" if "0A" in served else served[0]
    assert plan.metadata.preview_period == period
    titles = [
        c.value
        for c in plan.value_cells
        if c.address.tab in (TabName.FORM, TabName.GUIDE)
        and isinstance(c.value, str)
        and c.value.startswith("Modelo 308 ·")
    ]
    assert {TabName.FORM, TabName.GUIDE} <= set(plan.tabs)
    assert titles == [f"Modelo 308 · {year} · {period}"], titles
    assert any(c.casilla_id == "papel-nombre-completo" and c.value == "Ana Ejemplo" for c in plan.value_cells)
    form_ids = {c.casilla_id for c in plan.formula_cells if c.address.tab is TabName.FORM}
    assert {"papel-nombre-completo", "decl.devolucion-ccc", "decl.req-iva-devolver-17"} <= form_ids
    assert not {"decl.devolucion-iban", "decl.tipo-tributacion", "decl.nombre"} & form_ids
    assert not source.revision.export_layouts
