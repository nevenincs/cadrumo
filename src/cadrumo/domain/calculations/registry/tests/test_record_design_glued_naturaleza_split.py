"""A naturaleza glued to the content-column marker no longer costs its record.

Modelo 200's 2010 and 2011 PDF designs lose a row of their ``Pág. 22`` records
because the space between the naturaleza and the content column vanished::

    169 1690 7 Num C  Agrup.interés económico y UTES - Modelo de info...
    170 1697 9 AnC    A i t   i UTES M d l d i f i  R l i  d i 18 NIF
    171 1706 1 Num C  Agrup.interés económico y UTES - Modelo de info...

Nothing is missing from that middle line: ordinal 170 at position 1697, nine
bytes, naturaleza ``An``, content column ``A``. Only the separating space is
gone, and without it the row does not parse, its nine positions read as a hole,
and a record read with a hole is skipped whole.

WHY THIS IS ITS OWN REPAIR. The module already collapses this gluing where the
COORDINATES are doubled as well -- ``137 1777 15 1777 15 AnC B ...`` -- but that
rule needs the doubling to key on. Here the coordinates are printed once and
correctly, so it never matched.

THE DESCRIPTION IS LEFT DAMAGED ON PURPOSE. AEAT's own PDF drops characters from
that cell, and the extracted text reads ``A i t   i UTES M d l d i f i``. This
repair recovers the row's POSITION, which is what stops the record being
skipped; it carries the description through exactly as extracted. Reconstructing
prose would be a worse failure than reporting it damaged.
"""

from __future__ import annotations

import pytest

from .....core.resources import bundled_path
from cadrumo.domain.calculations.registry.record_design import extract_record_design
from ..record_design import _split_glued_naturaleza_rows

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_DESIGNS = (
    "02-200-ejercicio-2010-472-kb-pdf.pdf",
    "03-200-ejercicio-2011-522-kb-pdf.pdf",
)


def _design(name: str):
    return extract_record_design(
        bundled_path("corpus", "aeat_official", "disenos_registro", "modelo_200", "files", name)
    )


@pytest.mark.parametrize("name", _DESIGNS)
def test_the_record_is_no_longer_skipped(name: str) -> None:
    """``Pág. 22`` was skipped on both designs for this one row."""
    extraction = _design(name)

    skipped = {sheet.name.strip()[-2:] for sheet in extraction.skipped}

    assert "22" not in skipped, [(s.name, s.reason) for s in extraction.skipped]


@pytest.mark.parametrize("name", _DESIGNS)
def test_the_recovered_record_tiles_without_a_hole(name: str) -> None:
    extraction = _design(name)
    sheet = next(s for s in extraction.sheets if s.name.strip().endswith(" 22"))

    occupied: set[int] = set()
    for field in sheet.fields:
        occupied |= set(range(field.offset, field.offset + field.length))
    unwritten = sorted(set(range(1, (sheet.total_positions or 0) + 1)) - occupied)

    assert not unwritten, unwritten[:8]


def test_the_glued_row_is_separated_when_it_continues_the_previous_row() -> None:
    lines = (
        "169 1690 7 Num C Agrup. interes economico y UTES.",
        "170 1697 9 AnC A i t   i UTES M d l d i f i  R l i  d i 18 NIF",
        "171 1706 1 Num C Agrup. interes economico y UTES.",
    )

    split = _split_glued_naturaleza_rows(lines)

    assert split[1].startswith("170 1697 9 An C ")
    assert split[0] == lines[0]
    assert split[2] == lines[2]


def test_a_glued_row_that_does_not_continue_is_left_alone() -> None:
    """The over-determination, broken on the position half.

    The coordinates say 1699 where the previous row ends at 1697, so the
    ordinal follows but the position does not resume. One disagreeing fact is
    enough to refuse.
    """
    lines = (
        "169 1690 7 Num C Agrup. interes economico y UTES.",
        "170 1699 9 AnC A mangled description",
    )

    assert _split_glued_naturaleza_rows(lines) == lines


def test_the_damaged_description_is_carried_through_unchanged() -> None:
    """The repair recovers position, never prose."""
    damaged = "A i t   i UTES M d l d i f i  R l i  d i 18 NIF"
    lines = (
        "169 1690 7 Num C Agrup. interes economico y UTES.",
        f"170 1697 9 AnC {damaged}",
    )

    split = _split_glued_naturaleza_rows(lines)

    assert split[1] == f"170 1697 9 An C {damaged}"
