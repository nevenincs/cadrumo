"""LIVA art. 3 overrides the country catalogue in both directions.

The country rung answers from the Member State catalogue, which is right for
almost every code and wrong for a short named list. Ley 37/1992 art. 3 carves
territories OUT of the interior del país while they sit inside a Member State,
and apartado Tres brings three territories IN while they sit outside every one.
This gates the override.

**The case that forced the table is Monaco**, and it is the one worth stating
plainly: Monaco is outside the Union, every general country register carries it,
and it is not a Member State -- so resolving it from the catalogue alone answers
"third country", which on the issued side is export treatment. Art. 3.Tres says
operations with Monaco have the same consideration as operations with France. A
widening built from a country register would therefore have exempted a supply
that is not exempt, which is the same failure the country rung was narrowed to
close, reintroduced through the data instead of the code.

**Assimilation is gated as a POINTER, not as a scope**, because that is the
property that keeps it true. The article fixes what a territory is treated as and
says nothing about what the parent establishes, so the Isle of Man followed the
United Kingdom out of the Community without the article changing a word. The
tests below assert Monaco AGREES WITH FRANCE and the Isle of Man AGREES WITH THE
UNITED KINGDOM rather than pinning either to a literal scope: a literal would
pass today and would have to be edited the day a parent's status moved, which is
exactly when nobody would notice it was the test rather than the law that changed.

Real registry data and the real loader throughout; the citations are verified
against the bundled consolidated law at load, so an ungrounded row cannot be read
at all.

See Also:
    :func:`~domain.iva.territorial_scope_for_country`
        The resolver the table overrides.
    :func:`~domain.iva.territorial_scope_for_spanish_postal_code`
        The sub-national rung the Spanish rows defer to.
"""

from __future__ import annotations

import pytest

from ..classification import IvaTerritorialScope
from ..establishment import (
    StatedCountryCodeStatus,
    stated_country_code_status,
    territorial_scope_for_country,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_monaco_is_not_a_third_country() -> None:
    """The defect the table exists to prevent, asserted on the side where it exempts."""
    assert territorial_scope_for_country("MC") is not IvaTerritorialScope.THIRD_COUNTRY


def test_monaco_resolves_exactly_as_france_does() -> None:
    """The assimilation as a pointer: agreement with the parent, not a literal.

    Pinning ``MC`` to the EU-member scope would pass identically today and would
    stop being about art. 3.Tres the moment France's own status was what moved.
    """
    assert territorial_scope_for_country("MC") == territorial_scope_for_country("FR")


def test_the_isle_of_man_resolves_exactly_as_the_united_kingdom_does() -> None:
    """The pointer's other end, and the one that has already survived a change.

    The Isle of Man was inside the Community until 2020 and is outside it now,
    with the row unchanged. That is only possible because the row never named a
    scope, and this is the assertion that holds it to it.
    """
    assert territorial_scope_for_country("IM") == territorial_scope_for_country("GB")


@pytest.mark.parametrize("code", ["AX", "GP", "MQ", "GF", "RE", "YT", "JE", "GG"])
def test_an_excluded_territory_is_a_third_territory(code: str) -> None:
    """Art. 3.Dos.1 excludes them and art. 3.Dos.3 then makes them third territories.

    Two readings of the same provision rather than an inference, which is why
    these carry a scope directly while the assimilations carry a pointer.
    """
    assert territorial_scope_for_country(code) is IvaTerritorialScope.THIRD_COUNTRY


@pytest.mark.parametrize("code", ["AX", "GP", "MQ", "GF", "RE", "YT"])
def test_an_excluded_territory_does_not_inherit_its_member_state(code: str) -> None:
    """The discriminating control: these sit inside Member States and must not follow them.

    Åland is Finnish and the five French territories are French, so a resolver
    reading membership before the carve-outs would answer every one of them
    ``EU_MEMBER`` -- the ordering the table depends on, asserted rather than
    assumed.
    """
    assert territorial_scope_for_country(code) is not IvaTerritorialScope.EU_MEMBER


@pytest.mark.parametrize("code", ["IC", "EA"])
def test_a_spanish_territory_code_establishes_nothing_and_is_not_a_gap(code: str) -> None:
    """Recognised, deliberately unresolved, and reported as neither garbage nor a gap.

    Both are excluded by art. 3.Dos.1 and would be defensible as third
    territories in tax terms. They are refused here anyway, because this codebase
    models them as their own scopes and the postal rung owns the sub-national
    evidence that picks between them -- so a third-country answer would be right
    about the tax and wrong about the model.

    The status half is the substantive gain: before the table, these read to an
    operator as codes this system does not carry, which invites somebody to
    "fix" the data. They are a decision, and now they say so.
    """
    assert territorial_scope_for_country(code) is None
    assert stated_country_code_status(code) is StatedCountryCodeStatus.CATALOGUED


@pytest.mark.parametrize("code", ["IC", "EA"])
def test_a_spanish_territory_code_never_yields_a_spanish_scope(code: str) -> None:
    """The module's founding refusal is not weakened by recognising these codes.

    Naming the territory is not the same as establishing it, and the temptation
    once ``IC`` is recognised is to answer ``ES_CANARIAS`` from it. The postal
    code is the evidence for that, and a country code that skipped it would be a
    second authority on the Spanish territories.
    """
    assert territorial_scope_for_country(code) not in {
        IvaTerritorialScope.ES_MAINLAND,
        IvaTerritorialScope.ES_CANARIAS,
        IvaTerritorialScope.ES_CEUTA_MELILLA,
    }


def test_the_carve_outs_do_not_disturb_the_ordinary_answers() -> None:
    """Anti-blast-radius: the override is narrow, and an override is not a rewrite.

    Without this, a carve-out consulted too eagerly -- or a table that captured
    more codes than it names -- would pass every case above while quietly
    changing what an ordinary Member State or third country establishes.
    """
    assert territorial_scope_for_country("FR") is IvaTerritorialScope.EU_MEMBER
    assert territorial_scope_for_country("FI") is IvaTerritorialScope.EU_MEMBER
    assert territorial_scope_for_country("US") is IvaTerritorialScope.THIRD_COUNTRY
    assert territorial_scope_for_country("ES") is None
