"""Development-only: a página constant that is a composite, and the design that proves the split.

Most designs write the page directly: modelo 200's ``001``, modelo 763's ``02``.
Modelo 390's 2015 edition writes a five-digit composite -- ``01000`` through
``08000`` -- where the leading digits are the page and the trailing ``000`` is a
sub-counter.

THE SPLIT IS NOT ASSUMED, and this was refused once before it was read. The
design cross-checks itself: its second record is headed ``Pag. 1 DISENO DE
REGISTRO`` by AEAT's own running header, needing no help from the recovery at
all, and that SAME record declares ``Constante "01000"`` and closes
``</T39001000>``. Page 1 and token 01000 are one record stated two ways, which
fixes the reading. The other seven records run 02000 to 08000 and name pages 2
to 8, colliding with nothing.

An earlier tick recorded this as ungroundable, reasoning that decomposing
``01000`` to page 1 would collide with the header-derived ``Pag. 1`` and that
the collision showed the two schemes were different. The collision was real and
the inference backwards: they collide because they name the same record, which
is the corroboration rather than the objection.

A five-digit token that does NOT carry the sub-counter is left whole, because
nothing here says how to split it.
"""

from __future__ import annotations

import pytest

from ..compiler.record_design import extract_record_design
from .test_every_bundled_design_is_read_or_reported import _bundled_designs

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_the_bundled_modelo_390_design_names_its_eight_page_records() -> None:
    """The real corpus case: seven of these were anonymous before the split."""
    matches = [path for path in _bundled_designs() if path.name.startswith("08-390-ejercicio-2015")]
    assert matches, "the bundled modelo 390 2015 design is no longer in the corpus"

    extraction = extract_record_design(matches[0])
    named = {sheet.name for sheet in (*extraction.sheets, *extraction.skipped)}

    for page in range(1, 9):
        assert f"P\u00e1g. {page}" in named, sorted(named)
