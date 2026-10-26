"""Merge a successor's keyed registry families with the declarations it inherits."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from pathlib import Path
from typing import Final

from cadrumo.domain.calculations.registry.cleared_families import cleared_family_names
from cadrumo.domain.calculations.registry.errors import RegistryLoadError
from cadrumo.domain.calculations.registry.keyed_families import (
    KeyedFamilySpec as _KeyedFamily,
)
from cadrumo.domain.calculations.registry.keyed_families import (
    inline_family_source_default,
)
from cadrumo.domain.calculations.registry.modelo_localization import as_toml_array
from dev.registry.compiler._toml_helpers import as_toml_table as _as_toml_table

from .casilla_identity import _casillas_by_id
from .keyed_family_identity import _member_identity, _refuse_undeclared_repurpose
from .keyed_family_period_scope import selector_covers
from .keyed_family_storage_delta import _apply_family_storage_delta

_CLEARED_FAMILIES_FIELD: Final = "cleared_families"
_RESTATED_FAMILIES_FIELD: Final = "restated_families"
_IDENTIFIER_EVOLUTIONS_SECTION: Final = "identifier_evolutions"


def _restated_families(successor: Mapping[str, object]) -> frozenset[str]:
    """Return the families ``successor`` declares it states in full on this edge.

    A declared family is not merged at all: the edition's stated array survives
    as authored, member for member and in stated order, because the claim is
    that the official structure the edition was drawn from lays the family out
    end to end. Inheriting there would carry members the successor's own
    document withdrew.

    Nothing is validated here. A malformed entry, a family name outside the
    merge vocabulary, an empty stated family, and a root edition claiming a
    restatement are all refused by the declaration's own typed validators, so a
    reading that recognises nothing simply merges as before and lets the
    edition be refused with the schema's error rather than a loader one.
    """
    entries = as_toml_array(successor.get(_RESTATED_FAMILIES_FIELD, ())) or ()
    declared: set[str] = set()
    for raw_entry in entries:
        entry = _as_toml_table(raw_entry)
        if entry is None:
            continue
        family = entry.get("family")
        if isinstance(family, str):
            declared.add(family)
    return frozenset(declared)


def _keyed_retirements(successor: Mapping[str, object], revision_id: str, family: _KeyedFamily) -> frozenset[str]:
    """Return the identifiers ``family`` withdraws from ``revision_id``.

    Both evolution kinds withdraw the identifier they name: ``retired`` ends it,
    and ``replaced`` ends it in favour of a successor member the edition states
    under the new identifier, so the old one must not also survive by
    inheritance.
    """
    evolutions = as_toml_array(successor.get(_IDENTIFIER_EVOLUTIONS_SECTION, ())) or ()
    retired: set[str] = set()
    for raw_evolution in evolutions:
        evolution = _as_toml_table(raw_evolution)
        if evolution is None or evolution.get("to_revision") != revision_id:
            continue
        if evolution.get("family") != family.section:
            continue
        identifier = evolution.get("identifier")
        if isinstance(identifier, str):
            retired.add(identifier)
    return frozenset(retired)


def inherit_keyed_family(
    context: str,
    *,
    revision_id: str,
    predecessor_id: str,
    predecessor: Mapping[str, object],
    family: _KeyedFamily,
    inherited: tuple[object, ...],
    inherited_casillas: tuple[object, ...],
    successor_casillas: tuple[object, ...],
    successor: Mapping[str, object],
) -> tuple[object, ...]:
    """Merge a predecessor's materialised members of one keyed family with the successor's stated ones.

    An inherited member is kept unless the successor states one carrying the
    same identity, which supersedes it in its position, or an evolution retires
    it. A stated member whose identity matches nothing inherited is new and is
    appended after the inherited members, in stated order. The resulting order
    is therefore the predecessor's order with supersessions in place and new
    members after, exactly as the casilla merge defines it.

    A period-scoped member whose own filing period the successor does not file
    is not inherited, whether the edge is a named predecessor or a storage
    baseline. A storage baseline reuses payload; it cannot make another
    period's deadline this edition's, and no valid tree could hold one, since
    the window would then be owned twice. The scope is judged after the
    edition's storage patches, so a member an override moves into the
    successor's period is kept.

    Refused, because each would otherwise resolve to a guess: a member carrying
    no identity at all, which cannot be superseded or inherited deterministically;
    two stated members sharing an identity, so neither can be said to supersede;
    two inherited members sharing one, so a stated member cannot say which it
    supersedes; and a stated member carrying an identity the same edition
    retires.
    """
    stated = _stated_members(context, family, successor)
    if stated is None:
        return ()
    inherited = tuple(_pin_family_source_default(member, predecessor, family) for member in inherited)
    inherited, removed, positions, patched = _apply_family_storage_delta(
        context, predecessor_id=predecessor_id, family=family, inherited=inherited, successor=successor
    )
    retired = _keyed_retirements(successor, revision_id, family) | removed
    inherited_casillas_by_id = _casillas_by_id(inherited_casillas)
    successor_casillas_by_id = _casillas_by_id(successor_casillas)
    superseders = _validated_superseders(context, family, stated, retired)
    _refuse_ambiguous_superseders(context, family, inherited, superseders)
    members, superseded = _inherit_members(
        context,
        family,
        inherited,
        successor,
        retired,
        superseders,
        patched,
        inherited_casillas_by_id,
        successor_casillas_by_id,
    )
    members.extend(member for member in stated if _member_identity(member, family) not in superseded)
    return _apply_family_positions(context, family, members, positions)


def _stated_members(context: str, family: _KeyedFamily, successor: Mapping[str, object]) -> tuple[object, ...] | None:
    if family.section in cleared_family_names(successor.get(_CLEARED_FAMILIES_FIELD, ())):
        if successor.get(family.section):
            raise RegistryLoadError(f"{context}: cleared family {family.section!r} also states members")
        return None
    raw = successor.get(family.section)
    stated = _parse_stated_members(raw, family)
    if stated is None:
        expected = "a table" if family.singleton else "an array"
        raise RegistryLoadError(f"{context}: {family.section} must be {expected}")
    return stated


def _parse_stated_members(raw: object, family: _KeyedFamily) -> tuple[object, ...] | None:
    if family.singleton:
        table = _as_toml_table(raw)
        return () if raw is None else (table,) if table is not None else None
    return as_toml_array(raw if raw is not None else ())


def _validated_superseders(
    context: str,
    family: _KeyedFamily,
    stated: tuple[object, ...],
    retired: frozenset[str],
) -> dict[str, object]:
    superseders: dict[str, object] = {}
    for member in stated:
        identity = _member_identity(member, family)
        if identity is None:
            raise RegistryLoadError(
                f"{context}: states a {family.section} member carrying no {family.identity!r}, so it can neither "
                "supersede an inherited member nor be superseded by a later edition",
            )
        if identity in retired:
            raise RegistryLoadError(
                f"{context}: states {family.section} {identity!r}, which the same edition retires",
            )
        if identity in superseders:
            raise RegistryLoadError(
                f"{context}: states more than one {family.section} member with {family.identity} {identity!r}, "
                "so neither can supersede the inherited member",
            )
        superseders[identity] = member
    return superseders


def _refuse_ambiguous_superseders(
    context: str,
    family: _KeyedFamily,
    inherited: tuple[object, ...],
    superseders: Mapping[str, object],
) -> None:
    counts = Counter(identity for member in inherited if (identity := _member_identity(member, family)) is not None)
    ambiguous = sorted(identity for identity in superseders if counts[identity] > 1)
    if ambiguous:
        raise RegistryLoadError(
            f"{context}: the predecessor carries {family.section} {family.identity} {ambiguous!r} on more than "
            "one member, so a stated member carrying it cannot say which one it supersedes",
        )


def _inherit_members(
    context: str,
    family: _KeyedFamily,
    inherited: tuple[object, ...],
    successor: Mapping[str, object],
    retired: frozenset[str],
    superseders: Mapping[str, object],
    patched: frozenset[str],
    inherited_casillas_by_id: Mapping[str, tuple[object, ...]],
    successor_casillas_by_id: Mapping[str, tuple[object, ...]],
) -> tuple[list[object], set[str]]:
    members: list[object] = []
    superseded: set[str] = set()
    for member in inherited:
        keep, replacement, superseded_identity = _inherited_member(
            context,
            family,
            member,
            successor,
            retired,
            superseders,
            patched,
            inherited_casillas_by_id,
            successor_casillas_by_id,
        )
        if keep:
            members.append(replacement)
        if superseded_identity is not None:
            superseded.add(superseded_identity)
    return members, superseded


def _inherited_member(
    context: str,
    family: _KeyedFamily,
    member: object,
    successor: Mapping[str, object],
    retired: frozenset[str],
    superseders: Mapping[str, object],
    patched: frozenset[str],
    inherited_casillas_by_id: Mapping[str, tuple[object, ...]],
    successor_casillas_by_id: Mapping[str, tuple[object, ...]],
) -> tuple[bool, object, str | None]:
    identity = _member_identity(member, family)
    if identity is None:
        raise RegistryLoadError(
            f"{context}: the predecessor carries a {family.section} member with no {family.identity!r}, so it "
            "cannot be inherited deterministically",
        )
    if identity in retired:
        return False, member, None
    if family.period_scoped and not selector_covers(successor.get("period_selector"), member):
        return False, member, None
    stated = superseders.get(identity)
    if stated is not None:
        if identity not in patched:
            _refuse_undeclared_repurpose(
                context,
                family,
                identity,
                member,
                stated,
                inherited_casillas_by_id=inherited_casillas_by_id,
                successor_casillas_by_id=successor_casillas_by_id,
            )
        return True, stated, identity
    if identity not in patched:
        # Even an omitted declaration is interpreted against successor casillas.
        _refuse_undeclared_repurpose(
            context,
            family,
            identity,
            member,
            member,
            inherited_casillas_by_id=inherited_casillas_by_id,
            successor_casillas_by_id=successor_casillas_by_id,
        )
    return True, member, None


def _apply_family_positions(
    context: str,
    family: _KeyedFamily,
    members: list[object],
    positions: tuple[tuple[str, int], ...],
) -> tuple[object, ...]:
    if not positions:
        return tuple(members)
    by_identity = {_member_identity(member, family): member for member in members}
    for identity, position in positions:
        member = by_identity.get(identity)
        if member is None:
            raise RegistryLoadError(f"{context}: family position names missing {family.section} {identity!r}")
        members.remove(member)
        members.insert(min(position, len(members)), member)
    return tuple(members)


def _pin_family_source_default(member: object, predecessor: Mapping[str, object], family: _KeyedFamily) -> object:
    """Keep an inherited member bound to the source default effective at its origin."""
    table = _as_toml_table(member)
    if table is None:
        return member
    pinned = inline_family_source_default(table, predecessor, family.source_default_key)
    return member if pinned is table else pinned


def _refuse_undecided_scoped_family(
    context: str,
    *,
    family: _KeyedFamily,
    inherited: tuple[object, ...],
    stated: tuple[object, ...],
    declined: frozenset[str],
) -> None:
    """Refuse silence that would leave a scoped family empty on both sides of an edge.

    A scoped family is asserted per edition, so an edition that does not name
    it in ``scoped_families`` takes none of its predecessor's members. That is
    the ordinary full-copy case and decides nothing while the edition states
    the family itself, or while the predecessor carries none either.

    The one case it does decide is a predecessor that carries members against
    an edition that states none: the family goes empty, and it goes empty
    through an absent word rather than a declaration. Every family paired with
    it by a closure rule inherits as usual, so the edition keeps the
    capability link - the ``export`` surface over no export layout - and loses
    only what backs it. Declining is available and explicit: naming the family
    in ``cleared_families`` says the edition takes nothing from its
    predecessor, and says it where a reader looks.
    """
    if not inherited or stated or family.section in declined:
        return
    raise RegistryLoadError(
        f"{context}: the predecessor declares {len(inherited)} {family.section} member(s), this edition states "
        f"none, and it neither asserts {family.section!r} in scoped_families nor declines it in "
        "cleared_families; a scoped family is asserted per edition, so silence here would leave the family "
        "empty with nothing recording the decision",
    )


def _raw_keyed_members(
    source_path: Path,
    revision_id: str,
    table: Mapping[str, object],
    family: _KeyedFamily,
) -> tuple[object, ...]:
    raw = table.get(family.section)
    if family.singleton:
        if raw is None:
            return ()
        member = _as_toml_table(raw)
        if member is None:
            raise RegistryLoadError(f"{source_path}: revision {revision_id!r} {family.section} must be a table")
        return (member,)
    members = as_toml_array(raw if raw is not None else ())
    if members is None:
        raise RegistryLoadError(f"{source_path}: revision {revision_id!r} {family.section} must be an array")
    return members
