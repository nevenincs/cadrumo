"""The generator over the real registry: totality, idempotence, official grounding and the gates.

Expected structure is checked against the official record design the revision
cites, read independently of the generator, rather than against values copied
from its own output.
"""

from __future__ import annotations

from collections.abc import Mapping
from functools import cache

import pytest

from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.schema import ModeloDefinition
from cadrumo.domain.calculations.registry.schema_form_layouts import (
    FormCellKind,
    FormContextFieldBlock,
    FormFieldBlock,
    FormGridBlock,
    FormLayoutDefinition,
    FormLayoutReviewState,
    FormLayoutSeedSource,
    FormPlacementKind,
)
from cadrumo.domain.calculations.registry.schema_references import SourceReference

from ...compiler.form_layout_integrity import form_layout_failures
from ...compiler.loader import load_registry_tree
from ...record_design_labels import DATA_ROOT, read_record_design, record_design_sidecars
from ..cli import REGISTRY_ROOT, synchronise_form_layouts
from ..column_vocabulary import SHARED_COLUMN_KEYS, shared_column_key
from ..coverage import coverage_rows, coverage_totals
from ..generator import generate_modelo_layouts
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


def test_126_periodification_preserves_the_official_empty_corner() -> None:
    layout = _layout("126", "2019-y-siguientes")
    assert layout.seed_source is FormLayoutSeedSource.AUTHORED
    sections = layout.pages[0].sections
    assert [section.id for section in sections] == [
        "identificacion",
        "devengo",
        "liquidacion",
        "ingreso",
        "complementaria",
    ]
    first, periodification, *totals = sections[2].blocks
    assert isinstance(first, FormGridBlock)
    assert [[str(cell.casilla_id) for cell in row.cells] for row in first.rows] == [["01", "02"]]
    assert isinstance(periodification, FormGridBlock)
    assert [[cell.casilla_id for cell in row.cells] for row in periodification.rows] == [
        ["03", "04", "05", "06"],
        ["07", "08", "09", None],
    ]
    assert periodification.rows[1].cells[3].kind is FormCellKind.BLANK
    assert [str(block.casilla_id) for block in totals if isinstance(block, FormFieldBlock)] == ["10", "11", "12"]
    context = [block for section in sections for block in section.blocks if isinstance(block, FormContextFieldBlock)]
    assert len(context) == 8
    assert all(block.export_record_id == "modelo-126-page-01" for block in context)


def test_128_official_parallel_blocks_keep_the_empty_withholding_position() -> None:
    layout = _layout("128", "2019-y-siguientes")
    assert layout.seed_source is FormLayoutSeedSource.AUTHORED
    sections = layout.pages[0].sections
    grid, *totals = sections[2].blocks
    assert isinstance(grid, FormGridBlock)
    assert [[cell.casilla_id for cell in row.cells] for row in grid.rows] == [["01", "04"], ["02", "05"], ["03", None]]
    assert grid.rows[2].cells[1].kind is FormCellKind.BLANK
    assert [str(block.casilla_id) for block in totals if isinstance(block, FormFieldBlock)] == ["06", "07"]
    context = [block for section in sections for block in section.blocks if isinstance(block, FormContextFieldBlock)]
    assert len(context) == 8
    assert all(block.export_record_id == "modelo-128-page-01" for block in context)


def test_117_uses_the_revised_eleven_box_annex_not_the_2007_eight_box_form() -> None:
    layout = _layout("117", "2019-y-siguientes")
    assert layout.seed_source is FormLayoutSeedSource.AUTHORED
    assert "boe-2018-17997-modelo-117-form-pdf" in {source.source_ref for source in layout.design_sources}
    sections = layout.pages[0].sections
    assert [section.id for section in sections] == [
        "identificacion",
        "devengo",
        "liquidacion",
        "pago-cuenta",
        "total",
        "ingreso",
        "complementaria",
    ]
    grid = sections[2].blocks[0]
    assert isinstance(grid, FormGridBlock)
    assert [[cell.casilla_id for cell in row.cells] for row in grid.rows] == [["01", "04"], ["02", "05"], ["03", "06"]]
    assert [block.casilla_id for block in sections[3].blocks if isinstance(block, FormFieldBlock)] == ["07", "08"]
    assert [block.casilla_id for block in sections[4].blocks if isinstance(block, FormFieldBlock)] == ["09", "10", "11"]


def test_216_historical_form_keeps_the_official_columns_without_promoting_capability() -> None:
    revision = _modelos()["216"].revisions["2020-2023"]
    layout = revision.form_layouts[0]
    assert layout.seed_source is FormLayoutSeedSource.AUTHORED
    assert "boe-2008-18497-modelo-216-form-pdf" in {s.source_ref for s in layout.design_sources}
    # Annex I, BOE page 45593: 01/04, 02/05, 03/empty, then 06 and 07.
    sections = layout.pages[0].sections
    assert [s.id for s in sections] == ["identificacion", "devengo", "liquidacion", "ingreso", "complementaria"]
    grid, *totals = sections[2].blocks
    assert isinstance(grid, FormGridBlock)
    assert [[cell.casilla_id for cell in row.cells] for row in grid.rows] == [["1", "4"], ["2", "5"], ["3", None]]
    assert grid.rows[2].cells[1].kind is FormCellKind.BLANK
    assert [block.casilla_id for block in totals if isinstance(block, FormFieldBlock)] == ["6", "7"]
    assert {str(p.casilla_id): str(p.box_number) for p in layout.placements} == {str(n): f"{n:02}" for n in range(1, 8)}
    assert revision.authority_grade is not None
    assert revision.authority_grade.value == "calculation"
    assert not revision.bindings
    assert len(revision.export_layouts) == 1
    context = [b for s in sections for b in s.blocks if isinstance(b, FormContextFieldBlock)]
    assert len(context) == 8
    assert {str(b.export_layout_id) for b in context} == {"generated-modelo-216-2020-2023-fichero"}
    assert {str(b.export_field_id) for b in context} == {
        "modelo-216-page-01-" + field
        for field in (
            "nif",
            "apellidos",
            "nombre",
            "devengo-ejercicio",
            "devengo-periodo",
            "iban",
            "complementaria",
            "complementaria-justificante",
        )
    }


def test_216_current_form_separates_withheld_and_nonwithheld_income_grids() -> None:
    layout = _layout("216", "2024-y-siguientes")
    assert layout.seed_source is FormLayoutSeedSource.AUTHORED
    sections = layout.pages[0].sections
    assert [s.id for s in sections] == [
        "devengo",
        "identificacion",
        "sometidas",
        "no-sometidas",
        "liquidacion",
        "ingreso",
        "complementaria",
    ]
    for section, expected in zip(
        sections[2:4],
        [
            [["05", "08", "11"], ["06", "09", "12"], ["07", "10", "13"]],
            [["14", "17"], ["15", "18"], ["16", "19"]],
        ],
        strict=True,
    ):
        grid = section.blocks[0]
        assert isinstance(grid, FormGridBlock)
        assert [[cell.casilla_id for cell in row.cells] for row in grid.rows] == expected
    assert [b.casilla_id for b in sections[4].blocks if isinstance(b, FormFieldBlock)] == ["20", "21"]
    assert {str(p.casilla_id) for p in _layout("216", "2020-2023").placements} == {str(i) for i in range(1, 8)}


def test_regeneration_reproduces_the_committed_fragments_byte_for_byte() -> None:
    changed, undeclared = synchronise_form_layouts(REGISTRY_ROOT, DATA_ROOT, check=True)
    assert changed == []
    assert undeclared == []


@pytest.mark.parametrize("stale", [False, True])
def test_authored_draft_is_preserved_without_promoting_review(stale: bool) -> None:
    modelo = _modelos()["130"]
    revision = modelo.revisions["2019-y-siguientes"]
    layout = revision.form_layouts[0]
    authored = layout.model_copy(
        update={
            "seed_source": FormLayoutSeedSource.AUTHORED,
            "source_state_digest": "0" * 64 if stale else layout.source_state_digest,
        }
    )
    revision = revision.model_copy(update={"form_layouts": (authored,)})
    modelo = modelo.model_copy(update={"revisions": {revision.id: revision}})

    if stale:
        with pytest.raises(RegistryValidationError, match="authored form layout is stale"):
            generate_modelo_layouts(modelo, sources=_catalogue_sources(), data_root=DATA_ROOT)
    else:
        assert generate_modelo_layouts(modelo, sources=_catalogue_sources(), data_root=DATA_ROOT) == {}
    assert authored.review.state is FormLayoutReviewState.GENERATED
    assert revision.form_layouts == (authored,)


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
    sections = _layout("130", "2019-y-siguientes").pages[0].sections
    assert [section.id for section in sections[:2]] == ["identificacion", "devengo"]
    assert [section.id for section in sections[5:]] == ["ingreso", "complementaria"]
    headings = [section.official_heading for section in sections[2:5]]
    assert [heading.split(". ")[1] if heading else None for heading in headings] == ["I", "II", "III"]
    assert all(heading and heading.startswith("Liquidación (3).") for heading in headings)


def test_authored_115_retains_five_printed_boxes_and_exact_context_targets() -> None:
    layout = _layout("115", "2019-y-siguientes")
    assert layout.seed_source is FormLayoutSeedSource.AUTHORED
    assert any(source.source_ref == "boe-2000-21430-modelo-115-form" for source in layout.design_sources)
    sections = layout.pages[0].sections
    assert [section.id for section in sections] == [
        "identificacion",
        "devengo",
        "liquidacion",
        "complementaria",
        "ingreso",
    ]
    assert [block.casilla_id for block in sections[2].blocks if isinstance(block, FormFieldBlock)] == [
        "01",
        "02",
        "03",
        "04",
        "05",
    ]
    context = [block for section in sections for block in section.blocks if isinstance(block, FormContextFieldBlock)]
    assert {str(block.export_field_id) for block in context} == {
        f"modelo-115-page-01-{suffix}"
        for suffix in (
            "nif",
            "apellidos",
            "nombre",
            "ejercicio",
            "periodo",
            "declaracion-complementaria",
            "justificante-anterior",
            "iban",
        )
    }


@pytest.mark.parametrize(
    ("revision", "rows", "period_boxes", "total_boxes"),
    (
        ("2019-2023", (("01", "02", "03"),), ("04", "05"), ("06", "07", "08")),
        (
            "2024-y-siguientes",
            (("01", "02", "03"), ("04", "05", "06"), ("07", "08", "09")),
            ("10", "11"),
            ("12", "13", "14"),
        ),
    ),
)
def test_123_printed_revision_grids_preserve_changed_box_meanings(
    revision: str, rows: tuple[tuple[str, ...], ...], period_boxes: tuple[str, ...], total_boxes: tuple[str, ...]
) -> None:
    layout = _layout("123", revision)
    assert layout.seed_source is FormLayoutSeedSource.AUTHORED
    sections = layout.pages[0].sections
    assert [section.id for section in sections] == [
        "identificacion",
        "devengo",
        "liquidacion",
        "ingreso",
        "complementaria",
    ]
    income, period, *totals = sections[2].blocks
    assert isinstance(income, FormGridBlock)
    assert tuple(tuple(cell.casilla_id for cell in row.cells) for row in income.rows) == rows
    assert isinstance(period, FormGridBlock)
    assert tuple(cell.casilla_id for cell in period.rows[0].cells) == period_boxes
    assert tuple(block.casilla_id for block in totals if isinstance(block, FormFieldBlock)) == total_boxes
    assert len(sections[0].blocks) == (2 if revision == "2024-y-siguientes" else 3)


def test_authored_131_activity_table_preserves_all_official_columns_and_bindings() -> None:
    layout = _layout("131", "2019-2023")
    assert layout.seed_source is FormLayoutSeedSource.AUTHORED
    assert layout.review.state is FormLayoutReviewState.GENERATED
    assert any(source.source_ref == "boe-2015-1656-modelos-130-131-form" for source in layout.design_sources)
    sections = layout.pages[0].sections[2:6]
    assert [section.id for section in layout.pages[0].sections[:2]] == ["identificacion", "devengo"]
    assert [section.id for section in layout.pages[0].sections[6:]] == ["ingreso", "complementaria-7"]
    assert [section.id for section in sections[:4]] == [
        "liquidacion-i",
        "liquidacion-ii",
        "liquidacion-iii",
        "liquidacion-iv",
    ]
    grid = sections[0].blocks[0]
    assert isinstance(grid, FormGridBlock)
    assert len(grid.columns) == 4
    assert len(grid.rows) == 5
    fields = ("epigrafe", "rendimiento-neto", "porcentaje", "resultado")
    for index, row in enumerate(grid.rows, 1):
        assert tuple(cell.binding_id for cell in row.cells) == tuple(
            f"modelo-131.page1.actividad-{index}-{field}" for field in fields
        )
    expected_sections = {
        f"{box:02}": section
        for section, boxes in (
            ("liquidacion-i", range(1, 3)),
            ("liquidacion-ii", range(3, 5)),
            ("liquidacion-iii", range(5, 7)),
            ("liquidacion-iv", range(7, 16)),
        )
        for box in boxes
    }
    assert {box: position[1] for box, position in layout.casilla_sections().items()} == expected_sections


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


def test_authored_111_preserves_the_nine_printed_three_column_rows() -> None:
    layout = _layout("111", "2019-y-siguientes")
    assert layout.seed_source is FormLayoutSeedSource.AUTHORED
    assert layout.review.state is FormLayoutReviewState.GENERATED
    assert any(source.source_ref == "boe-2011-4948-modelo-111-form" for source in layout.design_sources)
    sections = layout.pages[0].sections[2:8]
    assert len(sections) == 6
    assert [section.id for section in layout.pages[0].sections[:2]] == ["identificacion", "devengo"]
    assert [section.id for section in layout.pages[0].sections[8:]] == ["ingreso", "complementaria"]
    for section, numeral in zip(sections[:5], ("I.", "II.", "III.", "IV.", "V."), strict=True):
        assert section.official_heading and section.official_heading.startswith(numeral)
    rows = []
    for section in sections[:5]:
        for block in section.blocks:
            assert isinstance(block, FormGridBlock)
            assert len(block.columns) == 3
            rows.extend(tuple(str(cell.casilla_id) for cell in row.cells) for row in block.rows)
    assert rows == [tuple(f"{start + offset:02}" for offset in range(3)) for start in range(1, 28, 3)]
    assert len(layout.placements) == 30


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
