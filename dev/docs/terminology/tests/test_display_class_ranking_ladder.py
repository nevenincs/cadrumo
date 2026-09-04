"""Ladder gate: the declared weight table matches the ratified ordering verbatim.

The ratified ranking decision moves the base-weight table
from per-kind to per-display-class and declares ONE user-first ordering:
general-fact concept cards (``doc``), then ``modelo``, then ``casilla``, then
``legal``, then ``cli``, then ``technical`` (api / dev machinery) pages last.
A BOE article or Orden GROUNDS a modelo or casilla surface rather than
answering the operator's question, so it ranks beneath both while still leading
the machinery tiers. This gate pins that ordering so a future reorder of the
declared table fails loudly, and proves every display class carries exactly one
weight (an unmapped class is a failure).

The expected ordering is derived strictly from the ratified ladder prose, never
copied from the table under test.
"""

from __future__ import annotations

from itertools import pairwise

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_core, pytest.mark.docs]


def test_every_display_class_carries_exactly_one_weight() -> None:
    """The declared table maps every ``ResultDisplayClass`` member to one weight.

    A class with no weight (or a table key that is not a member) is a gate
    failure: the derivation authority must never produce a class the ranking
    table cannot weigh.
    """
    from ..search_record import ResultDisplayClass
    from ..unified_record import display_class_base_weight

    weights = {member: display_class_base_weight(member) for member in ResultDisplayClass}
    assert set(weights) == set(ResultDisplayClass)
    assert all(0.0 <= weight <= 1.0 for weight in weights.values())


def test_weight_table_orders_the_d8_ladder_verbatim() -> None:
    """The base weights order ``doc > modelo > casilla > legal > cli > technical``.

    The expected sequence is the ratified user-first ladder prose: general-fact
    concept cards lead, then modelo document cards, then casilla rows, then the
    legal provisions that ground them, then CLI records, then technical
    (api / dev) pages last.
    """
    from ..search_record import ResultDisplayClass
    from ..unified_record import display_class_base_weight

    ladder_high_to_low = (
        ResultDisplayClass.DOC,
        ResultDisplayClass.MODELO,
        ResultDisplayClass.CASILLA,
        ResultDisplayClass.LEGAL,
        ResultDisplayClass.CLI,
        ResultDisplayClass.TECHNICAL,
    )
    weights = [display_class_base_weight(member) for member in ladder_high_to_low]
    assert weights == sorted(weights, reverse=True)
    # Strictly descending: no two adjacent classes share a rank band, so the
    # ladder ordering is unambiguous.
    assert all(higher > lower for higher, lower in pairwise(weights))


def test_ladder_covers_every_display_class_exactly_once() -> None:
    """The pinned D8 ladder enumerates every display class with no omission."""
    from ..search_record import ResultDisplayClass

    ladder = (
        ResultDisplayClass.DOC,
        ResultDisplayClass.MODELO,
        ResultDisplayClass.CASILLA,
        ResultDisplayClass.LEGAL,
        ResultDisplayClass.CLI,
        ResultDisplayClass.TECHNICAL,
    )
    assert len(ladder) == len(set(ladder)) == len(ResultDisplayClass)
    assert set(ladder) == set(ResultDisplayClass)


def test_legal_ranks_beneath_the_surfaces_it_grounds() -> None:
    """A legal provision sits below modelo and casilla, above the machinery tiers.

    The corrected ranking: a BOE article or Orden grounds a modelo or casilla
    surface rather than answering the operator's question. Aliasing it onto the
    user-documentation class put every provision above the very cards it
    grounds, so this pins the corrected position from both sides.
    """
    from ..search_record import ResultDisplayClass
    from ..unified_record import display_class_base_weight

    legal = display_class_base_weight(ResultDisplayClass.LEGAL)

    assert display_class_base_weight(ResultDisplayClass.CASILLA) > legal
    assert display_class_base_weight(ResultDisplayClass.MODELO) > legal
    assert display_class_base_weight(ResultDisplayClass.DOC) > legal
    assert legal > display_class_base_weight(ResultDisplayClass.CLI)
    assert legal > display_class_base_weight(ResultDisplayClass.TECHNICAL)


def test_casilla_outranks_cli_and_technical_ranks_last() -> None:
    """The two D8 amendments to the parent ladder: casilla > cli, technical last."""
    from ..search_record import ResultDisplayClass
    from ..unified_record import display_class_base_weight

    casilla = display_class_base_weight(ResultDisplayClass.CASILLA)
    cli = display_class_base_weight(ResultDisplayClass.CLI)
    technical = display_class_base_weight(ResultDisplayClass.TECHNICAL)
    doc = display_class_base_weight(ResultDisplayClass.DOC)

    # D8 amendment 1: within the navigation tier casilla now outranks cli.
    assert casilla > cli
    # D8 amendment 2: the full-text tier splits so technical (api/dev) sinks
    # strictly below user documentation (doc).
    assert doc > technical
    assert technical == min(display_class_base_weight(member) for member in ResultDisplayClass)
