"""A design cell whose own text divides it becomes one field per declared part.

Modelo 347 prints one four-byte cell at offset 77 and divides it in its text:
"77-78 CODIGO PROVINCIA" (numerico) and "79-80 CODIGO PAIS" (alfabetico). A
part is held to that cell: its statement must be the cell's verbatim text, its
range must be printed by the design, and the parts must tile the cell exactly.
"""

from __future__ import annotations

import pytest

from cadrumo.domain.calculations.registry.errors import RegistryValidationError

from ..compiler.authority import compiled_bundled_authority
from ..pipeline.semantic_map_validation import validate_declared_parts
from ..pipeline.joined_record_design import JoinedRecordDesignField, design_view
from ..pipeline.render_check import revision_render_inputs
from ..pipeline.semantic_map import SemanticMapEntry

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


@pytest.fixture(scope="module")
def m347_split_cell() -> tuple[tuple[JoinedRecordDesignField, ...], tuple[SemanticMapEntry, ...]]:
    inputs = revision_render_inputs(compiled_bundled_authority(), modelo="347", revision="2025-y-siguientes")
    parted = tuple(field for field in inputs.joined.fields if field.semantic_entry.part is not None)
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
