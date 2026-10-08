"""Modelo 322 preserves the printed grids and keeps supporting figures separate."""

from decimal import Decimal
from functools import cache
from pathlib import Path

import pytest

from cadrumo.core.i18n.render import lookup_translation
from cadrumo.domain.calculations.registry.form_context import resolve_form_context_field
from cadrumo.domain.calculations.registry.schema import ModeloRevision
from cadrumo.domain.calculations.registry.schema_form_layouts import (
    FormContextFieldBlock,
    FormFieldBlock,
    FormGridBlock,
)

from ...compiler.form_layout_integrity import form_layout_failures
from ...compiler.loader import load_modelo_directory

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


@cache
def _revision() -> ModeloRevision:
    return load_modelo_directory(Path("src/cadrumo/_data/registry/aeat/modelos/322")).revisions["2026-y-siguientes"]


def _grids() -> dict[str, FormGridBlock]:
    return {
        block.id: block
        for page in _revision().form_layouts[0].pages
        for section in page.sections
        for block in section.blocks
        if isinstance(block, FormGridBlock)
    }


def test_322_printed_rows_keep_base_rate_and_amount_correlated() -> None:
    grid = _grids()["devengado"]
    assert [[cell.casilla_id for cell in row.cells] for row in grid.rows] == [
        ["159", "160", "161"],
        ["171", "172", "173"],
        ["01", "02", "03"],
        ["162", "163", "164"],
        ["04", "05", "06"],
        ["07", "08", "09"],
        ["10", None, "11"],
        ["150", "151", "152"],
        ["165", "166", "167"],
        ["12", "13", "14"],
        ["153", "154", "155"],
        ["15", "16", "17"],
        ["18", "19", "20"],
        ["21", None, "22"],
        ["23", None, "24"],
        ["25", None, "26"],
        ["156", "157", "158"],
        ["168", "169", "170"],
        ["27", "28", "29"],
        ["30", "31", "32"],
        ["33", "34", "35"],
        ["36", None, "37"],
    ]
    assert [column.key for column in grid.columns] == ["base", "tipo", "cuota"]


def test_322_annual_and_deduction_sections_follow_the_official_pages() -> None:
    layout = _revision().form_layouts[0]
    assert len(layout.pages) == 4
    annual = layout.pages[2]
    assert annual.condition == "period_restricted"
    assert annual.condition_periods == ("12",)
    assert [section.id for section in annual.sections] == ["actividades", "territorio", "anuales"]
    grids = _grids()
    assert len(grids["prorrata"].rows) == 5
    assert [cell.casilla_id for cell in grids["prorrata"].rows[-1].cells] == ["520", "521", "522", "523", "524"]
    assert [cell.casilla_id for cell in grids["grupo-1"].rows[-1].cells] == ["714", "715"]
    assert [cell.casilla_id for cell in grids["grupo-2"].rows[-1].cells] == ["732", "733"]
    assert len(grids["actividades"].rows) == 6


def test_322_complete_accounting_does_not_claim_missing_paper_data_or_calculations() -> None:
    revision = _revision()
    layout = revision.form_layouts[0]
    assert form_layout_failures(revision) == ()
    assert len(layout.placements) == len(revision.casillas) == 229
    assert {p.casilla_id for p in layout.placements if p.kind == "working_figure"} == {
        c.id for c in revision.casillas if str(c.id).startswith("iva.")
    }
    assert all(p.box_number is None for p in layout.placements if not str(p.casilla_id).isdigit())
    assert layout.review.state == "generated"
    assert "February2026" in (layout.review.notes or "")
    assert "65 applies the declared territorial percentage64" in (layout.review.notes or "")
    assert "no-activity marker" in (layout.review.notes or "")
    fields = [
        block
        for page in layout.pages
        for section in page.sections
        for block in section.blocks
        if isinstance(block, FormContextFieldBlock)
    ]
    assert {resolve_form_context_field(revision, block).producer_key for block in fields} == {
        "taxpayer.tax_id",
        "taxpayer.surnames_or_legal_name",
        "amendment_evidence.is_complementaria",
        "amendment_evidence.original_aeat_receipt",
    }


@pytest.mark.parametrize("locale", ["es", "en", "ca", "hu"])
def test_322_authored_headings_are_translated(locale: str) -> None:
    layout = _revision().form_layouts[0]
    keys = {page.heading_key for page in layout.pages}
    for page in layout.pages:
        for section in page.sections:
            keys.add(section.heading_key)
            for block in section.blocks:
                if isinstance(block, FormGridBlock):
                    keys.update(column.heading_key for column in block.columns)
                    keys.update(row.heading_key for row in block.rows)
                elif isinstance(block, FormContextFieldBlock):
                    keys.add(block.heading_key)
                elif isinstance(block, FormFieldBlock):
                    keys.update(choice.heading_key for choice in block.choices)
    assert all(lookup_translation(key, locale=locale) for key in keys)


def test_322_missing_advance_payment_placement_is_rejected() -> None:
    revision = _revision()
    layout = revision.form_layouts[0]
    broken = layout.model_copy(update={"placements": tuple(p for p in layout.placements if p.casilla_id != "112")})
    assert form_layout_failures(revision.model_copy(update={"form_layouts": (broken,)}))


def test_322_activity_declaration_has_one_manual_owner_in_form_and_export() -> None:
    revision = _revision()
    owner = next(c for c in revision.casillas if c.id == "decl.sin-actividad")
    assert owner.input_kind == "manual"
    assert owner.formula is None and owner.binding is None
    assert owner.constraints is not None and set(owner.constraints.enum or ()) == {"X", ""}
    section = revision.form_layouts[0].pages[1].sections[-1]
    assert section.id == "sin-actividad"
    assert len(section.blocks) == 1
    block = section.blocks[0]
    assert isinstance(block, FormFieldBlock) and block.casilla_id == owner.id
    marker = next(
        f
        for layout in revision.export_layouts
        for record in layout.records
        for f in record.fields
        if f.id == "modelo-322-page-02-338"
    )
    assert marker.kind == "casilla" and marker.casilla_id == owner.id
    assert marker.computed_key is None


@pytest.mark.parametrize(
    "box", [str(n) for n in (153, 154, 155, 162, 163, 164, 165, 166, 167, 168, 169, 170, 171, 172, 173)]
)
def test_322_note_five_boxes_refuse_nonzero_amounts(box: str) -> None:
    """DR32201 Note5 fixes these fifteen boxes to zero, not other rate rows."""
    owner = next(c for c in _revision().casillas if c.id == box)
    assert owner.constraints is not None
    assert owner.constraints.violates(Decimal("0")) is None
    assert owner.constraints.violates(Decimal("0.01")) is not None
    assert owner.constraints.violates(Decimal("-0.01")) is not None
    assert "aeat-dr-322-2026" in owner.constraints.source_refs
    previous = load_modelo_directory(Path("src/cadrumo/_data/registry/aeat/modelos/322")).revisions["2024-2025"]
    assert next(c for c in previous.casillas if c.id == box).constraints is None


def test_322_prorrata_election_and_revocation_keep_one_exclusive_owner() -> None:
    revision = _revision()
    identity = revision.form_layouts[0].pages[0].sections[0]
    block = next(
        block
        for block in identity.blocks
        if isinstance(block, FormFieldBlock) and block.casilla_id == "decl.prorrata-especial"
    )
    assert [choice.value for choice in block.choices] == ["0", "1", "2", "3"]
    assert [lookup_translation(choice.heading_key, locale="es") for choice in block.choices] == [
        "Sin marcar",
        "Opción por la prorrata especial",
        "Revocación de la opción",
        "Ni opción ni revocación",
    ]
    owner = next(c for c in revision.casillas if c.id == block.casilla_id)
    broken = revision.model_copy(
        update={
            "casillas": tuple(
                c.model_copy(update={"constraints": None}) if c == owner else c for c in revision.casillas
            )
        }
    )
    assert form_layout_failures(broken)


def test_322_activity_descriptions_are_independent_paper_values_beside_the_codes() -> None:
    revision = _revision()
    grid = _grids()["actividades"]
    assert [column.key for column in grid.columns] == ["descripcion", "codigo", "iae"]
    for row, instance in zip(grid.rows, ["principal", *(f"otras-{i}" for i in range(1, 6))], strict=True):
        assert [cell.casilla_id for cell in row.cells] == [
            f"actividad.{instance}.descripcion",
            f"actividad.{instance}.codigo",
            f"actividad.{instance}.epigrafe-iae",
        ]
        description = next(c for c in revision.casillas if c.id == row.cells[0].casilla_id)
        assert description.input_kind == "informational"
        assert description.formula is None and description.binding is None
        assert not description.export_refs
        assert not description.required
        for locale in ("es", "en", "ca", "hu"):
            assert description.get_label(locale)
