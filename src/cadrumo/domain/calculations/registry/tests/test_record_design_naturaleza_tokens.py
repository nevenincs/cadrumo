"""Two ways a modelo 100 row hid its position behind its type column.

Both were read as dropped rows, which is what a scattered single-byte hole looks
like from the contiguity check -- 12, 192, 372, 581 in one record. Neither was
corpus damage; both were tokens the reader did not know.

``Tit`` IS A NATURALEZA. Modelo 100 uses it for the one-byte code naming which
titular an entry belongs to, and the rows say so: every occurrence ends its
description in "... - Titular" or "... - Contribuyente". Across the six bundled
editions that use it there are 454 such rows and every one declares length 1,
which is what a holder code is. Leaving it unrecognised dropped all 454.

``1A`` IS A LOST SPACE. The PDF text layer drops the gap between length and
type, so modelo 100's 2009 through 2011 editions write ``5 9 1A Indicador de
pagina complementaria`` for a row that is length 1, type A. The split stays
unambiguous because length is digits and type is a closed alternation, so ``1A``
can only be 1 + A.

Both populations were measured across every bundled PDF before being admitted:
454 rows in six designs for ``Tit``, three rows in three designs for ``1A``, and
in both cases every match is a genuine field row.
"""

from __future__ import annotations

import pytest

from .. import extract_record_design
from .._record_design import _parse_pdf_row
from .test_every_bundled_design_is_read_or_reported import _bundled_designs

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_a_titular_row_keeps_its_position() -> None:
    row = _parse_pdf_row("26 192 1 Tit C Bienes inmuebles no afectos. Inmueble 2. Contribuyente", 1)

    assert row is not None
    assert (row.offset, row.length, row.type_code) == (192, 1, "Tit")


def test_a_length_and_type_written_without_a_space_still_split() -> None:
    row = _parse_pdf_row('5 9 1A Indicador de pagina complementaria. Blanco o "C"', 1)

    assert row is not None
    assert (row.offset, row.length, row.type_code) == (9, 1, "A")


def test_a_spaced_row_is_unaffected() -> None:
    row = _parse_pdf_row("6 10 13 N (A) Rdto. Trabajo - Retribuciones dinerarias", 1)

    assert row is not None
    assert (row.offset, row.length, row.type_code) == (10, 13, "N")


def test_an_unknown_type_token_is_still_refused() -> None:
    """Admitting these two tokens must not admit any token at all."""
    assert _parse_pdf_row("26 192 1 Zzz Alguna descripcion", 1) is None


@pytest.mark.parametrize(
    "prefix", ["14-100-ejercicio-2009", "15-100-ejercicio-2010", "16-100-ejercicio-2011"]
)
def test_the_bundled_modelo_100_editions_carry_no_position_holes(prefix: str) -> None:
    """The real corpus case: each of these reported holes across most of its records."""
    matches = [path for path in _bundled_designs() if path.name.startswith(prefix)]
    assert matches, f"the bundled design {prefix!r} is no longer in the corpus"

    extraction = extract_record_design(matches[0])
    holes = [sheet for sheet in extraction.skipped if "not read at all" in sheet.reason]

    assert not holes, [sheet.reason[:120] for sheet in holes]


@pytest.mark.parametrize(
    "prefix", ["17-100-ejercicio-2012", "18-100-ejercicio-2013", "19-100-ejercicio-2014"]
)
def test_the_later_editions_still_lose_one_doubly_glued_row(prefix: str) -> None:
    """The limit of what reading a token can recover, pinned rather than hidden.

    These three editions write the same row as ``59 1A Indicador de pagina
    complementaria`` -- BOTH spaces lost, so ordinal 5 and position 9 are glued
    into ``59`` as well as length and type into ``1A``. ``1A`` splits on its own
    evidence because length is digits and type is a closed set. ``59`` does not:
    it is equally readable as ordinal 59, and only the surrounding sequence --
    the previous row being ordinal 4 at position 8 -- would say otherwise. That
    is inference from context rather than reading a declared value, and this
    reader does not invent positions.

    The declared-correction sidecar cannot express it either, and for a related
    reason: a single-position correction attaches to a line that presents a
    position candidate, and this line presents none at all, because its first
    token is not a bare position.

    So exactly one byte per edition stays unread and stays REPORTED. This test
    exists so that is a recorded limit with its reason attached rather than an
    absence someone later reads as coverage -- and so that anyone who does
    ground a fix sees this expectation fail and knows to remove it.
    """
    matches = [path for path in _bundled_designs() if path.name.startswith(prefix)]
    assert matches, f"the bundled design {prefix!r} is no longer in the corpus"

    extraction = extract_record_design(matches[0])
    holes = [sheet for sheet in extraction.skipped if "not read at all" in sheet.reason]

    assert len(holes) == 1, [sheet.reason[:120] for sheet in holes]
    assert "but 9 were not read at all" in holes[0].reason
