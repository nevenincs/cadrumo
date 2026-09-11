"""A field row keeps its position even when the design letters it first.

Modelo 604's English ATF design writes two rows of its correction block as
``A. 325 Alphabetic CORRECTION.`` and ``A. 350-367 Numeric CORRECTED TAX``,
lettering them as items of a group, while every other row in the same record
opens with the position. The row parser required the position first, so both
rows were dropped -- and the one-byte hole left at 325 was reported as a dropped
row, which is exactly what it was, though the cause was the reader rather than
the corpus.

WHAT IS NOT RELAXED. The marker is admitted; the guard that decides is not. A
line still has to name a naturaleza AEAT uses in the token after its position,
which is what keeps AEAT's own prose out -- descriptions routinely open with the
field's own range, and 41 bundled designs carry such lines. Measured across
every bundled PDF before the change, allowing the marker admits two lines in one
design and nothing else.
"""

from __future__ import annotations

import pytest

from ..record_design import extract_record_design
from ..record_design_pdf_rows import parse_pdf_row
from .test_every_bundled_design_is_read_or_reported import _bundled_designs

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_a_lettered_row_keeps_its_single_position() -> None:
    row = parse_pdf_row("A. 325 Alphabetic CORRECTION.", 1)

    assert row is not None
    assert (row.offset, row.length) == (325, 1)


def test_a_lettered_row_keeps_its_position_range() -> None:
    row = parse_pdf_row("A. 350-367 Numeric CORRECTED TAX", 1)

    assert row is not None
    assert (row.offset, row.length) == (350, 18)


def test_a_lettered_prose_line_is_still_refused() -> None:
    """The naturaleza guard, not the marker, is what admits a row."""
    assert parse_pdf_row("A. 15 personas que conviven con el declarante", 1) is None


def test_an_unlettered_prose_line_is_still_refused() -> None:
    assert parse_pdf_row("68-107 APELLIDOS Y NOMBRE: Se consignara el primer", 1) is None


def test_the_bundled_modelo_604_design_reads_both_records_whole() -> None:
    """The real corpus case: before this, its transactions record held a hole at 325."""
    matches = [path for path in _bundled_designs() if path.name.startswith("02-604-diseno-de-registro-atf")]
    assert matches, "the bundled modelo 604 ATF design is no longer in the corpus"

    extraction = extract_record_design(matches[0])

    assert not extraction.skipped, [sheet.name for sheet in extraction.skipped]
    assert extraction.is_complete
