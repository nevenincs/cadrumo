"""Resolve printed country evidence to a party's territorial scope, or to nothing.

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

**Why a country NAME needs its own rung.** A code is printed only where a
NIF-IVA is printed. Everywhere else the country appears in an address block as a
name, in the document's own language -- "Alemania", "Deutschland", "Germany".
Asking a reading stage for the code would be asking it to translate, and
translation is inference. So the name is transcribed verbatim and matched
against a bounded vocabulary held as registry data, which is deterministic
lookup; the code that yields is then handed to the same country resolver, so
nothing about what a country ESTABLISHES is decided twice.

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

from ...core.identity import (
    NifIvaPrefix,
    iso_country_for_nif_iva_prefix,
    nif_iva_format_for_country,
    normalise_nif_iva,
)
from ...core.parsing import normalise_iso_3166_alpha2_jurisdiction
from ...core.resources import bundled_path
from ...core.text_fold import fold_diacritics
from ._classification import IvaTerritorialScope
from ._schema import EUMemberState

__all__ = [
    "SPAIN_COUNTRY_CODE",
    "country_code_for_printed_country_name",
    "country_code_for_printed_tax_identifier",
    "territorial_scope_for_country",
    "territorial_scope_for_printed_country_name",
    "territorial_scope_for_printed_tax_identifier",
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


def country_code_for_printed_tax_identifier(printed_identifier: str | None) -> str | None:
    """Return the alpha-2 code a printed tax IDENTIFIER names, or ``None``.

    The first rung of the establishment ladder. An intra-community VAT number
    leads with its Member State's VAT prefix, so a document printing
    ``DE811234567`` states a country in the one place a domestic invoice's
    address block often does not.

    **The prefix is matched against the closed VAT prefix vocabulary, and the
    body against that State's published VIES structure.** The prefix alone is
    not evidence: two leading letters occur in plenty of strings a reader might
    put in an identifier field, and ``FRANCISCO`` would otherwise place a party
    in France. Requiring the whole number to match the shape its own prefix
    claims makes the rung answer only where a real VAT number was printed.

    **A Spanish identifier contributes nothing here, by design.** ``ES`` is
    absent from the prefix vocabulary because Spanish identifiers are checksum
    identifiers rather than structural ones -- and, more deeply, because
    registration is not establishment: the non-resident ``N`` leader, the
    ``L``/``M`` identifiers and the ``X``/``Y``/``Z`` series all belong to
    parties registered in Spain and established elsewhere, and establishment for
    IVA is the sede de actividad económica (Ley 37/1992 arts. 69-70). So a
    Spanish-prefixed number is handed back to the ladder, where the printed
    address country -- a statement about WHERE the party is, not about where it
    is registered -- is what may name Spain and open the postal rung.

    Args:
        printed_identifier: The identifier as transcribed, or ``None``. Spacing
            and separator punctuation are normalised away, because an issuer
            prints ``BE 0123.456.789`` as readily as ``BE0123456789``.

    Returns:
        The ISO 3166-1 alpha-2 code -- ``GR`` for a Greek ``EL`` number, since
        the VAT prefix and the ISO code diverge there and every catalogue
        downstream is ISO-keyed -- or ``None`` when no VAT number was printed,
        the prefix names no Member State, or the body does not match the shape
        its prefix claims.
    """
    if printed_identifier is None:
        return None
    normalised = normalise_nif_iva(printed_identifier)
    if len(normalised) < _ALPHA2_LENGTH:
        return None
    candidate = normalised[:_ALPHA2_LENGTH]
    try:
        prefix = NifIvaPrefix(candidate)
    except ValueError:
        return None
    spec = nif_iva_format_for_country(prefix.value)
    if spec is None or not spec.pattern.match(normalised):
        return None
    return iso_country_for_nif_iva_prefix(prefix)


def territorial_scope_for_printed_tax_identifier(printed_identifier: str | None) -> IvaTerritorialScope | None:
    """Return the territorial scope a printed tax IDENTIFIER establishes.

    The identifier rung expressed against the same target every other rung
    resolves into, and deliberately a composition rather than a second rule set:
    :func:`country_code_for_printed_tax_identifier` answers "which country did
    the number name" and :func:`territorial_scope_for_country` stays the single
    authority on "what does that country establish".

    Args:
        printed_identifier: The identifier as transcribed, or ``None``.

    Returns:
        The scope the named country establishes, or ``None`` when no VAT number
        was recognised. Spain cannot arise here -- the prefix vocabulary excludes
        it -- so this rung never opens the Spanish territory question and never
        answers it.
    """
    return territorial_scope_for_country(country_code_for_printed_tax_identifier(printed_identifier))


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


def _normalise_printed_country_name(printed: str) -> str:
    """Return the form a printed country name is matched under.

    Three normalisations and no more. Case is folded because a document sets its
    address block in whatever typography it likes. Runs of whitespace collapse to
    one because a name broken across an address line arrives with the break in
    it. Combining accents are folded away because invoicing systems routinely
    print ASCII-only, so ``"Mexico"`` and ``"México"`` are the same printed name.

    Punctuation is deliberately NOT stripped: ``"EE.UU."`` is carried in the
    vocabulary with its stops, and squeezing punctuation generally would start
    matching strings that are not names.
    """
    return " ".join(fold_diacritics(printed.casefold()).split())


@lru_cache(maxsize=1)
def _country_codes_by_printed_name() -> dict[str, str]:
    """Return every vocabulary name, normalised, mapped to its alpha-2 code.

    Read from ``registry/aeat/iva/country_names.toml`` rather than written here,
    for the same reason the territory table is: a name vocabulary inlined in a
    feature module is unreviewable, and reviewability is the whole argument for
    it being data.

    Raises:
        IvaCatalogueError: When the bundled vocabulary cannot be read, names a
            malformed code, or maps one normalised name to two different
            countries. The last is the check that makes accent folding safe:
            folding is only sound while no two distinct countries fold together,
            and this refuses the table rather than resolving the collision to
            whichever record happened to be read last.
    """
    from ._errors import IvaCatalogueError

    target = bundled_path("registry", "aeat", "iva", "country_names.toml")
    try:
        payload = tomllib.loads(target.read_text(encoding="utf-8"))
    except OSError as exc:
        raise IvaCatalogueError(f"{target}: cannot read the country-name vocabulary: {exc}") from exc
    except tomllib.TOMLDecodeError as exc:
        raise IvaCatalogueError(f"{target}: malformed country-name vocabulary: {exc}") from exc
    return _index_country_names(payload, source=str(target))


def _index_country_names(payload: object, *, source: str) -> dict[str, str]:
    """Index an already-parsed vocabulary payload, refusing an unusable one.

    Split from the read so the refusals are reachable with a payload rather than
    only with a file: the collision refusal is the one that makes accent folding
    sound, and a check that can only be exercised against the bundled table is a
    check nothing proves.

    Args:
        payload: The parsed TOML document.
        source: What to name in a diagnostic -- the bundled path in production.

    Returns:
        Each normalised printed name mapped to its alpha-2 code.

    Raises:
        IvaCatalogueError: When a record names no alpha-2 code, carries no
            printed name, carries a blank one, when two DIFFERENT countries
            claim one normalised name, or when the vocabulary is empty.
    """
    from ._errors import IvaCatalogueError

    target = source
    if not isinstance(payload, dict):
        raise IvaCatalogueError(f"{target}: the country-name vocabulary is not a table")

    resolved: dict[str, str] = {}
    for record in payload.get("country", ()):
        code = str(record.get("code", "")).strip().upper()
        if len(code) != _ALPHA2_LENGTH or not code.isalpha():
            raise IvaCatalogueError(f"{target}: country record names no alpha-2 code: {record!r}")
        names = record.get("names", ())
        if not names:
            raise IvaCatalogueError(f"{target}: country {code} carries no printed name")
        for name in names:
            normalised = _normalise_printed_country_name(str(name))
            if not normalised:
                raise IvaCatalogueError(f"{target}: country {code} carries a blank printed name")
            claimed = resolved.get(normalised)
            if claimed is not None and claimed != code:
                raise IvaCatalogueError(
                    f"{target}: the printed name {name!r} normalises to {normalised!r}, which both "
                    f"{claimed} and {code} claim; a name that cannot name one country cannot establish one",
                )
            resolved[normalised] = code
    if not resolved:
        raise IvaCatalogueError(f"{target}: the country-name vocabulary is empty")
    return resolved


def country_code_for_printed_country_name(printed_name: str | None) -> str | None:
    """Return the alpha-2 code a printed country NAME establishes, or ``None``.

    The second rung of the establishment ladder, and the reason it exists: a
    country prints as a name in the document's own language -- "Alemania",
    "Deutschland", "Germany" -- so asking a reader for ``DE`` would be a
    translation, and translation is inference. Transcribing the name verbatim and
    matching it against this closed vocabulary is a deterministic lookup instead,
    the same shape as matching a transcribed regime mención against the closed
    statutory vocabulary.

    Matching is EXACT after normalisation, not containment. A country name is a
    field value rather than a phrase inside prose, and containment over country
    names is actively wrong: ``"Niger"`` is contained in ``"Nigeria"`` and
    ``"Guinea"`` in ``"Papua New Guinea"``, so a containment match would place a
    party in the wrong tax territory from a correctly printed name. A near miss
    is not a match here.

    Args:
        printed_name: The country name transcribed from the document, or
            ``None``. Case, surrounding and repeated whitespace, and combining
            accents are normalised away; nothing else is.

    Returns:
        The upper-case ISO 3166-1 alpha-2 code, or ``None`` when the name is
        absent, blank, or not in the vocabulary.

        ``None`` NEVER degrades to a country and above all never to Spain. The
        peninsula is the majority population, so a domestic default would be
        invisible in testing while silently placing foreign parties inside the
        territorio de aplicación del impuesto. An unrecognised name is handed
        back to the ladder, which exhausts to an unknown scope and asks the
        operator.

    Raises:
        IvaCatalogueError: When the bundled vocabulary cannot be read.
    """
    if printed_name is None:
        return None
    candidate = _normalise_printed_country_name(printed_name)
    if not candidate:
        return None
    return _country_codes_by_printed_name().get(candidate)


def territorial_scope_for_printed_country_name(printed_name: str | None) -> IvaTerritorialScope | None:
    """Return the territorial scope a printed country NAME establishes.

    The name rung expressed against the same target the other rungs resolve
    into. It is deliberately a composition rather than a second rule set:
    :func:`country_code_for_printed_country_name` answers "which country was
    printed" and :func:`territorial_scope_for_country` stays the single authority
    on "what does that country establish", so a change to either question is made
    in one place.

    Args:
        printed_name: The country name transcribed from the document, or
            ``None``.

    Returns:
        The scope the named country establishes, or ``None`` when no name was
        recognised OR when the recognised country is Spain -- the country axis
        returns nothing for Spain by design, because ``ES`` names the Member
        State while the IVA territory inside it stays undetermined. A caller that
        needs the Spanish territory resolves it from the postal code.

    Raises:
        IvaCatalogueError: When the bundled vocabulary cannot be read.
    """
    return territorial_scope_for_country(country_code_for_printed_country_name(printed_name))
