"""Real-behaviour tests for the per-modelo casilla label derivation.

The claim this module makes is that the collapse loses nothing, so the round
trip carries the weight here. A round trip that only ever passes proves that the
arithmetic is self-consistent, not that it would notice a loss - so the
reconstruction is also shown failing on a derived form with an override
removed, which is the shape a generator bug would produce.
"""

from __future__ import annotations

import dataclasses

import pytest

from ..casilla_label_derivation import DerivedLabels, derive_labels, derived_from, expand_labels
from ..revision_label_restatement import casilla_labels

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_LOCALE = "es"


@pytest.fixture(scope="module")
def shipped() -> dict[str, dict[str, dict[str, str]]]:
    return casilla_labels(_LOCALE)


@pytest.fixture(scope="module")
def derived() -> DerivedLabels:
    return derive_labels(_LOCALE)


def test_the_derived_form_reproduces_every_shipped_label(
    derived: DerivedLabels, shipped: dict[str, dict[str, dict[str, str]]]
) -> None:
    """Expanding the derivation returns the shipped mapping byte-for-byte.

    Compared as whole mappings rather than by sampling: a derivation that lost
    one string in one modelo would pass any sample that missed it, and the one
    string it lost is taxpayer-facing text.
    """
    assert shipped, "no labels were read, so the round trip compared nothing"
    assert expand_labels(derived) == shipped


def test_the_round_trip_detects_a_dropped_override(derived: DerivedLabels) -> None:
    """A derived form missing one override no longer reproduces the corpus.

    Constructed rather than waited for. Without this the round trip above could
    pass while comparing something to itself.
    """
    modelo = next(iter(derived.overrides))
    casilla = next(iter(derived.overrides[modelo]))
    thinned = dict(derived.overrides)
    thinned[modelo] = {key: value for key, value in derived.overrides[modelo].items() if key != casilla}
    damaged = dataclasses.replace(derived, overrides=thinned)

    rebuilt = expand_labels(damaged)
    assert rebuilt != expand_labels(derived)
    # The loss must land on the casilla whose override was removed, not merely
    # somewhere: a reconstruction that differed for an unrelated reason would
    # satisfy an inequality while proving nothing about the dropped override.
    assert rebuilt[modelo][casilla] != expand_labels(derived)[modelo][casilla]
    assert len(set(rebuilt[modelo][casilla].values())) == 1


def test_the_derivation_stores_fewer_strings_than_the_catalogue(
    derived: DerivedLabels, shipped: dict[str, dict[str, dict[str, str]]]
) -> None:
    """The collapse is a reduction, and the residual is the override population.

    Held as an ordering. The size of the reduction is what the module prints and
    moves with every landing revision; that it reduces at all is the property.
    """
    held = sum(len(texts) for casillas in shipped.values() for texts in casillas.values())
    assert 0 < derived.strings < held
    assert derived.overrides, "a corpus with no override at all would need no derivation"


def test_a_casilla_labelled_identically_everywhere_needs_no_override() -> None:
    """The restated population collapses to one string and no override.

    The whole point of the derivation, asserted through the derived form on
    constructed input so it does not depend on the corpus continuing to contain
    such a casilla. Asserted on the OVERRIDES too: a derivation that chose the
    right canonical text and then recorded it as an override as well would
    reproduce the corpus perfectly and save nothing.
    """
    derived = derived_from(
        {"200": {"00001": {"2023": "misma", "2024": "misma", "2025": "misma"}}},
    )
    assert derived.canonical == {"200": {"00001": "misma"}}
    assert derived.overrides == {}
    assert derived.strings == 1


def test_the_canonical_choice_does_not_depend_on_revision_ordering() -> None:
    """The same disagreement yields the same canonical text whatever the order.

    A derivation whose output depends on the order the catalogue was written in
    cannot be checked by re-running it, and an evenly split casilla is exactly
    where that dependence would hide.
    """
    from ..casilla_label_derivation import _canonical_text

    forwards = _canonical_text({"2023": "beta", "2024": "alfa"})
    backwards = _canonical_text({"2024": "alfa", "2023": "beta"})
    assert forwards == backwards == "alfa"
    # A majority beats the tie-break, or the tie-break would silently decide
    # cases that are not ties.
    assert _canonical_text({"2023": "beta", "2024": "beta", "2025": "alfa"}) == "beta"
