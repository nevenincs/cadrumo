"""Two ways a row's own punctuation cost it its position.

``An.`` IS THE SAME NATURALEZA AS ``An``. Modelo 131 writes
``52 464 13 An. Complementaria (7) - Numero de Justificante anterior``, with
abbreviation punctuation after the type. The narrative recogniser has always
accepted that -- ``_naturaleza_or_none`` strips " ." before matching -- so the
compact path was simply out of step with the recogniser beside it. Three lines
in three designs, and they were the whole of modelo 131's reported damage: each
edition lost this one 13-byte row and reported it as a dropped run.

A STUTTERED PREFIX REPEATS WHAT THE ROW ALREADY SAYS. Modelo 200's 2010 and
2011 editions emit nine rows as ``99 1592 99 1592 17 Num ...``, and every one of
those positions is otherwise unread. Dropping the first pair asserts nothing the
line does not state twice about itself.

WHY ONLY THAT SHAPE. A row can also arrive behind genuine leading text, where a
wrapped description spills onto its line -- modelo 131's
``Domiciliacion 48 465 1 Num Ingreso (4) - Forma de pago`` is one. Those cannot
be admitted on the line's own evidence: measured across the bundled corpus,
lines of that shape include both real rows and prose carrying number sequences,
and nothing in the line separates them. A back-reference to the same two numbers
carries no such ambiguity, so that is where the line is drawn.
"""

from __future__ import annotations

import pytest

from ..record_design import extract_record_design
from ..record_design_pdf_repairs import _collapse_stuttered_row_prefix
from ..record_design_pdf_rows import _parse_pdf_row
from .test_every_bundled_design_is_read_or_reported import _bundled_designs

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_a_type_written_with_abbreviation_punctuation_still_parses() -> None:
    row = _parse_pdf_row("52 464 13 An. Complementaria (7) - Numero de Justificante anterior", 1)

    assert row is not None
    assert (row.offset, row.length, row.type_code) == (464, 13, "An")


def test_a_stuttered_ordinal_and_position_prefix_is_dropped() -> None:
    assert _collapse_stuttered_row_prefix(("99 1592 99 1592 17 Num Deducciones",)) == ("99 1592 17 Num Deducciones",)


def test_an_ordinary_row_is_untouched() -> None:
    assert _collapse_stuttered_row_prefix(("99 1592 17 Num Deducciones",)) == ("99 1592 17 Num Deducciones",)


def test_a_near_miss_is_not_treated_as_a_stutter() -> None:
    """The back-reference must match exactly; two different positions are two claims."""
    line = "99 1592 99 1593 17 Num Deducciones"

    assert _collapse_stuttered_row_prefix((line,)) == (line,)


def test_genuine_leading_text_is_never_stripped() -> None:
    """The case deliberately left unhandled, pinned so it is not quietly widened."""
    line = "Domiciliacion 48 465 1 Num Ingreso (4) - Forma de pago"

    assert _collapse_stuttered_row_prefix((line,)) == (line,)


@pytest.mark.parametrize("prefix", ["02-131-ejercicio-2008-primer", "03-131-ejercicio-2008-trimestre"])
def test_the_bundled_modelo_131_editions_now_read_whole(prefix: str) -> None:
    matches = [path for path in _bundled_designs() if path.name.startswith(prefix)]
    assert matches, f"the bundled design {prefix!r} is no longer in the corpus"

    extraction = extract_record_design(matches[0])

    assert not extraction.skipped, [sheet.reason[:120] for sheet in extraction.skipped]
    assert extraction.is_complete
