"""Modelo 309 follows the printed 2023 form, not fixed-width byte offsets."""

from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.formula_runtime import evaluate_expression
from cadrumo.domain.calculations.registry.schema import FormulaDefinition
from cadrumo.domain.calculations.registry.schema_form_layouts import (
    FormContextFieldBlock,
    FormFieldBlock,
    FormGridBlock,
)

from ...compiler.form_layout_integrity import form_layout_failures
from ...compiler.loader import load_modelo_directory

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_2023_grid_preserves_the_inserted_official_rate_row() -> None:
    revision = load_modelo_directory(Path("src/cadrumo/_data/registry/aeat/modelos/309")).revisions["2023-y-siguientes"]
    (layout,) = revision.form_layouts
    assert form_layout_failures(revision) == ()
    sections = {section.id: section for page in layout.pages for section in page.sections}
    grid = sections["liquidacion"].blocks[0]
    assert isinstance(grid, FormGridBlock)
    assert [column.key for column in grid.columns] == ["base", "tipo", "cuota"]
    assert [[str(cell.casilla_id).rsplit("-", 1)[-1] for cell in row.cells] for row in grid.rows] == [
        ["01", "02", "03"],
        ["25", "26", "27"],
        ["04", "05", "06"],
        ["07", "08", "09"],
        ["10", "11", "12"],
        ["13", "14", "15"],
        ["16", "17", "18"],
        ["19", "20", "21"],
    ]
    assert {placement.casilla_id for placement in layout.placements} == {c.id for c in revision.casillas}
    positions = {placement.casilla_id: placement.box_number for placement in layout.placements}
    for cid in ("decl.complementaria", "decl.situacion-tributaria", "decl.hecho-imponible", "decl.tipo-declaracion"):
        assert positions[cid] is None
    assert positions["decl.resultado-24"] == "24"


def test_2023_identity_and_choices_have_declared_semantic_owners() -> None:
    revision = load_modelo_directory(Path("src/cadrumo/_data/registry/aeat/modelos/309")).revisions["2023-y-siguientes"]
    sections = {section.id: section for page in revision.form_layouts[0].pages for section in page.sections}
    contexts = [block for block in sections["identificacion"].blocks if isinstance(block, FormContextFieldBlock)]
    assert {block.export_field_id for block in contexts} == {"modelo-309-p1-nif", "modelo-309-p1-apellidos"}
    fields = {
        field.id: field for layout in revision.export_layouts for record in layout.records for field in record.fields
    }
    assert fields["modelo-309-p1-nif"].producer_key == "taxpayer.tax_id"
    assert fields["modelo-309-p1-apellidos"].producer_key == "taxpayer.full_name"
    casillas = {c.id: c for c in revision.casillas}
    for section_id in ("situacion", "hecho"):
        (block,) = sections[section_id].blocks
        assert isinstance(block, FormFieldBlock)
        assert [choice.value for choice in block.choices] == ["1", "2", "3", "4", "5", "6"]
        assert block.casilla_id is not None
        casilla = casillas[block.casilla_id]
        assert casilla.constraints is not None
        assert set(casilla.constraints.enum or ()) == {choice.value for choice in block.choices}
        invalid = casilla.model_copy(update={"constraints": None})
        changed = revision.model_copy(
            update={"casillas": tuple(invalid if c.id == invalid.id else c for c in revision.casillas)}
        )
        assert any("requires a closed text casilla domain" in failure for failure in form_layout_failures(changed))


def test_total_includes_the_new_quota_and_missing_does_not_mean_zero() -> None:
    revision = load_modelo_directory(Path("src/cadrumo/_data/registry/aeat/modelos/309")).revisions["2023-y-siguientes"]
    total = next(formula for formula in revision.formulas if formula.target_casilla_id == "decl.cuota-devengada-22")
    result = next(formula for formula in revision.formulas if formula.target_casilla_id == "decl.resultado-24")
    values = {
        "decl.rg-cuota-03": Decimal("10"),
        "decl.rg-cuota-27": Decimal("20"),
        "decl.rg-cuota-06": Decimal("30"),
        "decl.rg-cuota-09": Decimal("40"),
        "decl.re-cuota-12": Decimal("50"),
        "decl.re-cuota-15": Decimal("60"),
        "decl.re-cuota-18": Decimal("70"),
        "decl.re-cuota-21": Decimal("80"),
        "decl.a-deducir-23": Decimal("25"),
    }

    def evaluate(formula: FormulaDefinition) -> Decimal:
        return evaluate_expression(
            formula.expression,
            values=values,
            binding_values={},
            parameters={},
            date_context={},
            relation_values={},
            unresolved_relation_ids=frozenset(),
            unresolved_casilla_ids=set(),
            operand_refs=[],
            operand_casilla_refs=[],
            operand_values=[],
        )

    values["decl.cuota-devengada-22"] = evaluate(total)
    assert values["decl.cuota-devengada-22"] == Decimal("360")
    assert evaluate(result) == Decimal("335")
    values["decl.rg-cuota-27"] = Decimal("0")
    assert evaluate(total) == Decimal("340")
    del values["decl.rg-cuota-27"]
    with pytest.raises(RegistryValidationError, match="referenced before evaluation"):
        evaluate(total)


def test_signature_and_payment_use_paper_fields_without_filing_side_effects() -> None:
    modelo = load_modelo_directory(Path("src/cadrumo/_data/registry/aeat/modelos/309"))
    paper_ids = {"firma-lugar", "firma-fecha", "firma", "papel-forma-pago"}
    for revision in modelo.revisions.values():
        paper = [c for c in revision.casillas if c.id in paper_ids]
        assert len(paper) == 4
        assert all(c.input_kind.value == "informational" and not c.required for c in paper)
        assert all(not c.export_refs and c.formula is None and c.binding is None for c in paper)
        assert paper_ids <= set(revision.constructs[0].casilla_ids)
    revision = modelo.revisions["2023-y-siguientes"]
    layout = revision.form_layouts[0]
    sections = {section.id: section for page in layout.pages for section in page.sections}
    payment = sections["ingreso"].blocks
    assert [block.casilla_id for block in payment if isinstance(block, FormFieldBlock)] == [
        "decl.resultado-24",
        "papel-forma-pago",
        "decl.iban",
    ]
    declaration_type = sections["datos-presentacion"].blocks[0]
    assert isinstance(declaration_type, FormFieldBlock)
    assert declaration_type.casilla_id == "decl.tipo-declaracion"
    placement = next(p for p in layout.placements if p.casilla_id == "decl.resultado-24")
    assert [(alias.page_id, alias.section_id) for alias in placement.aliases] == [("m30901", "ingreso")]
    assert form_layout_failures(revision) == ()


def test_2018_layout_does_not_import_the_later_rate_row_or_presenter_identity() -> None:
    revision = load_modelo_directory(Path("src/cadrumo/_data/registry/aeat/modelos/309")).revisions["2018-2022"]
    layout = revision.form_layouts[0]
    assert revision.authority_grade is not None
    assert revision.authority_grade.value == "applicability"
    assert form_layout_failures(revision) == ()
    assert {p.casilla_id for p in layout.placements} == {c.id for c in revision.casillas}
    assert not any(p.kind.value == "unplaced" for p in layout.placements)
    assert {p.box_number for p in layout.placements}.isdisjoint({"25", "26", "27", "1016", "200", "201"})
    section = next(s for page in layout.pages for s in page.sections if s.id == "liquidacion")
    grid = section.blocks[0]
    assert isinstance(grid, FormGridBlock)
    assert [row.key for row in grid.rows] == ["rg-01", "rg-04", "rg-07", "re-10", "re-13", "re-16", "re-19"]
    nif = next(
        f
        for export in revision.export_layouts
        for record in export.records
        for f in record.fields
        if f.id == "modelo-309-p1-nif"
    )
    assert nif.producer_key == "taxpayer.tax_id"
