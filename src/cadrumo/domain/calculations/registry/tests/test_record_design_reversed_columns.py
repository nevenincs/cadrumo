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

from ..record_design import _rejoin_reversed_column_rows, _row_identities_by_record

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_the_two_halves_of_a_swapped_row_are_reassembled() -> None:
    joined = _rejoin_reversed_column_rows(
        ("17 Num Ret. e ingr. a cuenta participaciones I.I.C.", "30 419 [596]"),
    )

    assert joined == ("30 419 17 Num Ret. e ingr. a cuenta participaciones I.I.C. [596]",)


def test_the_two_halves_are_reassembled_in_natural_order_too() -> None:
    """The row may simply break after its position, with no column swap at all.

    Modelo 200's 2010 editions do this roughly 1,500 times: a page break lands
    mid-row and leaves ``7 28`` above ``17 Num Deducc...``. It is the same row
    split over two lines as the swapped case, so it is read the same way -- and
    refused the same way when either half stands on its own.
    """
    joined = _rejoin_reversed_column_rows(
        ("7 28", "17 Num Deducc para incentivar determinadas actividades"),
    )

    assert joined == ("7 28 17 Num Deducc para incentivar determinadas actividades",)


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


def test_the_duplicate_guard_is_scoped_to_the_record_that_states_the_row() -> None:
    """A row identity in ANOTHER record must not block a join in this one.

    Every record restarts at ordinal 1, position 1, so low identities recur all
    through a design: measured on modelo 200's 2010 edition, ``(30, 419)`` is
    stated intact by 28 different records. A design-wide guard therefore refused
    almost every legitimate join, and refused them silently, because a refused
    join looks exactly like no join at all.
    """
    lines = (
        "1 1 2 An Inicio del primer registro",
        "30 419 17 N Fila intacta del PRIMER registro",
        "1 1 2 An Inicio del segundo registro",
        "17 Num Mitad partida del SEGUNDO registro",
        "30 419 [596]",
    )

    joined = _rejoin_reversed_column_rows(lines)

    assert joined[-1] == "30 419 17 Num Mitad partida del SEGUNDO registro [596]"
    assert len(joined) == len(lines) - 1


def test_an_identity_the_same_record_states_intact_still_blocks_the_join() -> None:
    lines = (
        "1 1 2 An Inicio del registro",
        "30 419 17 N Fila intacta de ESTE registro",
        "17 Num Mitad partida del MISMO registro",
        "30 419",
    )

    assert _rejoin_reversed_column_rows(lines) == lines


def test_record_identities_are_partitioned_at_each_position_one_row() -> None:
    identities = _row_identities_by_record(
        ("1 1 2 An Primero", "5 10 1 An Otro", "1 1 2 An Segundo", "9 40 3 Num Tercero"),
    )

    assert ("5", 10) in identities[0]
    assert ("5", 10) not in identities[-1]
    assert ("9", 40) in identities[-1]


def test_a_head_carrying_bled_description_text_joins_when_it_continues() -> None:
    """The last shapes in modelo 200 leak description onto the head's own line.

    ``79 1236 (2 a 6) [021]`` is the position half of a row whose description
    fragment landed beside it. The pattern alone would match prose beginning
    with two numbers, so it is admitted only under the same over-determination
    the glued-ordinal split uses: ordinal 79 follows 78, and position 1236 is
    exactly where the previous row's 1219 plus 17 ends.
    """
    lines = (
        "78 1219 17 Num Reg.reserva inversiones Canarias - Inv.anticipadas",
        "17 Num Reg.reserva inversiones Canarias - futuras dotaciones",
        "79 1236 (2 a 6) [021]",
    )

    joined = _rejoin_reversed_column_rows(lines)

    assert joined[-1].startswith("79 1236 17 Num ")
    assert len(joined) == len(lines) - 1


def test_a_bled_head_that_does_not_continue_is_refused() -> None:
    """Without continuity there is nothing separating this from prose."""
    lines = (
        "78 1219 17 Num Algo",
        "17 Num Otra cosa",
        "90 5000 prosa cualquiera que empieza con numeros",
    )

    assert _rejoin_reversed_column_rows(lines) == lines
