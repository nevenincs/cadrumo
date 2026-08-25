"""A field row keeps its position when AEAT wraps its description to the next line.

Modelo 202 writes ``15 80 1 Num`` and puts "Datos adicionales (3) - Cooperativa
fiscalmente protegida ..." on the line below. The row pattern requires a
description on the same line, so the row was not seen at all -- and the position
it declared, byte 80, was then reported as a hole. The corpus was fine; the
reader was reading one line at a time.

WHY A PRE-PASS RATHER THAN A LOOSER PATTERN, which is the substance here. The
first attempt let the row match with no description and relied on the
continuation handler to fill it in afterwards. That handler only fills the field
still under construction, so anything intervening leaves the field empty and a
later validator refuses the entire design: three modelo 200 editions went from
partly-read to hard ERROR that way. Joining the lines first means every row
still reaches the parser complete and no downstream invariant moves.

The line being absorbed must not itself carry meaning -- not a row, not a page
heading, not a record heading -- because swallowing one would lose a field or a
record boundary, which is a worse failure than the hole being repaired.
"""

from __future__ import annotations

import pytest

from cadrumo.domain.calculations.registry.record_design import extract_record_design
from ..record_design import _join_wrapped_row_descriptions
from .test_every_bundled_design_is_read_or_reported import _bundled_designs

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_a_wrapped_description_is_reattached_to_its_row() -> None:
    joined = _join_wrapped_row_descriptions(
        ("15 80 1 Num", "Datos adicionales (3) - Cooperativa fiscalmente protegida"),
    )

    assert joined == ("15 80 1 Num Datos adicionales (3) - Cooperativa fiscalmente protegida",)


def test_a_following_row_is_never_absorbed() -> None:
    """Absorbing the next row would lose a field outright."""
    joined = _join_wrapped_row_descriptions(("15 80 1 Num", "16 81 5 An Tipo de gravamen"))

    assert joined == ("15 80 1 Num", "16 81 5 An Tipo de gravamen")


def test_a_following_record_heading_is_never_absorbed() -> None:
    """Absorbing a heading would lose a record boundary."""
    joined = _join_wrapped_row_descriptions(
        ("15 80 1 Num", "Pág. 2 DISEÑO DE REGISTRO"),
    )

    assert joined == ("15 80 1 Num", "Pág. 2 DISEÑO DE REGISTRO")


def test_a_row_that_already_carries_its_description_is_untouched() -> None:
    lines = ("16 81 5 An Tipo de gravamen del Impuesto sobre Sociedades", "otra prosa")

    assert _join_wrapped_row_descriptions(lines) == lines


def test_a_bare_row_with_nothing_usable_after_it_is_left_alone() -> None:
    assert _join_wrapped_row_descriptions(("15 80 1 Num", "   ")) == ("15 80 1 Num", "   ")


@pytest.mark.parametrize(
    "prefix",
    ["08-202-orden-hap-2055-2012", "12-202-orden-hap-636-2013", "09-202-orden-hap-2214-2013"],
)
def test_the_bundled_modelo_202_designs_carry_no_position_holes(prefix: str) -> None:
    """The real corpus case: each of these reported a dropped byte at 80 or 81."""
    matches = [path for path in _bundled_designs() if path.name.startswith(prefix)]
    assert matches, f"the bundled design {prefix!r} is no longer in the corpus"

    extraction = extract_record_design(matches[0])
    holes = [sheet for sheet in extraction.skipped if "not read at all" in sheet.reason]

    assert not holes, [sheet.reason for sheet in holes]
