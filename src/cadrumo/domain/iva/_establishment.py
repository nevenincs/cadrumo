"""Resolve a printed country code to a party's territorial scope, or to nothing.

The IVA treatment of a business invoice turns on WHERE each party is established,
so a reading pipeline that recovers amounts but not places cannot answer the
question the operation actually poses. The only country signal a read document
carries is printed: the two-letter prefix on a NIF-IVA, or the country stated in a
party's address. This module turns that printed evidence into the closed
:class:`IvaTerritorialScope` the classifier consumes -- or into ``None``, which is
the answer far more often than it looks.

**Absence is modelled as ``None``, never as an enum member.** A missing scope is
not a kind of scope, and adding an ``UNKNOWN`` member would put a value into a
closed set that every consumer's rule table would then have to special-case. The
optional type says the same thing where the type checker can enforce it.

**A wrong establishment is worse than an absent one, and it is worse in a
specific direction.** Resolving an unrecognised or unstated country to the
domestic scope silently converts an intra-community or reverse-charge operation
into a domestic one -- a value that is plausible at every boundary it crosses and
wrong only against the counterparty's own declaration. That is the
restrictive-default shape this codebase has been bitten by before, so the rule
here is strict: this module NEVER returns a Spanish scope.

**Why "ES" resolves to ``None`` rather than to the mainland.** This is the
substantive limit, not a caution. ``ES`` names the Member State, and Spain
contains three different IVA territories: the peninsula and Balearics inside the
territorio de aplicación del impuesto, the Canary Islands under IGIC, and Ceuta
and Melilla under IPSI -- the latter two outside LIVA entirely (Ley 37/1992 art.
3.Dos). A country code cannot distinguish them, so resolving ``ES`` to
:attr:`IvaTerritorialScope.ES_MAINLAND` would place every Canarian and Ceutan
party inside a territory their operations are not subject to, which is exactly
the silent domestic capture above. Discriminating them needs sub-national printed
evidence -- the address province or postal code -- which this module does not
receive and does not guess at.

So the honest reading of a Spanish prefix is "Spain, territory undetermined", and
the honest return for it is ``None``.

See Also:
    :class:`IvaTerritorialScope`
        The closed target this resolves into.
    :class:`EUMemberState`
        The Member State catalogue the EU branch is derived from.
"""

from __future__ import annotations

import tomllib
from functools import lru_cache
from typing import Final

from ...core.parsing import normalise_iso_3166_alpha2_jurisdiction
from ...core.resources import bundled_path
from ._classification import IvaTerritorialScope
from ._schema import EUMemberState

__all__ = [
    "SPAIN_COUNTRY_CODE",
    "territorial_scope_for_country",
    "territorial_scope_for_spanish_postal_code",
]

_ALPHA2_LENGTH: Final[int] = 2

SPAIN_COUNTRY_CODE: Final[str] = "ES"
"""The one code this module deliberately refuses to resolve.

Named rather than inlined because two things depend on agreeing about it: the
resolver's refusal, and the gate that proves the refusal holds. A literal spelled
twice is the drift this codebase keeps closing.
"""

_EU_MEMBER_CODES: Final[frozenset[str]] = frozenset(
    member.value.upper() for member in EUMemberState if member.value.upper() != SPAIN_COUNTRY_CODE
)
"""Every Member State code except Spain, derived from the closed catalogue.

Derived rather than listed so a State entering or leaving the catalogue moves
here with it -- a hand-written copy of this set once shipped covering half a
taxonomy elsewhere in this tree. Northern Ireland (``XI``) is a member of that
catalogue for goods under the Protocol and is deliberately not special-cased out:
the catalogue is the authority on who is inside, and second-guessing it here
would be a second opinion with no provision behind it.
"""


def territorial_scope_for_country(country_code: str | None) -> IvaTerritorialScope | None:
    """Return the territorial scope a printed country code establishes.

    Args:
        country_code: An ISO 3166-1 alpha-2 code as printed -- a NIF-IVA prefix or
            an address country. Surrounding whitespace and letter case are
            normalised here, because a document prints what it prints; anything
            that is not then a well-formed alpha-2 code is treated as ABSENT
            rather than coerced or refused.

            Absent rather than refused is the deliberate half. The core
            jurisdiction validator raises on malformed input, which is right for
            a configured value an operator supplied and wrong for a transcription
            of whatever a supplier chose to print: unreadable evidence is a
            normal outcome of reading, not an error condition. The shape is
            therefore checked before that validator is consulted, so the
            validator stays the single authority on what a well-formed code is
            without an exception being used for ordinary control flow.

    Returns:
        :attr:`IvaTerritorialScope.EU_MEMBER` for a Member State other than Spain,
        :attr:`IvaTerritorialScope.THIRD_COUNTRY` for a well-formed code outside
        the catalogue, or ``None`` when the code is absent, malformed, or Spanish.

        ``None`` is returned for Spain BY DESIGN, not as a gap: the code names the
        State while the IVA territory inside it stays undetermined, and the three
        Spanish territories are treated differently by law. A caller needing the
        Spanish scope must resolve it from sub-national evidence.
    """
    if country_code is None:
        return None
    candidate = country_code.strip().upper()
    if len(candidate) != _ALPHA2_LENGTH or not candidate.isalpha():
        return None
    normalised = normalise_iso_3166_alpha2_jurisdiction(candidate)
    if normalised is None:
        return None
    if normalised == SPAIN_COUNTRY_CODE:
        return None
    if normalised in _EU_MEMBER_CODES:
        return IvaTerritorialScope.EU_MEMBER
    return IvaTerritorialScope.THIRD_COUNTRY


_POSTAL_PREFIX_LENGTH: Final[int] = 2
_POSTAL_CODE_LENGTH: Final[int] = 5


@lru_cache(maxsize=1)
def _excluded_territories_by_prefix() -> dict[str, IvaTerritorialScope]:
    """Return the postal prefixes that name a territory OUTSIDE the TAI.

    Read from ``registry/aeat/iva/territories.toml`` rather than written here,
    because a territorial boundary is regulatory data versioned like every other
    value in that tree -- and because a mapping inlined in a feature module is
    the least-audited place for one to go stale.

    Only the EXCLUDED territories are enumerated, so a prefix absent from the
    table is inside the TAI. Enumerating the rest would be a second copy of the
    Spanish province list, maintained for no purpose.

    Returns:
        Each excluded prefix mapped to its scope.

    Raises:
        IvaCatalogueError: When the bundled table cannot be read or names a
            scope outside the closed set.
    """
    from ._errors import IvaCatalogueError

    target = bundled_path("registry", "aeat", "iva", "territories.toml")
    try:
        payload = tomllib.loads(target.read_text(encoding="utf-8"))
    except OSError as exc:
        raise IvaCatalogueError(f"{target}: cannot read the territory registry: {exc}") from exc
    except tomllib.TOMLDecodeError as exc:
        raise IvaCatalogueError(f"{target}: malformed territory registry: {exc}") from exc

    resolved: dict[str, IvaTerritorialScope] = {}
    for record in payload.get("territory", ()):
        try:
            scope = IvaTerritorialScope(record["scope"])
        except (KeyError, ValueError) as exc:
            raise IvaCatalogueError(f"{target}: territory record names no known scope: {record!r}") from exc
        for prefix in record.get("postal_prefixes", ()):
            resolved[str(prefix)] = scope
    if not resolved:
        raise IvaCatalogueError(f"{target}: the territory registry names no excluded territory")
    return resolved


def territorial_scope_for_spanish_postal_code(postal_code: str | None) -> IvaTerritorialScope | None:
    """Return the Spanish IVA territory a printed postal code establishes.

    The sub-national half of the establishment question, and the reason the
    country half returns nothing for Spain. The first two digits of a Spanish
    postal code are the province code, so this is a lookup against the excluded
    territories rather than an inference about them.

    Args:
        postal_code: The postal code as printed. Surrounding whitespace is
            normalised; anything that is not five digits is treated as absent
            rather than coerced, because a document prints what it prints and
            unreadable evidence is a normal outcome of reading.

    Returns:
        :attr:`IvaTerritorialScope.ES_CANARIAS` or
        :attr:`IvaTerritorialScope.ES_CEUTA_MELILLA` for a prefix the registry
        excludes, :attr:`IvaTerritorialScope.ES_MAINLAND` for a well-formed code
        outside those, or ``None`` when no code was readable.

        ``None`` rather than the mainland for an absent or malformed code, and
        that asymmetry is the whole safety property. The peninsula is the
        majority population, so a default would be invisible in testing and
        would silently place Canarian and Ceutan parties inside a territory
        their operations are not subject to -- the restrictive-provision-as-
        default failure, one level below the country axis that already refuses
        it.

    Raises:
        IvaCatalogueError: When the bundled territory registry cannot be read.
    """
    if postal_code is None:
        return None
    candidate = postal_code.strip()
    if len(candidate) != _POSTAL_CODE_LENGTH or not candidate.isdigit():
        return None
    excluded = _excluded_territories_by_prefix()
    return excluded.get(candidate[:_POSTAL_PREFIX_LENGTH], IvaTerritorialScope.ES_MAINLAND)
