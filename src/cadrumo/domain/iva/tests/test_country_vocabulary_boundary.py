"""A shape-valid country code that names no country establishes nothing.

The country rung is a match against a bounded vocabulary, not a shape check.
That distinction is the whole of this file, and it is not a stylistic one: the
resolver used to answer :attr:`IvaTerritorialScope.THIRD_COUNTRY` for any
well-formed alpha-2 pair, so ``XX``, ``ZZ`` and ``QQ`` -- the ISO 3166-1
user-assigned ranges, which denote nothing by construction -- settled a party
outside the EU. On the issued side third country is export treatment, so an
issuer typo, a placeholder or a truncated field zero-rated the operation from
evidence the ladder treated as decisive. Shape-validity is not reference.

The properties gated here are the ones that could be wrong:

* the three measured probes yield NO scope, from every consumer of the axis;
* a genuine third country still resolves, so the narrowing did not trade a
  silent zero-rating for a refused legitimate export;
* both legs are equally bounded -- a stated alpha-2 code is narrowed exactly as
  a printed one is, so a machine-read document cannot establish more or less
  than the identical printed code;
* an unassigned code is DISTINGUISHABLE from an assigned one the bundled
  vocabulary happens not to carry, because one is a typo signal and the other
  is a data gap somebody can close;
* nothing degrades to Spain, ever.

Model-free and network-free: a lookup against bundled registry data.

See Also:
    :func:`~domain.iva.territorial_scope_for_country`
        The single authority this states the property at.
    :func:`~domain.iva.country_code_for_stated_country_code`
        The structured leg, narrowed in the same change.
"""

from __future__ import annotations

import pytest

from ....tests.country_vocabulary_specimens import an_uncatalogued_alpha2
from ..classification import IvaTerritorialScope
from ..establishment import (
    StatedCountryCodeStatus,
    country_code_for_stated_country_code,
    stated_country_code_status,
    territorial_scope_for_country,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

#: The ISO 3166-1 user-assigned codes the amendment names by hand. Each is a
#: well-formed alpha-2 pair reserved for private use, so each denotes nothing
#: by construction: a document stating one has stated a string, not a country.
UNASSIGNED_PROBES = ("XX", "ZZ", "QQ")

#: Countries the bundled vocabulary carries that are genuinely outside the EU.
#: The positive control for every refusal below -- a file proving only that the
#: axis refuses would pass with the axis broken shut.
CATALOGUED_THIRD_COUNTRIES = ("US", "JP", "BR")


@pytest.mark.parametrize("code", UNASSIGNED_PROBES)
def test_an_unassigned_code_establishes_no_scope(code: str) -> None:
    """The defect this file exists for, at the authority that produced it."""
    assert territorial_scope_for_country(code) is None


@pytest.mark.parametrize("code", UNASSIGNED_PROBES)
def test_an_unassigned_code_survives_neither_case_nor_padding(code: str) -> None:
    """The narrowing is applied after normalisation, not before it.

    A check placed before the trim and the case fold would pass this file while
    ``" xx "`` walked straight through it, which is the form a reader actually
    produces.
    """
    assert territorial_scope_for_country(f" {code.lower()} ") is None


@pytest.mark.parametrize("code", UNASSIGNED_PROBES)
def test_the_structured_leg_refuses_the_same_codes(code: str) -> None:
    """Both legs move together, or the machine-read document disagrees with the page.

    A structured leg looser than the printed one would let a UBL ``CountryCode``
    of ``XX`` establish a territory that the identical string printed in an
    address block does not.
    """
    assert country_code_for_stated_country_code(code) is None


@pytest.mark.parametrize("code", CATALOGUED_THIRD_COUNTRIES)
def test_a_genuine_third_country_still_resolves(code: str) -> None:
    """The opposite direction. Refusing a real export is its own defect."""
    assert territorial_scope_for_country(code) is IvaTerritorialScope.THIRD_COUNTRY
    assert country_code_for_stated_country_code(code) == code


def test_a_member_state_still_resolves() -> None:
    """The EU branch is not collateral damage of the narrowing."""
    assert territorial_scope_for_country("DE") is IvaTerritorialScope.EU_MEMBER


def test_northern_ireland_survives_the_narrowing() -> None:
    """``XI`` is user-assigned in shape and a Member State in this catalogue.

    The one code where the two authorities disagree, and the reason the
    vocabulary is the union of them rather than the printed-name table alone: a
    narrowing that consulted only the name table would drop Northern Ireland out
    of the intra-community branch, and a narrowing that consulted only the
    user-assigned ranges would drop it as a placeholder.
    """
    assert territorial_scope_for_country("XI") is IvaTerritorialScope.EU_MEMBER


def test_spain_still_refuses_for_its_own_reason() -> None:
    """Spain returns nothing BY DESIGN, and must not be reclassified as unmatched."""
    assert territorial_scope_for_country("ES") is None
    assert stated_country_code_status("ES") is StatedCountryCodeStatus.CATALOGUED


@pytest.mark.parametrize("code", UNASSIGNED_PROBES)
def test_an_unassigned_code_is_reported_as_unassigned(code: str) -> None:
    """The typo signal. Distinguishable, or the operator cannot act on it."""
    assert stated_country_code_status(code) is StatedCountryCodeStatus.UNASSIGNED


def test_an_assigned_code_the_vocabulary_omits_is_a_catalogue_gap() -> None:
    """A data gap must be fixable rather than indistinguishable from garbage.

    The specimen is DERIVED from the vocabulary rather than named, because the
    property under test is the boundary and any particular country outside it is
    an accident of when this was written. A pinned country reds this case the day
    it is admitted, which says nothing about the behaviour and everything about
    the fixture.

    The honest report for such a code is that this codebase cannot yet say what
    it establishes -- not that the issuer typed nonsense. It fires no rung until
    the catalogue carries it.
    """
    specimen = an_uncatalogued_alpha2()

    assert stated_country_code_status(specimen) is StatedCountryCodeStatus.UNCATALOGUED
    assert territorial_scope_for_country(specimen) is None


@pytest.mark.parametrize("code", CATALOGUED_THIRD_COUNTRIES)
def test_a_catalogued_code_reports_as_catalogued(code: str) -> None:
    """Positive control over the status axis itself."""
    assert stated_country_code_status(code) is StatedCountryCodeStatus.CATALOGUED


@pytest.mark.parametrize("stated", [None, "", "  ", "Germany", "D", "E1", "1234"])
def test_nothing_that_is_not_an_alpha2_code_gets_a_status(stated: str | None) -> None:
    """A status is a statement ABOUT a code, so a non-code gets none.

    Reporting an address line as an unassigned country code would spend the
    operator's attention naming a string nobody claimed was a country.
    """
    assert stated_country_code_status(stated) is None


@pytest.mark.parametrize("code", [*UNASSIGNED_PROBES, "QM", "AA", "XA"])
def test_no_unmatched_code_degrades_to_spain(code: str) -> None:
    """The failure every rung on this axis refuses, restated at the new boundary.

    The derived catalogue-gap specimen is checked alongside the reserved codes,
    so both ways of being unmatched are covered without either being pinned.
    """
    assert country_code_for_stated_country_code(an_uncatalogued_alpha2()) != "ES"
    assert country_code_for_stated_country_code(code) != "ES"
    assert territorial_scope_for_country(code) is not IvaTerritorialScope.ES_MAINLAND
