"""The printed-box parser must read every box shape the record designs print.

Modelo 200 numbers five digits wide; modelo 036 prints lettered, bis and dotted
boxes. The parser reads exactly those shapes and refuses anything wider.

It must also locate a box AEAT prints across several campo lines -- a date filed
under one number and printed as dia, mes and ano -- while still refusing a number
printed for two unrelated campos.
"""

import pytest

from cadrumo.domain.calculations.registry.schema_surfaces import CasillaDefinition
from dev.registry.analysis.casilla_lineage_seed import (
    _DESIGN_BOX,
    DesignInventory,
    _defined_box,
    parse_design_inventory,
    printed_box,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _boxed_casilla(number: str) -> CasillaDefinition:
    """A row numbered the way modelo 036 numbers its boxes."""
    slug = number.lower().replace(".", "-")
    return CasillaDefinition.model_validate(
        {
            "id": slug,
            "number": number,
            "localization_keys": (f"modelo.036.casilla.{slug}.label",),
            "section": ("identificacion",),
            "semantic_role": "base_imponible",
            "legal_refs": ("ley-58-2003:art-29",),
            "source_refs": ("aeat-dr-036-2025-v1",),
        }
    )


def test_reads_a_five_digit_printed_box() -> None:
    assert _DESIGN_BOX.findall("Base imponible [00101] del ejercicio") == ["00101"]


def test_still_reads_shorter_printed_boxes() -> None:
    assert _DESIGN_BOX.findall("[1] [07] [123] [4567]") == ["1", "07", "123", "4567"]


def test_reads_every_box_on_a_line_of_five_digit_numbering() -> None:
    line = "[00101] + [00102] - [03442] = [00955]"
    assert _DESIGN_BOX.findall(line) == ["00101", "00102", "03442", "00955"]


def test_refuses_a_run_longer_than_the_widest_numbering() -> None:
    assert _DESIGN_BOX.findall("[123456]") == []


def test_reads_the_lettered_boxes_modelo_036_prints() -> None:
    line = "Casilla [A4] y casilla [A72] | [B38] | [B3B] | [C71] | [C70] | [B9] | [B8] | [B10]"
    assert _DESIGN_BOX.findall(line) == ["A4", "A72", "B38", "B3B", "C71", "C70", "B9", "B8", "B10"]


def test_reads_the_suffixed_boxes_modelo_036_prints() -> None:
    line = "[412bis] | [433bis] | [454bis] | [4774bis] | [716.a] | [717.b]"
    assert _DESIGN_BOX.findall(line) == ["412bis", "433bis", "454bis", "4774bis", "716.a", "717.b"]


@pytest.mark.parametrize("number", ["A4", "A72", "B3B", "412bis", "4774bis", "716.a"])
def test_a_non_numeric_box_matches_the_row_numbered_with_it(number: str) -> None:
    printed = _defined_box(f"Denominacion social [{number}]")
    assert printed == number
    assert printed == printed_box(_boxed_casilla(number))


@pytest.mark.parametrize("cell", ["[AB12]", "[A123]", "[a4]", "[123456]", "[412ter]", "[716.ab]"])
def test_refuses_a_shape_the_record_designs_do_not_print(cell: str) -> None:
    assert _DESIGN_BOX.findall(cell) == []


_COMPONENT_DESIGN = """# Pag. 3
Nº | Posic. | Lon | Tipo | Descripción
31 | 262 | 1 | An | La actividad se desarrolla en local determinado. Alta  [424]
32 | 263 | 2 | Num | La actividad se desarrolla en local determinado. Fecha. Dia.  [425]
33 | 265 | 2 | Num | La actividad se desarrolla en local determinado. Fecha. Mes.  [425]
34 | 267 | 4 | Num | La actividad se desarrolla en local determinado. Fecha. Año.  [425]
"""


def _inventory(text: str) -> DesignInventory:
    """The inventory of one design extract, parsed the way the oracle parses it."""
    return parse_design_inventory(text, relative_path="design.md", sha256="0" * 64)


def test_one_field_printed_as_three_components_locates_its_box() -> None:
    inventory = _inventory(_COMPONENT_DESIGN)
    assert inventory.lines[425] == (4, 5, 6)
    assert inventory.defining_lines(425) == (4, 5, 6)
    # The citation anchors on the first component, and the components tile @263+8.
    assert inventory.defining_line(425) == 4
    span = inventory.component_span(425)
    assert span is not None
    assert (span.record, span.offset, span.length) == ("Pag. 3", 263, 8)


def test_a_component_outside_the_tiled_span_is_refused() -> None:
    strayed = _COMPONENT_DESIGN.replace("34 | 267 | 4", "34 | 300 | 4")
    inventory = _inventory(strayed)
    assert inventory.defining_lines(425) is None
    assert inventory.defining_line(425) is None
    assert inventory.component_span(425) is None
    reason = inventory.unlocalised_reason(425)
    assert "@263+2" in reason
    assert "@300+4" in reason
    assert "do not tile one contiguous field" in reason


def test_two_lines_in_two_records_are_refused() -> None:
    text = (
        "# Pag. 3\n"
        "32 | 263 | 2 | Num | Fecha. Dia.  [425]\n"
        "# Pag. 4\n"
        "11 | 265 | 2 | Num | Otra cosa. Fecha. Mes.  [425]\n"
    )
    inventory = _inventory(text)
    assert inventory.defining_lines(425) is None
    assert inventory.defining_line(425) is None
    reason = inventory.unlocalised_reason(425)
    assert "different records" in reason
    assert "'Pag. 3'" in reason
    assert "'Pag. 4'" in reason


def test_a_box_printed_on_one_line_still_locates() -> None:
    inventory = _inventory(_COMPONENT_DESIGN)
    assert inventory.defining_lines(424) == (3,)
    assert inventory.defining_line(424) == 3
    # A single line is not a tiled field, so it reports no component span.
    assert inventory.component_span(424) is None
