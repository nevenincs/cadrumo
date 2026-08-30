"""Widening the country vocabulary must not admit a code that is not a third country.

The country resolver now matches a closed vocabulary rather than a code's shape,
and that vocabulary carries fifty-eight countries -- so a real jurisdiction
outside it refuses instead of resolving. Widening it is the obvious next move,
and the obvious way to widen it is the dangerous one: take an ISO 3166-1 register
or a CLDR territory list and admit every code in it.

**That would create a new silent zero-rating, in the same direction as the one
the narrowing closed.** The EU IVA territory is not the EU Member State set. The
Directive carves territories in and out of it (2006/112/EC arts. 5-7, mirrored
for Spain by Ley 37/1992 art. 3.Dos), and neither ISO nor CLDR encodes any of
that:

* Monaco is treated as FRANCE for IVA, so a Monegasque customer is an EU-member
  operation. Admitted from a plain ISO register it becomes a third country, and
  on the issued side that is export treatment -- exempt, on a supply that is not.
* ``IC`` and ``EA`` are exceptionally-reserved codes for the Canary Islands and
  for Ceuta y Melilla. Both are SPANISH, and this module's founding rule is that
  it never returns a Spanish scope from a country code because a code cannot tell
  the three Spanish territories apart. Admitting either as a third country would
  place a domestic party outside the EU.
* ``EU``, ``EZ`` and ``UN`` are in CLDR's territory list and name a union, a
  currency area and an organisation. None is a country and none can establish
  where a party is.
* ``GI`` is a territory rather than a state and levies no IVA at all, and
  ``XK`` sits in the ISO user-assigned range, so admitting it would make one
  code both catalogued and reserved. Both are named exclusions in the
  vocabulary's own header, and this is what holds them to it.

So this file is a tripwire rather than a description of current behaviour. Every
code below resolves to nothing TODAY because it is simply absent from the
vocabulary, and the assertions read as trivially satisfied for exactly that
reason. They stop being trivial the moment somebody widens: a bulk import from a
code register admits all of them at once, and this reds before the wrong scope
reaches a filing.

**What it deliberately does NOT assert** is that these codes resolve to nothing.
Monaco resolving to the EU-member scope would be CORRECT, and a gate pinned to
``None`` would refuse the right fix alongside the wrong one. The property is the
one that costs money: none of them is a third country.

See Also:
    :func:`~domain.iva.territorial_scope_for_country`
        The authority whose vocabulary a widening would change.
"""

from __future__ import annotations

import pytest

from ..classification import IvaTerritorialScope
from ..establishment import territorial_scope_for_country

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

#: Codes inside the EU IVA territory despite naming no Member State, or naming a
#: Spanish territory, or naming no country at all. Each is a code a general
#: register carries and a bulk widening would therefore admit.
NEVER_THIRD_COUNTRY = (
    "MC",  # Monaco: treated as France for IVA (Directive 2006/112/EC art. 7.1).
    "IC",  # Exceptionally reserved for the Canary Islands: Spanish.
    "EA",  # Exceptionally reserved for Ceuta y Melilla: Spanish.
    "EU",  # The Union itself. Not a country, and not somewhere a party is.
    "EZ",  # The euro area. A currency zone, not a jurisdiction.
    "UN",  # The United Nations. An organisation.
    "GI",  # Gibraltar: a territory rather than a state, and it levies no IVA.
    "XK",  # Kosovo: its code is user-assigned, so the axis reads it as denoting nothing.
)


@pytest.mark.parametrize("code", NEVER_THIRD_COUNTRY)
def test_a_widening_must_not_admit_this_code_as_a_third_country(code: str) -> None:
    """The tripwire. Trivially satisfied today; loud the moment it is not."""
    assert territorial_scope_for_country(code) is not IvaTerritorialScope.THIRD_COUNTRY


@pytest.mark.parametrize("code", NEVER_THIRD_COUNTRY)
def test_a_widening_must_not_admit_this_code_as_a_spanish_scope(code: str) -> None:
    """The other direction, for the two codes that really are Spanish.

    ``IC`` and ``EA`` name Spanish territories, so the tempting fix once they are
    noticed is to resolve them to the Canarian and Ceutan scopes. That is the one
    thing this module never does from a country code: it would make a foreign
    party printing a code it should not print into a domestic one, and the
    sub-national evidence -- the postal code -- is what separates the three
    Spanish territories.
    """
    assert territorial_scope_for_country(code) not in {
        IvaTerritorialScope.ES_MAINLAND,
        IvaTerritorialScope.ES_CANARIAS,
        IvaTerritorialScope.ES_CEUTA_MELILLA,
    }


def test_the_guard_would_notice_a_real_third_country() -> None:
    """Anti-vacuity: the resolver still ANSWERS, so the assertions above mean something.

    Without this, a resolver that had been broken shut -- returning ``None`` for
    every input -- would satisfy every case in this file, and the tripwire would
    be measuring nothing at all. The control is a catalogued third country, which
    must still reach the scope the cases above forbid.
    """
    assert territorial_scope_for_country("US") is IvaTerritorialScope.THIRD_COUNTRY
