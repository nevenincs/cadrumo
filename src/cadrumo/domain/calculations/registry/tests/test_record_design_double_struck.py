"""A row whose glyphs the PDF text layer emitted twice.

Modelo 390's 2015 edition double-strikes some rows: ``4422 662255 1177 NN 55..
OOppeerraacciioonneess`` is ``42 625 17 N 5. Operaciones``, every character
duplicated while the separating spaces stay single. Eight rows arrive that way
and each is a position the record otherwise reports as dropped -- 324, 625, 659
and their siblings all appear in that design's hole list.

THE REPAIR IS SELF-VERIFYING, which is what separates it from a guess. A line is
rewritten only when three things hold together: it does not parse as a row, the
tokens it is built from are exact pairwise repetitions, and the de-doubled
result DOES parse. Fail any one and the line is returned untouched. Nothing here
reasons about what the row ought to say; the doubling either undoes cleanly into
a row or it does not.

Like every row-adding repair in this reader it runs only in the repair pass, so
a design whose records already tile is never offered it.
"""

from __future__ import annotations

import pytest

from ..record_design_pdf_repairs import undouble_struck_rows

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_a_double_struck_row_is_undoubled() -> None:
    line = "4422 662255 1177 NN 55.. OOppeerraacciioonneess"

    assert undouble_struck_rows((line,)) == ("42 625 17 N 5. Operaciones",)


def test_a_row_that_already_parses_is_never_touched() -> None:
    """Even where its tokens happen to look doubled."""
    line = "44 6600 22 An Alguna descripcion"

    assert undouble_struck_rows((line,)) == (line,)


def test_a_line_that_does_not_become_a_row_is_left_alone() -> None:
    """Undoing the doubling has to PRODUCE something, or it is not evidence."""
    line = "aabbcc ddeeff gghhii"

    assert undouble_struck_rows((line,)) == (line,)


def test_prose_is_untouched() -> None:
    line = "Los campos numericos solo admiten numeros"

    assert undouble_struck_rows((line,)) == (line,)


def test_an_odd_length_token_disqualifies_that_token_only() -> None:
    """A single-struck fragment beside doubled ones must not veto the row."""
    line = "4422 662255 1177 NN 55.. Operaciones"

    assert undouble_struck_rows((line,)) == ("42 625 17 N 5. Operaciones",)
