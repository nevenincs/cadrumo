"""The compensation table follows the printed Annex II row relationships."""

from pathlib import Path

import pytest

from cadrumo.domain.calculations.registry.schema_form_layouts import FormGridBlock

from ...compiler.form_layout_integrity import form_layout_failures
from ...compiler.loader import load_modelo_directory

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


@pytest.mark.parametrize("revision_id", ["2005-2015", "2016-y-siguientes"])
def test_compensation_rows_preserve_official_operands_and_total(revision_id: str) -> None:
    revision = load_modelo_directory(Path("src/cadrumo/_data/registry/aeat/modelos/341")).revisions[revision_id]
    (layout,) = revision.form_layouts
    assert form_layout_failures(revision) == ()
    section = next(section for section in layout.pages[0].sections if section.id == "compensacion")
    grid, total = section.blocks
    assert isinstance(grid, FormGridBlock)
    assert [[cell.casilla_id for cell in row.cells] for row in grid.rows] == [
        ["01", "04", "07"],
        ["02", "05", "08"],
        ["03", "06", "09"],
    ]
    assert total.kind == "field" and total.casilla_id == "10"
    assert {placement.casilla_id for placement in layout.placements} == {item.id for item in revision.casillas}
    assert not any(placement.workbook_exclusion for placement in layout.placements)
    assert layout.review.state == "generated"
    assert layout.review.notes is not None and "review pending" in layout.review.notes


def test_historical_account_and_submission_inputs_are_not_dropped() -> None:
    revision = load_modelo_directory(Path("src/cadrumo/_data/registry/aeat/modelos/341")).revisions["2005-2015"]
    sections = revision.form_layouts[0].pages[0].sections
    assert {block.casilla_id for section in sections for block in section.blocks if block.kind == "field"} >= {
        "wire.codigo-cuenta-cliente",
        "wire.letras-etiqueta",
        "wire.observaciones",
    }


@pytest.mark.parametrize("revision_id", ["2005-2015", "2016-y-siguientes"])
def test_taxpayer_identity_is_not_replaced_by_contact_person(revision_id: str) -> None:
    revision = load_modelo_directory(Path("src/cadrumo/_data/registry/aeat/modelos/341")).revisions[revision_id]
    sections = {section.id: section for section in revision.form_layouts[0].pages[0].sections}
    identity_fields = [
        block.export_field_id for block in sections["identificacion"].blocks if block.kind == "context_field"
    ]
    assert not any("contacto" in field for field in identity_fields)
    assert any(field.endswith("-nif") for field in identity_fields)
    refund = sections["devolucion"].blocks
    assert refund[0].kind == "field" and refund[0].casilla_id == "10"
    if revision_id == "2005-2015":
        assert len(refund) == 2 and refund[1].kind == "field"
        assert refund[1].casilla_id == "wire.codigo-cuenta-cliente"
    else:
        assert {block.export_field_id for block in refund if block.kind == "context_field"} == {
            "modelo-341-p01-iban",
            "modelo-341-p01-swift-bic",
        }


def test_paper_fields_have_no_electronic_or_calculation_owner() -> None:
    modelo = load_modelo_directory(Path("src/cadrumo/_data/registry/aeat/modelos/341"))
    historical = modelo.revisions["2005-2015"]
    paper = [item for item in historical.casillas if item.id.startswith("papel-")]
    assert len(paper) == 14
    for item in paper:
        assert item.input_kind == "informational" and not item.required
        assert not item.export_refs and item.binding is None and item.formula is None
        assert "boe-modelo-341-2000-form-pdf" in item.source_refs
    assert not any(item.id.startswith("papel-") for item in modelo.revisions["2016-y-siguientes"].casillas)
    assert next(item for item in paper if item.id == "papel-domicilio-codigo-postal").data_type == "text"


@pytest.mark.parametrize("revision_id", ["2005-2015", "2016-y-siguientes"])
def test_refund_reuses_total_in_a_declared_alias_without_second_input(revision_id: str) -> None:
    revision = load_modelo_directory(Path("src/cadrumo/_data/registry/aeat/modelos/341")).revisions[revision_id]
    (layout,) = revision.form_layouts
    total = next(item for item in revision.casillas if item.id == "10")
    assert total.input_kind == "computed"
    placement = next(item for item in layout.placements if item.casilla_id == "10")
    assert len(placement.aliases) == 1
    assert placement.aliases[0].section_id == "devolucion"
