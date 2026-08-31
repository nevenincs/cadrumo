"""Resolve printed country evidence to a party's territorial scope, or to nothing.

The IVA treatment of a business invoice turns on WHERE each party is established,
so a reading pipeline that recovers amounts but not places cannot answer the
question the operation actually poses. The only country signal a read document
carries is printed: the two-letter prefix on a NIF-IVA, or the country stated in a
party's address. This module turns that printed evidence into the closed
:class:`IvaTerritorialScope` the classifier consumes -- or into ``None``, which is
the answer far more often than it looks.

**A code establishes a territory only through the closed vocabulary.** Every rung
on this axis is a deterministic lookup against bounded registry data, and the
country rung is no exception: a code the catalogues do not carry is an unmatched
token that fires nothing. It was once a shape check instead, so any well-formed
pair resolved to :attr:`IvaTerritorialScope.THIRD_COUNTRY` -- and third country
on the issued side is export treatment, zero-rated, so ``XX``, ``ZZ`` and ``QQ``
exempted an operation silently from a value with no referent. The ISO
user-assigned ranges denote nothing by construction; shape-validity is not
reference. An unmatched token is reported rather than dropped, through
:func:`stated_country_code_status`, which separates the operator's typo from
this codebase's own catalogue gap.

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

**Why a STATED code needs one too, and why it is not just a wider length check.**
A machine-readable invoice does not print a name; it states a code, and the
syntaxes disagree about which code system. UBL states the alpha-2 form, Facturae
the alpha-3 form -- ``ESP`` where everything here is keyed ``ES``. Handed
straight to :func:`territorial_scope_for_country` that fails the shape test and
returns ``None``, which is indistinguishable from a document stating no country
at all: the evidence is present and parsed and establishes nothing. So the
correspondence is a column in the same registry vocabulary the names are matched
against, and :func:`country_code_for_stated_country_code` is the lookup against
it -- a bounded table, never a rule turning three letters into two.

See Also:
    :class:`IvaTerritorialScope`
        The closed target this resolves into.
    :class:`EUMemberState`
        The Member State catalogue the EU branch is derived from.
"""

from __future__ import annotations

import tomllib
from collections.abc import Mapping
from enum import StrEnum
from functools import lru_cache
from typing import Any, Final, NamedTuple, TypeGuard

from ...core.external_constants import UTF_8_ENCODING
from ...core.identity import (
    NifIvaPrefix,
    iso_country_for_nif_iva_prefix,
    nif_iva_format_for_country,
    normalise_nif_iva,
)
from ...core.parsing import normalise_iso_3166_alpha2_jurisdiction
from ...core.resources._boundary import bundled_path
from ...core.text_fold import fold_printed_phrase
from .classification import IvaTerritorialScope
from .schema import EUMemberState

__all__ = [
    "SPAIN_COUNTRY_CODE",
    "StatedCountryCodeStatus",
    "country_code_for_printed_country_name",
    "country_code_for_printed_tax_identifier",
    "country_code_for_stated_country_code",
    "record_country_code_status",
    "stated_country_code_status",
    "territorial_scope_for_country",
    "territorial_scope_for_printed_country_name",
    "territorial_scope_for_spanish_postal_code",
]

_ALPHA2_LENGTH: Final[int] = 2
_ALPHA3_LENGTH: Final[int] = 3

_ASCII_UPPERCASE: Final[str] = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"

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


_USER_ASSIGNED_ALPHA2: Final[frozenset[str]] = frozenset(
    {"AA", "ZZ"}
    | {f"Q{letter}" for letter in "MNOPQRSTUVWXYZ"}
    | {f"X{letter}" for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ"},
)
"""The alpha-2 pairs ISO 3166-1 reserves for private use: ``AA``, ``QM``-``QZ``,
``XA``-``XZ`` and ``ZZ``.

Written as ranges rather than a list because that is what the standard reserves,
and a hand-expanded copy would be a second statement of one rule. These pairs
denote no country BY CONSTRUCTION -- not "no country yet", the way an unallocated
code does, but "reserved so that no country will ever be allocated here". That is
what makes them the sharp end of the axis: a document stating one has stated a
string, and the honest report is a typo rather than a data gap.

``XI`` falls inside the reserved ``XA``-``XZ`` block and is nevertheless a member
of :class:`EUMemberState` for goods under the Protocol, which is exactly why
membership is asked BEFORE this set is consulted. A reader that checked the
ranges first would drop Northern Ireland out of the intra-community branch as a
placeholder.
"""


_USER_ASSIGNED_ALPHA3: Final[frozenset[str]] = frozenset(
    {f"AA{letter}" for letter in _ASCII_UPPERCASE}
    | {f"Q{first}{second}" for first in "MNOPQRSTUVWXYZ" for second in _ASCII_UPPERCASE}
    | {f"X{first}{second}" for first in _ASCII_UPPERCASE for second in _ASCII_UPPERCASE}
    | {f"ZZ{letter}" for letter in _ASCII_UPPERCASE},
)
"""The alpha-3 codes ISO 3166-1 reserves for private use: ``AAA``-``AAZ``,
``QMA``-``QZZ``, ``XAA``-``XZZ`` and ``ZZA``-``ZZZ``.

The alpha-3 counterpart of :data:`_USER_ASSIGNED_ALPHA2`, and it exists because
the record axis admits both spellings while only one of them was being judged.
``ZZ`` reported as the placeholder it is and ``ZZZ`` -- the same placeholder,
one letter longer -- reported as a jurisdiction our vocabulary might simply be
missing, which is the OPPOSITE operator instruction: go and enrol it. Enrolling
a reserved code in the country vocabulary would be ungrounded registry data.

That asymmetry lands on the format it can least afford. Facturae states the
country in alpha-3 and is the Spanish national format, so it is the spelling most
of this corpus arrives in; the alpha-2 half of the axis was gated and this half
was not.

Written as ranges for the same reason its sibling is: that is what the standard
reserves, and a hand-expanded list would be a second statement of one rule.
"""


class StatedCountryCodeStatus(StrEnum):
    """What a well-formed alpha-2 code IS, once the closed vocabulary is asked.

    The axis exists because the two ways a code can fail to name a country are
    different problems with different owners, and collapsing them would leave an
    operator unable to tell which they are looking at. It says nothing about
    what a country ESTABLISHES -- :func:`territorial_scope_for_country` stays
    the single authority on that -- and nothing about codes that are not
    well-formed alpha-2 pairs at all, which get no status.
    """

    CATALOGUED = "catalogued"
    """A bounded catalogue in this codebase names the code.

    The one status a rung can fire from. Spain is catalogued and still
    establishes no scope, which is a different refusal entirely: ``ES`` names
    the Member State while the IVA territory inside it stays undetermined.
    """

    UNASSIGNED = "unassigned"
    """The code is in an ISO user-assigned range, so it denotes nothing.

    The operator's typo signal. ``XX``, ``ZZ`` and ``QQ`` are the forms a
    placeholder, a truncated field or a slipped keystroke actually takes, and
    no catalogue anywhere will ever resolve them.
    """

    UNCATALOGUED = "uncatalogued"
    """The code may name a real jurisdiction the bundled vocabulary omits.

    A data gap somebody can close by adding the country, rather than a document
    defect. Reported as the weaker claim it is: the ranges above are the only
    codes this codebase can say denote nothing, so anything outside them that
    the vocabulary does not carry is reported as unknown to US rather than
    asserted to be meaningless. It fires no rung until the catalogue carries it.
    """


class _CarveOut(NamedTuple):
    """One territory whose treatment does not follow from its code alone.

    Exactly one of the three fields carries the disposition, which the loader
    enforces: a row that named two would be a territory the law treats two ways.

    Attributes:
        assimilated_to: The alpha-2 code this territory is treated AS, or
            ``None``. A pointer rather than a scope, because LIVA art. 3.Tres
            fixes what a territory is assimilated to and never what that parent
            establishes -- the Isle of Man followed the United Kingdom out of the
            Community without the article changing a word.
        scope: The scope the territory establishes directly, or ``None``. Used
            for the exclusions, where art. 3.Dos.1 puts the territory outside the
            interior del país and art. 3.Dos.3 then makes anything outside it a
            third territory.
        establishes_nothing: Whether the territory is recognised and its scope
            deliberately left to other evidence. The Spanish case: the code is
            known, and which of the three Spanish territories a party sits in is
            settled by the postal rung that owns the sub-national evidence.
    """

    assimilated_to: str | None
    scope: IvaTerritorialScope | None
    establishes_nothing: bool


@lru_cache(maxsize=1)
def _territory_carve_outs() -> dict[str, _CarveOut]:
    """Return every territory whose IVA treatment its country code does not give.

    Read from ``registry/aeat/iva/territory_carve_outs.toml`` and verified
    against the bundled consolidated law at load, on the same terms the territory
    table is: an ungrounded territorial rule must not be readable at all, because
    a rule asserted by a test ships to every caller and fails afterwards in a lane
    nobody is watching.

    Returns:
        Each alpha-2 code mapped to its disposition.

    Raises:
        IvaCatalogueError: When the bundled table cannot be read, names a code or
            a scope outside the closed sets, cites no provision, or gives a row
            anything other than exactly one disposition.
    """
    from .errors import IvaCatalogueError

    target = bundled_path("registry", "aeat", "iva", "territory_carve_outs.toml")
    try:
        payload = tomllib.loads(target.read_text(encoding=UTF_8_ENCODING))
    except OSError as exc:
        raise IvaCatalogueError(f"{target}: cannot read the carve-out table: {exc}") from exc
    except tomllib.TOMLDecodeError as exc:
        raise IvaCatalogueError(f"{target}: malformed carve-out table: {exc}") from exc
    return _carve_out_rows_from_payload(target, payload)


def _is_object_list(value: object) -> TypeGuard[list[object]]:
    """Narrow an unparameterized runtime list to untrusted object entries."""
    return isinstance(value, list)


def _is_str_keyed_mapping(value: object) -> TypeGuard[Mapping[str, object]]:
    """Narrow an unparameterized runtime dict to a string-keyed mapping.

    True by construction for a table parsed from TOML: ``tomllib`` always
    produces string keys.
    """
    return isinstance(value, dict)


def _str_tuple_or_none(value: object) -> tuple[str, ...] | None:
    """Validate a raw TOML array is entirely strings, returning it widened.

    Returns ``None`` when *value* is not a list, or when any entry is not a
    string, so the caller raises its own domain-specific refusal.
    """
    if not _is_object_list(value):
        return None
    widened: list[str] = []
    for item in value:
        if not isinstance(item, str):
            return None
        widened.append(item)
    return tuple(widened)


# KWARGS-ANY-RATIONALE-TOML-PAYLOAD: raw tomllib-parsed table; every value is
# refused inline by the shape checks below rather than trusted from the type.
def _carve_out_rows_from_payload(target: object, payload: Mapping[str, Any]) -> dict[str, _CarveOut]:
    """Return the carve-out rows a parsed table declares, refusing a malformed one.

    Every refusal the table can earn lives here rather than beside the file
    read, so the parsed payload is the whole input: reading the bundled file and
    judging what it says are separate jobs, and only the second can be exercised
    against a table that does not exist on disk.

    Args:
        target: The table being judged, named in every diagnostic.
        payload: The parsed table.

    Returns:
        Each alpha-2 code mapped to its disposition.

    Raises:
        IvaCatalogueError: When the table names a code or a scope outside the
            closed sets, cites no provision, gives a row anything other than
            exactly one disposition, carves a code out twice, points an
            assimilation at a parent no catalogue names, or closes an
            assimilation chain into a cycle.
    """
    from ._grounding import verify_table_legal_refs

    resolved: dict[str, _CarveOut] = {}
    citations: list[tuple[str, tuple[str, ...]]] = []
    for record in payload.get("carve_out", ()):
        code, carve_out, references = _carve_out_row(target, record, already_resolved=resolved)
        citations.append((code, references))
        resolved[code] = carve_out

    _refuse_empty_carve_out_table(target, resolved)
    _refuse_unresolvable_parents(target, resolved)
    _refuse_assimilation_cycles(target, resolved)

    verify_table_legal_refs(str(target), citations)
    return resolved


# KWARGS-ANY-RATIONALE-TOML-PAYLOAD: one raw tomllib-parsed row from the same table; shape-checked inline below.
def _carve_out_code(target: object, record: Mapping[str, Any], already_resolved: Mapping[str, _CarveOut]) -> str:
    """Return the row's alpha-2 code, refusing a malformed or repeated one."""
    from .errors import IvaCatalogueError

    code = str(record.get("code", "")).strip().upper()
    if len(code) != _ALPHA2_LENGTH or not code.isalpha():
        raise IvaCatalogueError(f"{target}: carve-out record names no alpha-2 code: {record!r}")
    if code in already_resolved:
        raise IvaCatalogueError(f"{target}: {code} is carved out twice; one territory cannot be treated two ways")
    return code


# KWARGS-ANY-RATIONALE-TOML-PAYLOAD: one raw tomllib-parsed row from the same table; shape-checked inline below.
def _carve_out_disposition(
    target: object,
    record: Mapping[str, Any],
    *,
    code: str,
) -> tuple[str | None, IvaTerritorialScope | None, bool]:
    """Return the row's single disposition: assimilation parent, scope, or nothing.

    Exactly one must be declared. A row naming none establishes nothing by
    accident, and a row naming two states the law twice.
    """
    from .errors import IvaCatalogueError

    assimilated = record.get("assimilated_to")
    raw_scope = record.get("scope")
    nothing = bool(record.get("establishes_nothing", False))
    declared = [field for field in (assimilated, raw_scope, nothing or None) if field is not None]
    if len(declared) != 1:
        raise IvaCatalogueError(
            f"{target}: carve-out {code} must declare exactly one of assimilated_to, scope or "
            f"establishes_nothing; a row naming none establishes nothing by accident and a row "
            f"naming two states the law twice",
        )

    scope: IvaTerritorialScope | None = None
    if raw_scope is not None:
        try:
            scope = IvaTerritorialScope(str(raw_scope))
        except ValueError as exc:
            raise IvaCatalogueError(f"{target}: carve-out {code} names no known scope: {raw_scope!r}") from exc

    parent: str | None = None
    if assimilated is not None:
        parent = str(assimilated).strip().upper()
        if len(parent) != _ALPHA2_LENGTH or not parent.isalpha():
            raise IvaCatalogueError(f"{target}: carve-out {code} is assimilated to no alpha-2 code: {assimilated!r}")
        if parent == code:
            raise IvaCatalogueError(f"{target}: carve-out {code} is assimilated to itself")
    return parent, scope, nothing


# KWARGS-ANY-RATIONALE-TOML-PAYLOAD: one raw tomllib-parsed row from the same table; shape-checked inline below.
def _carve_out_citations(target: object, record: Mapping[str, Any], *, code: str) -> tuple[str, ...]:
    """Return the row's legal_refs, refusing an uncited or malformed row.

    A territorial rule IS a regulatory value, so an uncited row is ungrounded
    rather than merely undocumented and must not load.
    """
    from .errors import IvaCatalogueError

    references = _str_tuple_or_none(record.get("legal_refs", ()))
    if references is None:
        raise IvaCatalogueError(f"{target}: carve-out {code} legal_refs must be an array of strings")
    if not references:
        raise IvaCatalogueError(f"{target}: carve-out {code} cites no provision establishing its treatment")
    return references


# KWARGS-ANY-RATIONALE-TOML-PAYLOAD: one raw tomllib-parsed row from the same table; shape-checked inline below.
def _carve_out_row(
    target: object,
    record: Mapping[str, Any],
    *,
    already_resolved: Mapping[str, _CarveOut],
) -> tuple[str, _CarveOut, tuple[str, ...]]:
    """Judge one carve-out row, returning its code, disposition and citations."""
    code = _carve_out_code(target, record, already_resolved)
    parent, scope, nothing = _carve_out_disposition(target, record, code=code)
    references = _carve_out_citations(target, record, code=code)
    return code, _CarveOut(assimilated_to=parent, scope=scope, establishes_nothing=nothing), references


def _refuse_empty_carve_out_table(target: object, resolved: Mapping[str, _CarveOut]) -> None:
    """Refuse a table that names no territory at all."""
    from .errors import IvaCatalogueError

    if not resolved:
        raise IvaCatalogueError(f"{target}: the carve-out table names no territory")


def _refuse_unresolvable_parents(target: object, resolved: dict[str, _CarveOut]) -> None:
    """Refuse an assimilation pointing at a code no catalogue names."""
    from .errors import IvaCatalogueError

    unresolvable = {row.assimilated_to for row in resolved.values() if row.assimilated_to} - _resolvable_parents(
        resolved
    )
    if unresolvable:
        raise IvaCatalogueError(
            f"{target}: assimilated to {', '.join(sorted(unresolvable))}, which no catalogue names; an "
            f"assimilation whose parent cannot be resolved establishes nothing while reading as a rule",
        )


def _refuse_assimilation_cycles(target: object, resolved: Mapping[str, _CarveOut]) -> None:
    """Refuse an assimilation chain that closes into a ring.

    Separate from the per-row self-pointer refusal because a chain is a
    property of the WHOLE table, which a per-record check cannot see. The
    self-pointer refusal is the length-one case of this one; both are kept, so
    the commonest mistake still earns the message that names it directly.
    """
    from .errors import IvaCatalogueError

    for start in resolved:
        seen = {start}
        step = resolved[start].assimilated_to
        while step is not None and step in resolved:
            if step in seen:
                raise IvaCatalogueError(
                    f"{target}: the assimilation chain from {start} closes into a cycle; a territory "
                    f"assimilated in a ring is treated AS nothing, and following the pointer to answer "
                    f"for it cannot terminate",
                )
            seen.add(step)
            step = resolved[step].assimilated_to


def _resolvable_parents(rows: dict[str, _CarveOut]) -> frozenset[str]:
    """Return the codes an assimilation may point at.

    Computed from the catalogues rather than from the carve-out table itself, so
    a row pointing at a country nothing can resolve is refused at load instead of
    silently establishing nothing at the call site. Carve-out codes are included
    because one territory being assimilated to another is representable, though
    nothing uses it today.
    """
    return frozenset(_country_codes_by_printed_name().values()) | _EU_MEMBER_CODES | {SPAIN_COUNTRY_CODE} | set(rows)


@lru_cache(maxsize=1)
def _catalogued_country_codes() -> frozenset[str]:
    """Return every alpha-2 code a bounded catalogue in this codebase names.

    The union of the catalogues that already exist, and deliberately not a new
    one: the printed-name vocabulary carries the countries a document's address
    block names, :class:`EUMemberState` carries the Member States the
    intra-community branch turns on, and the carve-out table carries the
    territories LIVA art. 3 treats differently from the country they sit in or
    beside. No two of them nest -- Northern Ireland is a Member State for goods
    with no address-block name, and Monaco is a carve-out that is neither -- so
    asking any one alone would silently drop a real jurisdiction out of the axis.

    Spain is added explicitly rather than left to fall out of either, because
    the resolver's refusal for ``ES`` must stay a deliberate territorial
    refusal and never become an unmatched-token one; the two are reported to the
    operator as different things.

    Returns:
        The catalogued codes.

    Raises:
        IvaCatalogueError: When the bundled vocabulary cannot be read or breaks
            its one-name-one-country invariant.
    """
    return (
        frozenset(_country_codes_by_printed_name().values())
        | _EU_MEMBER_CODES
        | {SPAIN_COUNTRY_CODE}
        | frozenset(_territory_carve_outs())
    )


def stated_country_code_status(stated_code: str | None) -> StatedCountryCodeStatus | None:
    """Return what a stated alpha-2 code is, or ``None`` when it is not one.

    The diagnostic half of the country axis. :func:`territorial_scope_for_country`
    answers "what does this establish" and returns ``None`` for every code
    outside the vocabulary; this answers "and why", so an unmatched token reaches
    the operator as a string they can correct rather than as a blank.

    Args:
        stated_code: The code as printed or as a structured record states it, or
            ``None``. Surrounding whitespace and letter case are normalised, the
            same way every other reader of this axis normalises them.

    Returns:
        The status, or ``None`` when nothing that could be an alpha-2 code was
        stated. A status is a statement ABOUT a code, so an absent field, a
        blank one and an address line that landed in the country slot get none:
        reporting those as unassigned countries would spend the operator's
        attention naming a string nobody claimed was a country.

    Raises:
        IvaCatalogueError: When the bundled vocabulary cannot be read.
    """
    if stated_code is None:
        return None
    candidate = stated_code.strip().upper()
    if len(candidate) != _ALPHA2_LENGTH or not candidate.isalpha():
        return None
    if candidate in _catalogued_country_codes():
        return StatedCountryCodeStatus.CATALOGUED
    if candidate in _USER_ASSIGNED_ALPHA2:
        return StatedCountryCodeStatus.UNASSIGNED
    return StatedCountryCodeStatus.UNCATALOGUED


def territorial_scope_for_country(country_code: str | None) -> IvaTerritorialScope | None:
    """Return the territorial scope a country code establishes, via the closed vocabulary.

    **The rung is a match against a bounded vocabulary, never a shape check.** A
    code this codebase's catalogues do not carry is an UNMATCHED TOKEN: it fires
    nothing, and the caller walks on or exhausts to an unknown scope. That is
    the substantive rule of this function, and it is stated here rather than at
    any one caller because every caller inherits it -- a resolver that answered
    on shape would hand the same wrong establishment to each of them.

    **Why shape is not enough, in the direction that costs money.** Any
    well-formed pair once resolved to
    :attr:`IvaTerritorialScope.THIRD_COUNTRY`, so ``XX``, ``ZZ`` and ``QQ``
    settled a party outside the EU -- and on the issued side third country is
    export treatment, zero-rated. An issuer typo, a placeholder or a truncated
    field therefore exempted an operation silently, from evidence the ladder
    treated as decisive. The ISO user-assigned ranges denote nothing by
    construction, so deriving a tax treatment from one derives it from a value
    with no referent: shape-validity is not reference, which is the same lesson
    a checksum-valid tax identifier of the wrong entity teaches one axis over.

    **Decisiveness does not depend on the outcome.** A code outside the
    vocabulary fires no rung whichever way the resulting treatment would fall.
    Making evidence count only when its consequence is unfavourable would invert
    the fact-to-derivation direction -- the caller would need the tax
    consequence before deciding whether the evidence exists -- and would leave a
    wrong third-country answer standing wherever the outcome happened to be the
    over-payment one, which nothing else in this codebase watches.

    Args:
        country_code: An ISO 3166-1 alpha-2 code as printed or as a structured
            record states it -- a NIF-IVA prefix or an address country.
            Surrounding whitespace and letter case are normalised here, because
            a document prints what it prints; anything that is not then a
            well-formed alpha-2 code is treated as ABSENT rather than coerced or
            refused.

            Absent rather than refused is the deliberate half. The core
            jurisdiction validator raises on malformed input, which is right for
            a configured value an operator supplied and wrong for a transcription
            of whatever a supplier chose to print: unreadable evidence is a
            normal outcome of reading, not an error condition. The shape is
            therefore checked before that validator is consulted, so the
            validator stays the single authority on what a well-formed code is
            without an exception being used for ordinary control flow.

    Returns:
        :attr:`IvaTerritorialScope.EU_MEMBER` for a Member State other than
        Spain, :attr:`IvaTerritorialScope.THIRD_COUNTRY` for a CATALOGUED
        country outside that catalogue, or ``None`` when the code is absent,
        malformed, Spanish, or names no country the vocabulary carries.

        ``None`` is returned for Spain BY DESIGN, not as a gap: the code names
        the State while the IVA territory inside it stays undetermined, and the
        three Spanish territories are treated differently by law. A caller
        needing the Spanish scope must resolve it from sub-national evidence.

        ``None`` for an unmatched token is not silence either. A caller that
        must tell an operator WHY nothing resolved asks
        :func:`stated_country_code_status`, which separates a code that denotes
        nothing from one this codebase simply does not carry yet.

    Raises:
        IvaCatalogueError: When the bundled vocabulary cannot be read or breaks
            its one-name-one-country invariant. Propagated rather than softened:
            a corrupt bundled table is a defect, not an unestablished party.
    """
    if country_code is None:
        return None
    candidate = country_code.strip().upper()
    if len(candidate) != _ALPHA2_LENGTH or not candidate.isalpha():
        return None
    normalised = normalise_iso_3166_alpha2_jurisdiction(candidate)
    if normalised is None:
        return None
    if normalised not in _catalogued_country_codes():
        return None
    # The carve-outs are consulted BEFORE the Member State branch, because that
    # is the only order that can be right: every one of them is a territory
    # whose treatment disagrees with the country it sits in or beside, so a
    # branch reading membership first would answer them all from the very
    # catalogue LIVA art. 3 overrides.
    carve_out = _territory_carve_outs().get(normalised)
    if carve_out is not None:
        if carve_out.establishes_nothing:
            return None
        if carve_out.scope is not None:
            return carve_out.scope
        # Assimilation is resolved by RE-ASKING this function for the parent
        # rather than by reading a scope off the row. The article fixes what a
        # territory is treated as and never what that parent establishes, so
        # following the pointer is what keeps the answer true as the parent's
        # own status changes -- the Isle of Man left the Community without this
        # row changing a word. The loader refuses a parent no catalogue names
        # and refuses a chain that closes into a cycle, of which a self-pointer
        # is the shortest, so this cannot recurse without end. The cycle walk is
        # what makes that true: excluding a self-pointer and an unknown parent
        # leaves a two-row ring admissible, and the parent kind the table admits
        # is exactly the kind that can form one.
        return territorial_scope_for_country(carve_out.assimilated_to)
    if normalised == SPAIN_COUNTRY_CODE:
        return None
    if normalised in _EU_MEMBER_CODES:
        return IvaTerritorialScope.EU_MEMBER
    return IvaTerritorialScope.THIRD_COUNTRY


def country_code_for_printed_tax_identifier(printed_identifier: str | None) -> str | None:
    """Return the alpha-2 code a printed tax IDENTIFIER names, or ``None``.

    The first rung of the establishment ladder. An intra-community IVA number
    leads with its Member State's IVA prefix, so a document printing
    ``DE811234567`` states a country in the one place a domestic invoice's
    address block often does not.

    **The prefix is matched against the closed IVA prefix vocabulary, and the
    body against that State's published VIES structure.** The prefix alone is
    not evidence: two leading letters occur in plenty of strings a reader might
    put in an identifier field, and ``FRANCISCO`` would otherwise place a party
    in France. Requiring the whole number to match the shape its own prefix
    claims makes the rung answer only where a real IVA number was printed.

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
        the IVA prefix and the ISO code diverge there and every catalogue
        downstream is ISO-keyed -- or ``None`` when no IVA number was printed,
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
        IvaCatalogueError: When the bundled table cannot be read, names a scope
            outside the closed set, or cites a provision that does not resolve
            to the bundled legal text it claims.
    """
    from ._grounding import verify_table_legal_refs
    from .errors import IvaCatalogueError

    target = bundled_path("registry", "aeat", "iva", "territories.toml")
    try:
        payload = tomllib.loads(target.read_text(encoding=UTF_8_ENCODING))
    except OSError as exc:
        raise IvaCatalogueError(f"{target}: cannot read the territory registry: {exc}") from exc
    except tomllib.TOMLDecodeError as exc:
        raise IvaCatalogueError(f"{target}: malformed territory registry: {exc}") from exc

    resolved: dict[str, IvaTerritorialScope] = {}
    citations: list[tuple[str, tuple[str, ...]]] = []
    for record in payload.get("territory", ()):
        try:
            scope = IvaTerritorialScope(record["scope"])
        except (KeyError, ValueError) as exc:
            raise IvaCatalogueError(f"{target}: territory record names no known scope: {record!r}") from exc
        references = _str_tuple_or_none(record.get("legal_refs", ()))
        if references is None:
            raise IvaCatalogueError(f"{target}: territory {scope.value} legal_refs must be an array of strings")
        # A territorial exclusion IS a regulatory value, so an uncited row is
        # ungrounded rather than merely undocumented and must not load.
        if not references:
            raise IvaCatalogueError(f"{target}: territory {scope.value} cites no provision establishing its exclusion")
        citations.append((scope.value, references))
        for prefix in record.get("postal_prefixes", ()):
            resolved[str(prefix)] = scope
    if not resolved:
        raise IvaCatalogueError(f"{target}: the territory registry names no excluded territory")
    verify_table_legal_refs(str(target), citations)
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
    return fold_printed_phrase(printed)


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
    return _index_country_names(_country_vocabulary_payload(), source=_country_vocabulary_source())


def _country_vocabulary_source() -> str:
    """Return the bundled vocabulary's path, for diagnostics."""
    return str(bundled_path("registry", "aeat", "iva", "country_names.toml"))


def _country_vocabulary_payload() -> object:
    """Return the parsed vocabulary document, refusing an unreadable one.

    Split from both indexers so the two columns are read from one file once and
    cannot drift onto different copies of it.

    Raises:
        IvaCatalogueError: When the bundled table cannot be read or parsed.
    """
    from .errors import IvaCatalogueError

    target = bundled_path("registry", "aeat", "iva", "country_names.toml")
    try:
        return tomllib.loads(target.read_text(encoding=UTF_8_ENCODING))
    except OSError as exc:
        raise IvaCatalogueError(f"{target}: cannot read the country-name vocabulary: {exc}") from exc
    except tomllib.TOMLDecodeError as exc:
        raise IvaCatalogueError(f"{target}: malformed country-name vocabulary: {exc}") from exc


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
    from .errors import IvaCatalogueError

    target = source
    if not _is_str_keyed_mapping(payload):
        raise IvaCatalogueError(f"{target}: the country-name vocabulary is not a table")

    countries = payload.get("country", ())
    if not _is_object_list(countries):
        raise IvaCatalogueError(f"{target}: the country-name vocabulary carries a malformed country table")

    resolved: dict[str, str] = {}
    for record in countries:
        code, names = _country_record_code_and_names(record, target=target)
        for name in names:
            _claim_printed_country_name(resolved, name, code=code, target=target)
    if not resolved:
        raise IvaCatalogueError(f"{target}: the country-name vocabulary is empty")
    return resolved


def _country_record_code_and_names(record: object, *, target: str) -> tuple[str, list[object]]:
    """Return one vocabulary record's alpha-2 code and printed names, refusing an unusable record.

    Raises:
        IvaCatalogueError: When the record is not a table, names no alpha-2
            code, or carries no printed name.
    """
    from .errors import IvaCatalogueError

    if not _is_str_keyed_mapping(record):
        raise IvaCatalogueError(f"{target}: country record is not a table: {record!r}")
    code = str(record.get("code", "")).strip().upper()
    if len(code) != _ALPHA2_LENGTH or not code.isalpha():
        raise IvaCatalogueError(f"{target}: country record names no alpha-2 code: {record!r}")
    names = record.get("names", ())
    if not _is_object_list(names) or not names:
        raise IvaCatalogueError(f"{target}: country {code} carries no printed name")
    return code, names


def _claim_printed_country_name(
    resolved: dict[str, str],
    name: object,
    *,
    code: str,
    target: str,
) -> None:
    """Bind one printed name to its country, refusing a blank name or a cross-country collision.

    Raises:
        IvaCatalogueError: When the name normalises to nothing, or when two
            DIFFERENT countries claim one normalised name.
    """
    from .errors import IvaCatalogueError

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


@lru_cache(maxsize=1)
def _country_codes_by_alpha3() -> dict[str, str]:
    """Return every vocabulary record's alpha-3 code mapped to its alpha-2 code.

    Read from the same ``registry/aeat/iva/country_names.toml`` the printed names
    are read from, and deliberately so: the alpha-3 form is a second way of
    STATING the country that record already names, so recording it anywhere else
    would put two authorities on one country.

    Raises:
        IvaCatalogueError: When the bundled vocabulary cannot be read or a record
            breaks the one-code-one-country invariant.
    """
    return _index_country_alpha3(_country_vocabulary_payload(), source=_country_vocabulary_source())


def _index_country_alpha3(payload: object, *, source: str) -> dict[str, str]:
    """Index the alpha-3 column, refusing a table that cannot mean one thing.

    Split from the read for the same reason the name indexer is: the refusals are
    what make the correspondence trustworthy, and a refusal reachable only
    through the bundled file is a refusal nothing proves.

    Three refusals, and each closes a way the table could load a contradiction:

    * A record carrying NO alpha-3 code. Required rather than optional, because
      an omission is indistinguishable at the call site from a country with no
      alpha-3 form: both yield nothing, and the caller reads that as "the
      document states no country" -- the silent blank this column exists to
      close.
    * Two records claiming ONE alpha-3 code. That code would then name two
      countries, and whichever record was read last would win silently.
    * One alpha-2 code claiming TWO alpha-3 codes, which is the same
      contradiction reached from the other side: a duplicated country record
      disagreeing with itself.

    Args:
        payload: The parsed TOML document.
        source: What to name in a diagnostic -- the bundled path in production.

    Returns:
        Each alpha-3 code mapped to the alpha-2 code naming the same country.

    Raises:
        IvaCatalogueError: On any of the three refusals above, on a malformed
            code in either column, or when the column is empty.
    """
    from .errors import IvaCatalogueError

    target = source
    if not _is_str_keyed_mapping(payload):
        raise IvaCatalogueError(f"{target}: the country-name vocabulary is not a table")

    countries = payload.get("country", ())
    if not _is_object_list(countries):
        raise IvaCatalogueError(f"{target}: the country-name vocabulary carries a malformed country table")

    resolved: dict[str, str] = {}
    alpha3_by_code: dict[str, str] = {}
    for record in countries:
        if not _is_str_keyed_mapping(record):
            raise IvaCatalogueError(f"{target}: country record is not a table: {record!r}")
        code = str(record.get("code", "")).strip().upper()
        if len(code) != _ALPHA2_LENGTH or not code.isalpha():
            raise IvaCatalogueError(f"{target}: country record names no alpha-2 code: {record!r}")
        alpha3 = str(record.get("alpha3", "")).strip().upper()
        if len(alpha3) != _ALPHA3_LENGTH or not alpha3.isalpha():
            raise IvaCatalogueError(
                f"{target}: country {code} names no alpha-3 code; the column is required, because an "
                f"absent correspondence reads downstream as a document stating no country at all",
            )
        claimed = resolved.get(alpha3)
        if claimed is not None and claimed != code:
            raise IvaCatalogueError(
                f"{target}: the alpha-3 code {alpha3!r} is claimed by both {claimed} and {code}; "
                f"a code that cannot name one country cannot establish one",
            )
        stated = alpha3_by_code.get(code)
        if stated is not None and stated != alpha3:
            raise IvaCatalogueError(
                f"{target}: country {code} states two different alpha-3 codes, {stated!r} and {alpha3!r}",
            )
        resolved[alpha3] = code
        alpha3_by_code[code] = alpha3
    if not resolved:
        raise IvaCatalogueError(f"{target}: the country-name vocabulary carries no alpha-3 correspondence")
    return resolved


def country_code_for_stated_country_code(stated_code: str | None) -> str | None:
    """Return the alpha-2 code a STRUCTURED record's country element states.

    The structured counterpart of :func:`country_code_for_printed_country_name`,
    and it exists for the mirror-image reason. A printed document states a
    country as a name; a machine-readable one states it as a code -- and the
    syntaxes disagree about which code system. UBL states the alpha-2 form
    (EN16931 BT-40 / BT-55); Facturae states the alpha-3 form, ``ESP`` where
    every country surface in this codebase is keyed ``ES``.

    **The failure this closes is silent, which is why it is a function rather
    than a widened length check.** An alpha-3 code handed to
    :func:`territorial_scope_for_country` fails its shape test and returns
    ``None``, indistinguishable from a document that stated no country -- so a
    Facturae invoice whose ``CountryCode`` element is present, read and parsed
    establishes nothing, and the postal rung gated on country evidence naming
    Spain stays shut for the entire Spanish national format.

    **The alpha-3 leg is a lookup against registry data, never a transformation.**
    The correspondence is a column in the bundled country vocabulary beside the
    alpha-2 code it names, so a code outside that bounded table yields ``None``
    exactly as an unlisted printed name does. There is no rule turning three
    letters into two.

    Args:
        stated_code: The country code as the record states it, in either code
            system, or ``None``. Surrounding whitespace and letter case are
            normalised, because the value is machine-produced but the case
            convention is the issuer's.

    Returns:
        The upper-case ISO 3166-1 alpha-2 code, or ``None`` when the element is
        absent, malformed, or states a code in either system that the closed
        vocabulary does not carry.

        **Both legs are equally bounded**, and that symmetry is the point rather
        than an implementation detail. A stated alpha-2 code is matched against
        the same closed vocabulary a printed one is, so a machine-readable
        document establishes exactly what the identical string printed in an
        address block establishes -- neither more nor less. A looser alpha-2 leg
        would let a UBL ``CountryCode`` of ``XX`` settle a party outside the EU
        while the printed form settled nothing, and the structured reader is
        precisely the surface that puts machine-stated strings in front of the
        rung.

        ``None`` NEVER degrades to a country and above all never to Spain, for
        the reason every other rung refuses to: the peninsula is the majority
        population, so a domestic default would be invisible in testing while
        placing foreign parties inside the territorio de aplicación del impuesto.

    Raises:
        IvaCatalogueError: When the bundled vocabulary cannot be read or breaks
            its one-code-one-country invariant. Propagated rather than softened:
            a corrupt bundled table is a defect, not an unestablished party.
    """
    if stated_code is None:
        return None
    candidate = stated_code.strip().upper()
    if not candidate.isalpha():
        return None
    if len(candidate) == _ALPHA2_LENGTH:
        # Already the target system, so this leg normalises and then asks the
        # same closed vocabulary the printed legs ask. The core jurisdiction
        # normaliser is a SHAPE authority rather than a membership one, so it
        # cannot be the last word here: on its own it passes `XX` through, and a
        # code with no referent then settles a territory downstream. Membership
        # is asked separately so the two questions stay separable and neither
        # authority is asked for the other's answer.
        normalised = normalise_iso_3166_alpha2_jurisdiction(candidate)
        if normalised is None or normalised not in _catalogued_country_codes():
            return None
        return normalised
    if len(candidate) == _ALPHA3_LENGTH:
        return _country_codes_by_alpha3().get(candidate)
    return None


def record_country_code_status(stated_code: str | None) -> StatedCountryCodeStatus | None:
    """Return what a country code a RECORD states is, in either ISO spelling.

    The structured sibling of :func:`stated_country_code_status`, and here for
    the reason that one exists at all: an unmatched token has to reach the caller
    as a string it can act on rather than as a blank. What differs is which
    spellings are admitted. That function is handed values read off a printed
    page, where the country slot may hold anything the reader found, so it
    answers only about alpha-2 and declines everything else -- correctly, because
    calling an address line a bad country code would spend an operator's
    attention naming a string nobody claimed was a country.

    A machine-readable record's country ELEMENT is not that. The schema has
    already said the token is a country code, and the formats disagree only about
    which spelling they state it in: EN16931 states alpha-2 (BT-40 / BT-55) and
    Facturae -- the Spanish national format, so the majority of this corpus --
    states alpha-3. So this admits both, exactly as
    :func:`country_code_for_stated_country_code` already does for the resolution
    question, and the two stay in step by construction because this asks that
    function first.

    Four answers, in the order the evidence narrows:

    * a token the bundled correspondence places -- ``ES``, ``ESP``, ``DEU`` --
      is ``CATALOGUED``;
    * an alpha-2 token keeps whatever :func:`stated_country_code_status` calls
      it, so the ISO user-assigned pairs stay the issuer's error and a real
      jurisdiction the vocabulary omits stays this codebase's own gap;
    * an alpha-3 token in the ISO user-assigned ranges is ``UNASSIGNED``, on
      exactly the terms its alpha-2 sibling is. Judged from
      :data:`_USER_ASSIGNED_ALPHA3` rather than from length, because the
      catch-all below would otherwise report ``ZZZ`` as a gap in our data while
      ``ZZ`` -- the same placeholder -- reports as the issuer's;
    * any other three-letter alphabetic token is ``UNCATALOGUED``. This is the
      answer the alpha-2 authority structurally cannot give: a three-letter
      string is outside its domain entirely.

    **The two failure kinds must stay apart, because they are opposite
    instructions.** A consumer sparing a declared relief on a catalogue gap and
    refusing it on an ISO-unassigned code depends on this distinction:
    collapsing them either rejects a legitimate export over a row nobody has
    written, or honours a relief claimed on a code with no referent. The same
    split decides whether the operator is sent to re-read the document or to
    enrol a country -- and enrolling a reserved code would be ungrounded
    registry data.

    **Any three-letter token in a country element is read as a country claim**,
    including one that is plainly something else -- ``EUR`` from a currency
    field, ``TOT`` from a totals row. That is deliberate rather than an
    oversight: the schema said this element holds a country code, so a token
    that is not one is a document defect worth naming, and the alternative is
    the silence this function exists to remove. It is the one place this axis is
    less cautious than its printed-value sibling, and it can afford to be
    because the element is typed.

    Args:
        stated_code: The token the record's country element carries, or ``None``.
            Surrounding whitespace and letter case are normalised, the way every
            reader of this axis normalises them.

    Returns:
        The status, or ``None`` when the element stated nothing -- absent or
        blank -- or stated something of no country-code shape at all. Absence is
        not a kind of failure.

    Raises:
        IvaCatalogueError: When the bundled vocabulary cannot be read.
    """
    if stated_code is None:
        return None
    candidate = stated_code.strip().upper()
    if not candidate:
        return None
    if country_code_for_stated_country_code(candidate) is not None:
        return StatedCountryCodeStatus.CATALOGUED
    alpha2_status = stated_country_code_status(candidate)
    if alpha2_status is not None:
        return alpha2_status
    if candidate in _USER_ASSIGNED_ALPHA3:
        # Asked BEFORE the catch-all below, or the reserved ranges fall through
        # it and are reported as a gap in OUR vocabulary. That is the opposite
        # instruction: it sends the operator to enrol a code ISO reserved so
        # that no country will ever be allocated to it.
        return StatedCountryCodeStatus.UNASSIGNED
    if len(candidate) == _ALPHA3_LENGTH and candidate.isalpha():
        return StatedCountryCodeStatus.UNCATALOGUED
    return None


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
