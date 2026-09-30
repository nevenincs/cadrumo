"""The generator over the real registry: totality, idempotence, official grounding and the gates.

Expected structure is checked against the official record design the revision
cites, read independently of the generator, rather than against values copied
from its own output.
"""

from __future__ import annotations

from collections.abc import Mapping
from functools import cache

import pytest

from cadrumo.domain.calculations.registry.form_layout_integrity import form_layout_failures
from cadrumo.domain.calculations.registry.schema import ModeloDefinition
from cadrumo.domain.calculations.registry.schema_form_layouts import (
    FormCellKind,
    FormGridBlock,
    FormLayoutDefinition,
    FormLayoutReviewState,
    FormPlacementKind,
)
from cadrumo.domain.calculations.registry.schema_references import SourceReference

from ...compiler.loader import load_registry_tree
from ...record_design_labels import DATA_ROOT, read_record_design, record_design_sidecars
from ..cli import REGISTRY_ROOT, synchronise_form_layouts
from ..column_vocabulary import SHARED_COLUMN_KEYS, shared_column_key
from ..coverage import coverage_rows, coverage_totals
from ..official_text import clean_official_text, description_box, description_path, node_slug
from ..stability import PlacementMove, moved_placements, read_acknowledgements, unacknowledged_moves

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


@cache
def _modelos() -> Mapping[str, ModeloDefinition]:
    modelos, _catalogues = load_registry_tree(REGISTRY_ROOT)
    return {str(modelo.id): modelo for modelo in modelos}


def _layout(modelo: str, revision: str) -> FormLayoutDefinition:
    return _modelos()[modelo].revisions[revision].form_layouts[0]


def test_every_revision_declares_a_layout_that_places_every_casilla_once() -> None:
    for modelo in _modelos().values():
        for revision_id, revision in modelo.revisions.items():
            assert len(revision.form_layouts) == 1, (modelo.id, revision_id)
            layout = revision.form_layouts[0]
            assert layout.review.state is FormLayoutReviewState.GENERATED
            assert form_layout_failures(revision) == (), (modelo.id, revision_id)
            assert {item.casilla_id for item in layout.placements} == {item.id for item in revision.casillas}


def test_regeneration_reproduces_the_committed_fragments_byte_for_byte() -> None:
    changed, undeclared = synchronise_form_layouts(REGISTRY_ROOT, DATA_ROOT, check=True)
    assert changed == []
    assert undeclared == []


def test_303_tipo_boxes_are_design_constants_carrying_the_designs_literal() -> None:
    revision = _modelos()["303"].revisions["2025"]
    rows = read_record_design(record_design_sidecars(revision.source_refs, _catalogue_sources())[0][1])
    official = {
        description_box(row.label): row.label
        for (record, _offset), row in rows.items()
        if record == "DP30301" and "Tipo %" in row.label
    }
    cells = {
        cell.casilla_id: cell
        for page in _layout("303", "2025").pages
        for section in page.sections
        for block in section.blocks
        if isinstance(block, FormGridBlock)
        for grid_row in block.rows
        for cell in grid_row.cells
        if cell.casilla_id is not None
    }
    for box in ("02", "05", "08"):
        assert f"[{box}]" in official[box]
        assert cells[box].kind is FormCellKind.DESIGN_CONSTANT
        assert cells[box].literal is not None
    assert cells["01"].kind is FormCellKind.CASILLA


@cache
def _catalogue_sources() -> Mapping[str, SourceReference]:
    _modelos_tuple, catalogues = load_registry_tree(REGISTRY_ROOT)
    return catalogues.sources


def test_130_sections_are_the_designs_three_apartados_in_order() -> None:
    headings = [
        section.official_heading for page in _layout("130", "2019-y-siguientes").pages for section in page.sections
    ]
    assert [heading.split(". ")[1] if heading else None for heading in headings] == ["I", "II", "III"]
    assert all(heading and heading.startswith("Liquidación (3).") for heading in headings)


def test_111_withholding_rows_are_grids_over_the_shared_columns() -> None:
    grids = [
        block
        for page in _layout("111", "2019-y-siguientes").pages
        for section in page.sections
        for block in section.blocks
        if isinstance(block, FormGridBlock)
    ]
    assert grids
    first = grids[0]
    assert [column.key for column in first.columns] == [
        "numero_perceptores",
        "importe_percepciones",
        "importe_retenciones",
    ]
    assert all(column.heading_key == f"modelo.form.column.{column.key}" for column in first.columns)
    assert [cell.casilla_id for cell in first.rows[0].cells] == ["01", "02", "03"]


def test_coverage_accounts_for_every_casilla_of_every_revision() -> None:
    rows = coverage_rows(_modelos().values())
    totals = coverage_totals(rows)
    assert totals["revisions"] == sum(len(modelo.revisions) for modelo in _modelos().values())
    assert totals["declared"] + totals["undeclared"] == totals["revisions"]
    assert totals["on_form"] + totals["working_figure"] + totals["unplaced"] == totals["casillas"]
    for row in rows:
        assert row.on_form + row.working_figure + row.unplaced == row.casillas
        assert sum(row.unplaced_reasons.values()) == row.unplaced


def test_every_moved_placement_is_acknowledged_and_no_acknowledgement_is_stale() -> None:
    moves = moved_placements(_modelos().values())
    missing, stale = unacknowledged_moves(moves, read_acknowledgements())
    assert missing == ()
    assert stale == ()


def test_the_stability_gate_detects_an_unacknowledged_and_a_stale_move() -> None:
    real = moved_placements(_modelos().values())
    acknowledged = read_acknowledgements()
    extra = PlacementMove("303", "2025", "01", "dp30301/a", "dp30301/b")
    missing, stale = unacknowledged_moves((*real, extra), acknowledged)
    assert missing == (extra,)
    missing, stale = unacknowledged_moves(real, {**acknowledged, extra: "reviewed"})
    assert stale == (extra,)


def test_every_on_form_placement_has_a_position_and_every_other_has_none() -> None:
    layout = _layout("390", "2025")
    shown = layout.casilla_sections()
    for placement in layout.placements:
        assert (placement.casilla_id in shown) == (placement.kind is FormPlacementKind.ON_FORM)


@pytest.mark.parametrize(
    ("description", "section", "stem", "column", "box"),
    [
        (
            "Liquidación (3) - Regimen General - IVA Devengado - Régimen general - Base imponible [01]",
            ("Liquidación (3)", "Regimen General", "IVA Devengado"),
            "Régimen general",
            "Base imponible",
            "01",
        ),
        (
            "Rendim. del trabajo - Rendimientos dinerarios - Nº de perceptores",
            ("Rendim. del trabajo",),
            "Rendimientos dinerarios",
            "Nº de perceptores",
            None,
        ),
        (
            "Liquidación (3). I. Actividades econ. Estim. Directa - [07] Pago fraccionado previo ([04] - [05] - [06])",
            ("Liquidación (3). I. Actividades econ. Estim. Directa",),
            None,
            "Pago fraccionado previo",
            "07",
        ),
        (
            "Modificación bases y cuotas- Base imponible  [14]",
            ("Modificación bases y cuotas",),
            None,
            "Base imponible",
            "14",
        ),
    ],
)
def test_design_descriptions_split_into_section_row_and_column(
    description: str, section: tuple[str, ...], stem: str | None, column: str, box: str | None
) -> None:
    path = description_path(description)
    assert (path.section, path.stem, path.column) == (section, stem, column)
    assert description_box(description) == box


def test_a_description_naming_two_boxes_of_its_own_identifies_none() -> None:
    assert description_box("Total [46] y [47]") is None


def test_extraction_artefacts_are_repaired_without_rewording() -> None:
    assert clean_official_text("[0453] \x96[0454]\n  Total") == "[0453] –[0454] Total"
    assert clean_official_text("Base   imponible") == "Base imponible"


def test_node_slugs_are_bounded_and_distinct() -> None:
    long_a = "Importes de las entregas de bienes y prestaciones de servicios A"
    long_b = "Importes de las entregas de bienes y prestaciones de servicios B"
    assert node_slug("Pág. 2 bis") == "pag-2-bis"
    assert len(node_slug(long_a)) <= 48
    assert node_slug(long_a) != node_slug(long_b)


def test_the_shared_vocabulary_folds_the_designs_spellings() -> None:
    assert shared_column_key("Tipo %") == "tipo"
    assert shared_column_key("Nº de perceptores") == "numero_perceptores"
    assert shared_column_key("% de prorrata") == "porcentaje_prorrata"
    assert shared_column_key("Resultado") is None
    assert "base_imponible" in SHARED_COLUMN_KEYS
