"""The per-field provenance axis is a closed set with stable stored tokens.

Two properties are load-bearing and neither is self-evident from reading the
enum. The member SET is closed: an origin silently added or dropped changes
what a persisted record is able to say about how a value was obtained, and a
consumer branching on the axis would then be incomplete without any signal.
The stored TOKENS are the persisted form: a token that drifts from its member
name makes previously written records unhydratable, so each is pinned to its
literal rather than derived from the member (deriving it from ``.name.lower()``
would restate the implementation and pass no matter what the class said).
"""

from __future__ import annotations

import pytest

from ..field_origin import FieldOrigin

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


_EXPECTED_TOKENS = {
    "EXACT_STRUCTURED": "exact_structured",
    "TEXT_LAYER": "text_layer",
    "VISION": "vision",
    "TABULAR_MAPPED": "tabular_mapped",
    "OPERATOR": "operator",
    # Not a reading. Every member above answers how a value was copied off the
    # document; this one answers what followed from what was copied, and a
    # persisted record has to keep the two apart.
    "DERIVED": "derived",
}


def test_the_member_set_is_exactly_the_declared_origins() -> None:
    """A silent addition or removal reddens here.

    Written against member NAMES rather than the members themselves so a
    renamed member fails as a set difference the reader can act on.
    """
    assert {member.name for member in FieldOrigin} == set(_EXPECTED_TOKENS)


@pytest.mark.parametrize(("name", "token"), sorted(_EXPECTED_TOKENS.items()))
def test_each_member_carries_its_expected_stored_token(name: str, token: str) -> None:
    """Member value equals the token a persisted record stores."""
    assert FieldOrigin[name].value == token


@pytest.mark.parametrize(("name", "token"), sorted(_EXPECTED_TOKENS.items()))
def test_each_stored_token_hydrates_back_to_its_member(name: str, token: str) -> None:
    """The read direction: a stored token resolves to the member that wrote it."""
    assert FieldOrigin(token) is FieldOrigin[name]


def test_an_unknown_token_is_refused_rather_than_accepted() -> None:
    """The positive controls above are only meaningful if the set is truly closed.

    Without this, a permissive enum would satisfy every assertion here while
    admitting arbitrary strings at the boundary.
    """
    with pytest.raises(ValueError, match="structured_record"):
        FieldOrigin("structured_record")


def test_an_exactly_read_origin_is_not_equal_to_a_model_read_one() -> None:
    """The distinction the enum exists to preserve, asserted directly.

    A vision-read value must never compare equal to an exactly-read one; that
    equality is precisely the laundering the axis is meant to make impossible.
    """
    assert FieldOrigin.EXACT_STRUCTURED != FieldOrigin.VISION
    assert FieldOrigin.EXACT_STRUCTURED.value != FieldOrigin.VISION.value
