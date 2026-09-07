"""Gate: the set of unrendered TUI interfaces only ever shrinks.

The teeth are both directions, because a one-directional ratchet on this
signal would be half a gate. Debt arriving is the obvious failure; a recorded
name that has quietly become rendered is the one that lets the file drift into
fiction, and it is the failure this campaign actually committed twice -- once
on the symbol ratchet, once on the classification ledger's spent test rows.
"""

from __future__ import annotations

import pytest

from ..tui_render_coverage_ratchet import drift, recorded_qualnames, unrendered_qualnames

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_the_shipped_tree_matches_its_declaration() -> None:
    """The direction the gate exists for, in both senses."""
    added, spent = drift(unrendered_qualnames(), recorded_qualnames())

    assert (added, spent) == ((), ()), (
        f"interfaces newly unrendered: {added}; recorded but now rendered or gone: {spent}. "
        "Give a new one a surface or record it; remove a spent one in the step that earned it."
    )


def test_the_declaration_still_names_interfaces() -> None:
    """A vacuity floor: an empty file would make the shrink direction inert."""
    recorded = recorded_qualnames()

    assert len(recorded) >= 5, (
        f"the declaration records only {len(recorded)} interface(s); either the backlog is "
        "genuinely near zero and this floor should be lowered deliberately, or the reader "
        "has drifted and the gate is inert rather than satisfied"
    )


def test_the_scan_still_finds_interfaces() -> None:
    """A vacuity floor on the live side: scanning nothing would make everything look rendered."""
    from dev.tui import _inventory

    assert len(_inventory.scan()) >= 30, (
        "the interface scan collapsed; a gate reading an empty tree reports full coverage"
    )


def test_new_debt_fails() -> None:
    """Detector teeth: an interface that lost its surface."""
    assert drift(frozenset({"a.B", "c.D"}), frozenset({"a.B"})) == (("c.D",), ())


def test_unpaid_shrinkage_fails() -> None:
    """Detector teeth: an interface that gained a surface and stayed recorded.

    The half a count-based floor cannot see, and the half this campaign has
    twice left unpaid on a sibling ratchet.
    """
    assert drift(frozenset({"a.B"}), frozenset({"a.B", "c.D"})) == ((), ("c.D",))


def test_a_swap_is_not_silent() -> None:
    """Detector teeth: one gained and one lost nets to zero on a count, not here."""
    assert drift(frozenset({"a.B"}), frozenset({"c.D"})) == (("a.B",), ("c.D",))


def test_an_exact_match_passes() -> None:
    """The normal case, so the gate is not merely always-red."""
    assert drift(frozenset({"a.B"}), frozenset({"a.B"})) == ((), ())
