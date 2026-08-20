"""A row whose PDF columns were emitted out of order, and the guard around repairing it.

Modelo 200's older editions emit some rows as two lines with the columns
swapped: ``17 Num Ret. e ingr. a cuenta ...`` followed by ``30 419 [596]``,
where AEAT's row is ``30 419 17 Num Ret. e ingr. a cuenta ... [596]``. Neither
half is a row alone -- the first declares no position, the second no width --
and each supplies exactly the columns the other lacks.

WHY THE REPAIR IS CONDITIONAL, which is the substance of this module. A design
may emit the SAME row both split and intact. Joining the split copy then
declares a position the intact row already declares, and contiguity permits that
as containment, so it is silent: applied unconditionally the repair added twelve
duplicate importe fields to each of modelo 200's 2012-2014 editions, records
that had no unread positions at all.

So the repair is offered only to a design that reports something skipped, and
kept only if it leaves strictly fewer positions uncovered. That count is taken
over the parse state rather than the finished extraction, because a record with
holes is REPORTED rather than handed over -- which is exactly where this repair
does its work. Two earlier decision rules measured the extraction instead, saw
no difference, and left the repair permanently dead.
"""

from __future__ import annotations

import pytest

from .._record_design import _rejoin_reversed_column_rows

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_the_two_halves_of_a_swapped_row_are_reassembled() -> None:
    joined = _rejoin_reversed_column_rows(
        ("17 Num Ret. e ingr. a cuenta participaciones I.I.C.", "30 419 [596]"),
    )

    assert joined == ("30 419 17 Num Ret. e ingr. a cuenta participaciones I.I.C. [596]",)


def test_a_head_half_that_is_already_a_whole_row_is_left_alone() -> None:
    """The second line here needs no help; absorbing the first would duplicate it."""
    lines = ("17 N Sociedades de garantia reciproca - Cuenta", "30 419 17 N Sociedades de garantia reciproca")

    assert _rejoin_reversed_column_rows(lines) == lines


def test_a_pair_whose_identity_an_intact_row_already_claims_is_left_alone() -> None:
    """The duplicate guard: the design states row 30 at 419 intact elsewhere."""
    lines = (
        "30 419 17 Num Tributacion conjunta Estado y Adm. Forales",
        "17 Num Tributacion conjunta Estado y Adm. Forales",
        "30 419",
    )

    assert _rejoin_reversed_column_rows(lines) == lines


def test_ordinary_lines_are_untouched() -> None:
    lines = ("28 385 17 N Cuota liquida positiva [592]", "alguna prosa cualquiera")

    assert _rejoin_reversed_column_rows(lines) == lines
