"""The canonical elider is total, visible, and enforced by the type.

Three properties carry the whole point of this primitive, and each is asserted
against a consequence rather than against the implementation:

* **Total.** Every input satisfies the cap. A clamp that can still exceed its
  bound would put the raise back where the type promised to remove it.
* **Visible.** A cut is marked, so a shortened advisory cannot be read as a
  terse one. These messages carry remedies; losing words silently is its own
  defect.
* **Type-enforced.** A field declared with the annotation elides without the
  construction site doing anything, which is what makes it total for builders
  nobody has written yet.
"""

from __future__ import annotations

import pytest
from pydantic import BaseModel, Field, ValidationError

from ..prose_elision import PROSE_ELISION_MARKER, elide_to_cap, elided_prose

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


class _Capped(BaseModel):
    """A field declaring the eliding annotation and nothing else."""

    # Declared through the factory deliberately: this model exists to prove that
    # form still elides, so rewriting it to the literal annotation would delete
    # the thing under test.
    text: elided_prose(40)  # ty: ignore[invalid-type-form]


class _LengthConstrained(BaseModel):
    """The behaviour the annotation replaces, for contrast."""

    text: str = Field(min_length=1, max_length=40)


@pytest.mark.parametrize("cap", [8, 40, 128, 256, 300, 500, 512])
@pytest.mark.parametrize("length", [0, 1, 39, 511, 512, 5000])
def test_elide_to_cap_never_exceeds_the_cap(cap: int, length: int) -> None:
    """Totality, across every cap the tree declares and lengths around them.

    This is the property the type-level clamp trades a raise for. If it can be
    violated at any input the annotation is worse than the raise it replaced:
    the constraint behind it would fire, and the failure would resurface at the
    boundary the elision existed to protect.
    """
    assert len(elide_to_cap("word " * length, cap=cap)) <= cap


def test_a_message_that_already_fits_is_returned_untouched() -> None:
    """Eliding is not reformatting; a message under the cap must survive exactly."""
    message = "ledger row 7 declares IVA without a taxable base"

    assert elide_to_cap(message, cap=512) == message


def test_a_message_exactly_at_the_cap_is_returned_untouched() -> None:
    """The boundary is inclusive; an at-cap message is valid and must not be cut."""
    message = "y" * 512

    assert elide_to_cap(message, cap=512) == message


def test_a_cut_message_is_marked_as_cut() -> None:
    """Visibility. An operator must be able to tell a shortened message from a short one."""
    assert elide_to_cap("word " * 300, cap=512).endswith(PROSE_ELISION_MARKER)


def test_a_cut_falls_on_a_word_boundary_rather_than_mid_word() -> None:
    """A message ending in half an identifier reads as corruption, not truncation."""
    cut = elide_to_cap("alpha bravo charlie " * 40, cap=100)
    body = cut[: -len(PROSE_ELISION_MARKER)]

    assert not body.endswith(" ")
    assert body.split()[-1] in {"alpha", "bravo", "charlie"}, (
        f"the cut ended mid-word on {body.split()[-1]!r}; every word in the input is whole"
    )


def test_a_cap_too_small_to_hold_the_marker_still_produces_a_bounded_string() -> None:
    """Degenerate but total: no room to signal a cut is not licence to exceed the cap."""
    assert len(elide_to_cap("x" * 50, cap=3)) == 3


def test_the_annotation_elides_without_the_construction_site_helping() -> None:
    """The property that makes the clamp total for builders nobody has written yet.

    Nothing at this construction site knows about the cap. That is the whole
    difference from a call-site clamp, which is only as complete as the next
    author's memory.
    """
    model = _Capped(text="word " * 100)

    assert len(model.text) <= 40
    assert model.text.endswith(PROSE_ELISION_MARKER)


def test_the_annotation_still_refuses_empty_prose() -> None:
    """Eliding bounds the top, not the bottom; a blank message is a real defect."""
    with pytest.raises(ValidationError):
        _Capped(text="")


def test_the_raising_shape_is_what_the_annotation_replaces() -> None:
    """The control that gives the test above its meaning.

    Without this, a passing elision assertion could equally be explained by the
    cap not being enforced at all. This proves the same over-cap input against
    a plain capped field does raise, so the elision is a real behaviour change.
    """
    with pytest.raises(ValidationError):
        _LengthConstrained(text="word " * 100)
