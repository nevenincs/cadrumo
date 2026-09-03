"""The corpus accessor every screen asks for its modelo list.

Ten screen modules declared this three-line function privately and identically
before it had a home. It has one now, and a defining module owes the same proof
of behaviour a screen does - which nothing required, because the gate that
demands a test module asks it only of screens.
"""

from __future__ import annotations

import pytest

from cadrumo.domain.calculations.registry.authority import ValidatedRegistryAuthority, bundled_authority

from ..analysis.corpus import bundled_modelo_ids

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


@pytest.fixture(scope="module")
def authority() -> ValidatedRegistryAuthority:
    return bundled_authority()


def test_the_corpus_is_every_modelo_the_authority_carries(authority: ValidatedRegistryAuthority) -> None:
    """The list is the registry's, not a maintained copy of it.

    A screen walking a stale list reports a clean corpus by not looking at part
    of it, which is the failure this package has now found in three of its own
    instruments.
    """
    ids = bundled_modelo_ids()

    assert ids, "the corpus accessor returned nothing, so every screen would sweep an empty tree"
    assert set(ids) == {str(modelo.id) for modelo in authority.modelos}


def test_the_order_is_stable_and_the_members_are_strings() -> None:
    """Sorted strings, because the screens' output is compared line by line.

    An unordered walk makes two runs over one registry produce diffs that say
    nothing, and a non-string member would format into a row that greps
    differently from every other row.
    """
    ids = bundled_modelo_ids()

    assert list(ids) == sorted(ids)
    assert all(isinstance(item, str) for item in ids)
    assert len(set(ids)) == len(ids), "a repeated modelo would be screened twice and counted twice"
