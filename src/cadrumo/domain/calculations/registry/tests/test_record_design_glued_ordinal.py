"""A row whose ordinal and position were run together, split only when pinned.

Modelo 200's older editions lose the space after the ordinal on the three
identifier rows of most records, writing ``23 3 Num Modelo. OBLIGATORIO
Constante "200"`` where AEAT declares ordinal 2 at position 3. Thirty-two of the
forty holed records in the 2010 edition report the resulting ``3-9`` gap; it is
the single most common hole shape in the corpus.

WHY THIS IS A READING AND NOT A GUESS. ``23`` alone is as readable as ordinal
23. The split is admitted only when it is over-determined: ordinal 2 and
position 3 are taken only if BOTH the ordinal continues the previous row's by
one AND the position resumes exactly where the previous row ended. Two
independent facts, from a row already read, must agree. Either failing, or any
other split satisfying neither, leaves the gap reported.

That is precisely why the same shape was recorded and left alone when it was
first met on modelo 100: there the glued row stands alone with no read row
before it, so nothing closes the constraint. Nothing about the token changed --
the surrounding rows did.

AND IT ONLY RUNS AS A REPAIR. Like the reversed-column rejoin beside it, the
split is offered only to a design that already reports something skipped. A
design whose records tile their extents returns its first read untouched. That
guard is not decoration: before it existed the split added fields to modelo
200's 2012-2014 editions, which had no unread positions at all.
"""

from __future__ import annotations

import pytest

from ..record_design import _split_glued_ordinal_position
from ..record_design_schema import RecordDesignField

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _previous(ordinal: str, offset: int, length: int) -> RecordDesignField:
    return RecordDesignField(
        sheet="body",
        row=offset,
        ordinal=ordinal,
        offset=offset,
        length=length,
        type_code="An",
        description="previa",
    )


def test_a_glued_row_is_split_when_both_constraints_agree() -> None:
    row = _split_glued_ordinal_position(
        '23 3 Num Modelo. OBLIGATORIO Constante "200"', 10, previous=_previous("1", 1, 2)
    )

    assert row is not None
    assert (row.ordinal, row.offset, row.length) == ("2", 3, 3)


def test_the_split_is_refused_when_the_ordinal_does_not_continue() -> None:
    """Position would fit, but the ordinal does not follow -- so nothing is claimed."""
    assert _split_glued_ordinal_position("23 3 Num Modelo", 10, previous=_previous("7", 1, 2)) is None


def test_the_split_is_refused_when_the_position_does_not_resume() -> None:
    """Ordinal would follow, but the position leaves a gap -- so nothing is claimed."""
    assert _split_glued_ordinal_position("23 3 Num Modelo", 10, previous=_previous("1", 1, 5)) is None


def test_a_row_that_already_parses_is_never_resplit() -> None:
    assert _split_glued_ordinal_position("2 3 3 Num Modelo", 10, previous=_previous("1", 1, 2)) is None


def test_the_first_row_of_a_record_is_never_split() -> None:
    """With no previous row there is nothing to close the constraint."""
    assert _split_glued_ordinal_position("23 3 Num Modelo", 10, previous=None) is None
