"""A design cell whose own text divides it becomes one field per declared part.

Modelo 347 prints one four-byte cell at offset 77 and divides it in its text:
"77-78 CODIGO PROVINCIA" (numerico) and "79-80 CODIGO PAIS" (alfabetico). A
part is held to that cell: its statement must be the cell's verbatim text, its
range must be printed by the design, and the parts must tile the cell exactly.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.static_inspection import RegistryRevisionInspection

from ..compiler.loader import load_modelo_directory, load_shared_catalogues
from ..pipeline.joined_record_design import JoinedRecordDesignField, design_view, join_record_design_semantics
from ..pipeline.record_design_intermediate import load_record_design_intermediate
from ..pipeline.semantic_map import SemanticMapEntry, load_semantic_map
from ..pipeline.semantic_map_validation import validate_declared_parts

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


@pytest.fixture(scope="module")
def m347_split_cell() -> tuple[tuple[JoinedRecordDesignField, ...], tuple[SemanticMapEntry, ...]]:
    root = Path("src/cadrumo/_data")
    catalogues = load_shared_catalogues(root / "registry/aeat")
    definition = load_modelo_directory(root / "registry/aeat/modelos/347")
    semantic = load_semantic_map(Path("dev/registry/mappings/modelo_347/2025"))
    intermediate = load_record_design_intermediate(
        root,
        dict(catalogues.sources),
        source_ref=semantic.source_ref,
        filing_year=2025,
        design_epoch="2025",
    )
    joined = join_record_design_semantics(
        semantic,
        intermediate,
        RegistryRevisionInspection.from_revision(
            modelo=definition,
            revision=definition.revisions["2025-y-siguientes"],
            source_root=root,
            sources=catalogues.sources,
            legal_ref_ids=frozenset(catalogues.legal),
        ),
    )
    parted = tuple(field for field in joined.fields if field.semantic_entry.part is not None)
    return parted, tuple(field.semantic_entry for field in parted)


def test_the_provincia_pais_cell_joins_as_two_adjacent_parts(m347_split_cell) -> None:
    parted, entries = m347_split_cell

    assert [str(entry.export_field_id) for entry in entries] == [
        "m347-2025.declarado.f009a",
        "m347-2025.declarado.f009b",
    ]
    assert {(field.parser_field.offset, field.parser_field.length) for field in parted} == {(77, 4)}
    views = [design_view(field) for field in parted]
    assert [(view.offset, view.length, view.aeat_type) for view in views] == [
        (77, 2, "Numérico"),
        (79, 2, "Alfabético"),
    ]
    assert views[1].content is not None
    assert views[1].content.startswith("79-80")
    validate_declared_parts(entries, (parted[0].parser_field,))


def _with_part(entry: SemanticMapEntry, **update: object) -> SemanticMapEntry:
    assert entry.part is not None
    return entry.model_copy(update={"part": entry.part.model_copy(update=update)})


def test_a_statement_the_cell_does_not_print_is_refused(m347_split_cell) -> None:
    parted, (provincia, pais) = m347_split_cell

    with pytest.raises(RegistryValidationError, match="statement is not the text of its cell"):
        validate_declared_parts(
            (provincia, _with_part(pais, statement="79-80 CODIGO PAIS Campo numerico de 2 posiciones.")),
            (parted[0].parser_field,),
        )


def test_a_range_the_design_does_not_print_is_refused(m347_split_cell) -> None:
    parted, (provincia, pais) = m347_split_cell

    with pytest.raises(RegistryValidationError, match="is not printed by its cell"):
        validate_declared_parts(
            (_with_part(provincia, length=3), _with_part(pais, offset=80, length=1)),
            (parted[0].parser_field,),
        )


def test_parts_that_leave_a_byte_unaccounted_are_refused(m347_split_cell) -> None:
    parted, (provincia, _pais) = m347_split_cell

    with pytest.raises(RegistryValidationError, match="not tiled exactly"):
        validate_declared_parts((provincia,), (parted[0].parser_field,))


def test_overlapping_parts_are_refused(m347_split_cell) -> None:
    parted, (provincia, pais) = m347_split_cell

    with pytest.raises(RegistryValidationError, match="unaccounted or claimed twice"):
        validate_declared_parts((provincia, _with_part(pais, offset=78, length=3)), (parted[0].parser_field,))


@pytest.fixture(scope="module")
def m349_rectification_parts():
    root = Path("src/cadrumo/_data")
    intermediate = load_record_design_intermediate(
        root,
        load_shared_catalogues(root / "registry/aeat").sources,
        source_ref="aeat-dr-349-2020-current",
        filing_year=2024,
        design_epoch="2020",
    )
    sheet = next(
        sheet for sheet in intermediate.sheets if sheet.record_identity == "Tipo 2 - Registro De Retificaciones"
    )
    parent, revised, previous = (
        next(field for field in sheet.fields if field.offset == offset) for offset in (147, 153, 166)
    )
    assert (parent.length, revised.length, previous.length) == (32, 13, 13)
    assert parent.content is not None
    anchor = {key: getattr(parent, key) for key in ("sheet", "source_row", "ordinal", "record_identity")}
    entries = tuple(
        SemanticMapEntry.model_validate_json(
            json.dumps(
                {
                    "export_field_id": f"m349-rectification-{name}",
                    "kind": "filler",
                    "anchor": anchor,
                    "legal_refs": ["orden-hac-174-2020:art-1"],
                    "source_refs": ["aeat-dr-349-2020-current"],
                    "part": {
                        "offset": offset,
                        "length": length,
                        "aeat_type": aeat_type,
                        "statement": statement,
                    },
                }
            )
        )
        for name, offset, length, aeat_type, statement in (
            ("year", 147, 4, "Numérico", "147-150 Ejercicio Numérico de 4 posiciones"),
            ("period", 151, 2, "Alfanumérico", "151-152 Periodo Alfanumérico de 2 posiciones"),
        )
    )
    return (parent, revised, previous), entries


def test_rectification_parent_parts_and_separately_printed_bases_tile_exactly(m349_rectification_parts) -> None:
    fields, entries = m349_rectification_parts
    validate_declared_parts(entries, fields)


def test_rectification_parent_part_cannot_hide_missing_or_overlapping_base(m349_rectification_parts) -> None:
    (parent, revised, previous), entries = m349_rectification_parts
    with pytest.raises(RegistryValidationError, match="not tiled exactly"):
        validate_declared_parts(entries, (parent, revised))
    overlapping = previous.model_copy(update={"offset": 165})
    with pytest.raises(RegistryValidationError, match="unaccounted or claimed twice"):
        validate_declared_parts(entries, (parent, revised, overlapping))


@pytest.fixture(scope="module")
def m193_single_position_parts():
    root = Path("src/cadrumo/_data")
    source_ref = "aeat-dr-193-2025"
    intermediate = load_record_design_intermediate(
        root,
        load_shared_catalogues(root / "registry/aeat").sources,
        source_ref=source_ref,
        filing_year=2025,
        design_epoch="2025",
    )
    field = next(
        field for sheet in intermediate.sheets for field in sheet.fields if field.offset == 121 and field.length == 2
    )
    assert field.content is not None and "121 DECLARACIÓN COMPLEMENTARIA" in field.content
    assert "122 DECLARACIÓN SUSTITUTIVA" in field.content
    anchor = {key: getattr(field, key) for key in ("sheet", "source_row", "ordinal", "record_identity")}
    entries = tuple(
        SemanticMapEntry.model_validate_json(
            json.dumps(
                {
                    "export_field_id": f"m193-part-{offset}",
                    "kind": "filler",
                    "anchor": anchor,
                    "legal_refs": ["orden-eha-3377-2011:art-1"],
                    "source_refs": [source_ref],
                    "part": {"offset": offset, "length": 1, "aeat_type": "Alfabético", "statement": field.content},
                }
            )
        )
        for offset in (121, 122)
    )
    return field, entries


def test_official_single_position_parts_tile_their_real_source_cell(m193_single_position_parts) -> None:
    field, entries = m193_single_position_parts
    validate_declared_parts(entries, (field,))


@pytest.mark.parametrize("first_position", ["1121", "1210", "121-122"])
def test_a_partial_number_or_range_endpoint_cannot_attest_a_single_position(
    m193_single_position_parts, first_position: str
) -> None:
    field, entries = m193_single_position_parts
    changed = field.model_copy(
        update={"content": field.content.replace("121 DECLARACIÓN", f"{first_position} DECLARACIÓN")}
    )
    altered = tuple(_with_part(entry, statement=changed.content) for entry in entries)
    with pytest.raises(RegistryValidationError, match="is not printed by its cell"):
        validate_declared_parts(altered, (changed,))
