"""The module's list of handled text-show operators is joined to the set.

The sanitiser rewrites only the operands of the text-show operators it walks,
so that list IS the coverage claim of a leak boundary. It carried a count of
five over a list of four against a four-member set, and nothing compared any
of the three.
"""

from __future__ import annotations

import re

import pytest

from .. import _streams

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

#: An operator bullet in the module docstring's handled-operator list.
_OPERATOR_BULLET = re.compile(r"^\* ``(.+?)``", re.MULTILINE)


def _documented_operators() -> frozenset[str]:
    """The operator tokens the module docstring lists as handled."""
    assert _streams.__doc__ is not None, "the module docstring is the documentation under test"
    return frozenset(_OPERATOR_BULLET.findall(_streams.__doc__))


def _walked_operators() -> frozenset[str]:
    """The operator tokens the page walk actually matches on.

    Read off the pikepdf operators themselves rather than off any spelling of
    them, so an operator added to or dropped from the set moves this side
    without anybody remembering to.
    """
    return frozenset(str(operator) for operator in _streams._TEXT_OPERATORS)


def test_the_docstring_lists_every_text_show_operator_the_walk_handles() -> None:
    """An operator the sanitiser rewrites that its coverage claim omits.

    The direction a reviewer is misled by: the list reads as the boundary,
    so an operator missing from it is coverage nobody knows they have and
    nobody re-checks when the walk changes.
    """
    undocumented = sorted(_walked_operators() - _documented_operators())

    assert not undocumented, (
        f"the page walk rewrites the operands of {undocumented}, which the module docstring never lists; "
        "the list is read as this sanitiser's coverage claim"
    )


def test_the_docstring_lists_no_text_show_operator_the_walk_skips() -> None:
    """An operator the docstring claims and the walk never matches.

    The dangerous direction. An operator dropped from the set leaves its
    bullet standing, and the bullet reads exactly like the ones still true --
    so cleartext carried by that operator passes through unrewritten while
    the module still says it is handled.
    """
    unhandled = sorted(_documented_operators() - _walked_operators())

    assert not unhandled, (
        f"the module docstring lists {unhandled} as handled, but the page walk matches no such operator; "
        "text shown by it is left unrewritten while the claim stands"
    )
