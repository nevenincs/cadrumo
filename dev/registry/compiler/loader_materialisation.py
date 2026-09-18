"""Development-only mutable-registry TOML compiler internals.

The loading contract lives in :mod:`loader`; the fragment merge, the numbered-
fragment grammar, the directory walk and the memoised load paths are here, so a
caller outside this package cannot bind to a compilation step or a cache the
contract does not promise.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from dataclasses import field as dataclass_field
from functools import lru_cache
from pathlib import Path
from typing import Final, cast

from pydantic import BaseModel, TypeAdapter, ValidationError

from cadrumo.core.directory_scan import (
    DirectoryEntryKind,
    scan_directory,
)
from cadrumo.core.toml import freeze_toml, read_toml
from cadrumo.domain.calculations.registry.cleared_families import cleared_family_names
from cadrumo.domain.calculations.registry.errors import (
    RegistryFailureClassification,
    RegistryFailureCondition,
    RegistryLoadError,
    RegistryValidationError,
)
from cadrumo.domain.calculations.registry.export_field_casilla import derive_casilla_export_refs
from cadrumo.domain.calculations.registry.ids import RevisionId
from cadrumo.domain.calculations.registry.keyed_families import (
    INHERITED_FAMILY_SPECS as _CANONICAL_INHERITED_FAMILY_SPECS,
)
from cadrumo.domain.calculations.registry.keyed_families import (
    KEYED_FAMILY_SPECS as _CANONICAL_KEYED_FAMILY_SPECS,
)
from cadrumo.domain.calculations.registry.keyed_families import (
    KeyedFamilySpec as _KeyedFamily,
)
from cadrumo.domain.calculations.registry.keyed_families import (
    family_identity_value as _family_identity_value,
)
from cadrumo.domain.calculations.registry.keyed_families import (
    family_source_default_fields,
    inline_family_source_default,
)
from cadrumo.domain.calculations.registry.lineage_attestation import (
    LineageAttestation,
    validate_lineage_attestations,
)
from cadrumo.domain.calculations.registry.modelo_localization import (
    ModeloLocalizationFieldKind,
    as_toml_array,
    casilla_occurrence_locale_key,
    enroll_revision_localization,
    modelo_locale_key,
)
from cadrumo.domain.calculations.registry.revision_contracts import validate_predecessor_forest
from cadrumo.domain.calculations.registry.runtime_graph import expression_casilla_refs
from cadrumo.domain.calculations.registry.schema import (
    REVISION_GOVERNANCE_FIELDS as _REVISION_GOVERNANCE_FIELDS,
)
from cadrumo.domain.calculations.registry.schema import (
    REVISION_MANIFEST_ONLY_FIELDS as _REVISION_MANIFEST_ONLY_FIELDS,
)
from cadrumo.domain.calculations.registry.schema import (
    CasillaFieldOverride,
    CasillaMemberPosition,
    CasillaMemberRemoval,
    FamilyFieldOverride,
    FamilyMemberPosition,
    FamilyMemberRemoval,
    ModeloDefinition,
    ModeloRevision,
    RegistryCatalogues,
    SociedadesAnnualManualCoverageCatalogue,
    SupportedFilingYearsCatalogue,
)
from cadrumo.domain.calculations.registry.schema_formula import FormulaExpression
from cadrumo.domain.calculations.registry.schema_references import LegalReference, SourceReference
from cadrumo.domain.calculations.registry.schema_surfaces import CasillaDefinition, CasillaEvolutionKind
from cadrumo.domain.calculations.registry.validate_revision_identity import revision_reference_identity_failures
from dev.registry.compiler.identifier_lineage import identifier_lineage

from ._loader_revision_fragments import (
    merge_revision_fragment as _merge_revision_fragment,
)
from ._loader_revision_fragments import (
    merge_revision_manifest as _merge_revision_manifest,
)
from ._loader_revision_fragments import (
    reject_local_catalogues as _reject_local_catalogues,
)
from ._toml_helpers import as_toml_table as _as_toml_table
from .loader_cache import (
    ModeloRevisionSource as _ModeloRevisionSource,
)
from .loader_cache import (
    toml_file_fingerprint,
)
from .loader_fingerprints import (
    clear_fingerprint_cache as _clear_fingerprint_cache,
)
from .loader_fingerprints import (
    collect_modelo_directory_fingerprints,
    collect_registry_tree_fingerprints,
)
from .loader_grammar import revision_section_fragment_paths
from .loader_semantics import compile_export_semantic_field, compile_projection_endpoint_declaration

_PREDECESSOR_FIELD: Final = "predecessor"
_CASILLA_STORAGE_BASELINE_FIELD: Final = "casilla_storage_baseline"
_FAMILY_STORAGE_BASELINE_FIELD: Final = "family_storage_baseline"
_RESTATED_FAMILIES_FIELD: Final = "restated_families"
_CLEARED_FAMILIES_FIELD: Final = "cleared_families"
_NO_PREDECESSOR_TABLE_KEY: Final = "none"
_INHERITED_SECTION: Final = "casillas"
_RETIREMENT_SECTION: Final = "casilla_continuidad_evolutions"
_IDENTIFIER_EVOLUTIONS_SECTION: Final = "identifier_evolutions"
_EDITION_SOURCE_DEFAULT_FIELD: Final = "casilla_source_refs"
#: The family sections that lift a shared ``source_refs`` onto the manifest the
#: same way casillas do, each with the manifest key that carries its default.
_EDITION_ORDEN_FIELD: Final = "orden_aplicabilidad"
_ROW_SOURCE_FIELD: Final = "source_refs"
_ROW_SOURCE_ADDITIONS_FIELD: Final = "additional_source_refs"
_ROW_LEGAL_FIELD: Final = "legal_refs"
_ROW_INHERITED_FROM_FIELD: Final = "inherited_from"
_ROW_LINEAGE_CLAIM_FIELDS: Final = frozenset({"continuidad_origin", "continuidad_evidence"})
#: Fields whose change can make the stating edition's label no longer the row's.
#: A storage patch touching none of them keeps the row's label origin.
_ROW_LABEL_IDENTITY_FIELDS: Final = frozenset({"id", "number", "continuidad_id"})


#: The families this loader inherits along a predecessor chain, beyond casillas.
#:
#: Enrolment is explicit rather than derived from ``collection_shaped_fields``,
#: because carrying a collection has nothing to do with whether inheriting it is
#: TRUE. A family is inheritable only when a member restated unchanged by a
#: successor means the same thing as the predecessor's member. A family whose
#: members are per-edition assertions about the edition that states them - the
#: completeness manifest's graded closure claim is the worked example - would
#: otherwise attest for the successor something nobody established, which is
#: what ``scoped`` answers: the successor carries such a family only when it
#: names the family in its own ``scoped_families``, so the claim is adopted by
#: the edition rather than arriving with it. Adding a family here, and choosing
#: whether it is scoped, is that judgement, made once and reviewed on its own,
#: not a consequence of the field existing.  The
#: immutable domain-owned table is the only family enrolment source so the
#: status and migration consumers cannot drift from this merge.
_KEYED_FAMILIES: Final[tuple[_KeyedFamily, ...]] = _CANONICAL_KEYED_FAMILY_SPECS


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
    storage_only: bool,
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

    Refused, because each would otherwise resolve to a guess: a member carrying
    no identity at all, which cannot be superseded or inherited deterministically;
    two stated members sharing an identity, so neither can be said to supersede;
    two inherited members sharing one, so a stated member cannot say which it
    supersedes; and a stated member carrying an identity the same edition
    retires.
    """
    if family.section in cleared_family_names(successor.get(_CLEARED_FAMILIES_FIELD, ())):
        if successor.get(family.section):
            raise RegistryLoadError(f"{context}: cleared family {family.section!r} also states members")
        return ()
    raw_stated = successor.get(family.section)
    if family.singleton:
        stated_table = _as_toml_table(raw_stated)
        stated = () if raw_stated is None else (stated_table,) if stated_table is not None else None
    else:
        stated = as_toml_array(raw_stated if raw_stated is not None else ())
    if stated is None:
        expected = "a table" if family.singleton else "an array"
        raise RegistryLoadError(f"{context}: {family.section} must be {expected}")
    inherited = tuple(_pin_family_source_default(member, predecessor, family) for member in inherited)
    inherited, removed, positions, patched = _apply_family_storage_delta(
        context, predecessor_id=predecessor_id, family=family, inherited=inherited, successor=successor
    )
    inherited_casillas_by_id = _casillas_by_id(inherited_casillas)
    successor_casillas_by_id = _casillas_by_id(successor_casillas)
    retired = _keyed_retirements(successor, revision_id, family) | removed
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
    inherited_counts = Counter(
        identity for member in inherited if (identity := _member_identity(member, family)) is not None
    )
    ambiguous = sorted(identity for identity in superseders if inherited_counts[identity] > 1)
    if ambiguous:
        raise RegistryLoadError(
            f"{context}: the predecessor carries {family.section} {family.identity} {ambiguous!r} on more than "
            "one member, so a stated member carrying it cannot say which one it supersedes",
        )
    members: list[object] = []
    superseded: set[str] = set()
    for member in inherited:
        identity = _member_identity(member, family)
        if identity is None:
            raise RegistryLoadError(
                f"{context}: the predecessor carries a {family.section} member with no {family.identity!r}, so it "
                "cannot be inherited deterministically",
            )
        if identity in retired:
            continue
        if family.period_scoped and not storage_only and not _selector_covers(successor.get("period_selector"), member):
            continue
        if identity in superseders:
            if identity not in patched:
                _refuse_undeclared_repurpose(
                    context,
                    family,
                    identity,
                    member,
                    superseders[identity],
                    inherited_casillas_by_id=inherited_casillas_by_id,
                    successor_casillas_by_id=successor_casillas_by_id,
                )
            members.append(superseders[identity])
            superseded.add(identity)
            continue
        # Even an omitted declaration is interpreted against the successor's
        # casillas. An unchanged target token can now identify a split child,
        # so inheritance needs the same identity guard as a supersession.
        if identity not in patched:
            _refuse_undeclared_repurpose(
                context,
                family,
                identity,
                member,
                member,
                inherited_casillas_by_id=inherited_casillas_by_id,
                successor_casillas_by_id=successor_casillas_by_id,
            )
        members.append(member)
    for member in stated:
        identity = _member_identity(member, family)
        if identity is not None and identity not in superseded:
            members.append(member)
    if positions:
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


def _patch_family_table(context: str, value: object, fields: Mapping[str, object], removed: tuple[str, ...]) -> object:
    table = _as_toml_table(value)
    if table is None:
        raise RegistryLoadError(f"{context}: selected family member is not a table")
    result: dict[str, object] = dict(table)
    for key, replacement in fields.items():
        if isinstance(replacement, Mapping) and isinstance(result.get(key), Mapping):
            result[key] = _patch_family_table(context, result[key], replacement, ())
        else:
            result[key] = replacement
    for path in removed:
        segments = path.split(".")
        target = result
        for segment in segments[:-1]:
            child = target.get(segment)
            if not isinstance(child, Mapping):
                raise RegistryLoadError(f"{context}: removed field {path!r} does not exist")
            copied = dict(child)
            target[segment] = copied
            target = copied
        if target.pop(segments[-1], None) is None:
            raise RegistryLoadError(f"{context}: removed field {path!r} does not exist")
    return result


def patch_family_sequences(
    context: str,
    value: object,
    additions: Mapping[str, tuple[object, ...]],
    removals: Mapping[str, tuple[int, ...]],
    orders: Mapping[str, tuple[int, ...]],
) -> object:
    table = _as_toml_table(value)
    if table is None:
        raise RegistryLoadError(f"{context}: selected family member is not a table")
    result: dict[str, object] = dict(table)
    for path in sorted(set(additions) | set(removals) | set(orders)):
        target = result
        segments = path.split(".")
        for segment in segments[:-1]:
            child = target.get(segment)
            if not isinstance(child, Mapping):
                raise RegistryLoadError(f"{context}: sequence field {path!r} does not exist")
            copied = dict(child)
            target[segment] = copied
            target = copied
        existing = target.get(segments[-1])
        if not isinstance(existing, list | tuple):
            raise RegistryLoadError(f"{context}: sequence field {path!r} is not a sequence")
        removed = set(removals.get(path, ()))
        if any(index >= len(existing) for index in removed):
            raise RegistryLoadError(f"{context}: sequence removal for {path!r} is out of range")
        patched = [item for index, item in enumerate(existing) if index not in removed]
        patched.extend(additions.get(path, ()))
        order = orders.get(path)
        if order is not None:
            if sorted(order) != list(range(len(patched))):
                raise RegistryLoadError(f"{context}: sequence order for {path!r} is not a permutation")
            patched = [patched[index] for index in order]
        target[segments[-1]] = tuple(patched)
    return result


def _apply_family_storage_delta(
    context: str,
    *,
    predecessor_id: str,
    family: _KeyedFamily,
    inherited: tuple[object, ...],
    successor: Mapping[str, object],
) -> tuple[tuple[object, ...], frozenset[str], tuple[tuple[str, int], ...], frozenset[str]]:
    """Apply the canonical field/removal/order delta to one keyed family."""
    if family.section in cleared_family_names(successor.get(_CLEARED_FAMILIES_FIELD, ())):
        return tuple(), frozenset[str](), tuple(), frozenset[str]()
    try:
        overrides = tuple(
            FamilyFieldOverride.model_validate(value)
            for value in (as_toml_array(successor.get("family_overrides", ())) or ())
            if isinstance(value, Mapping) and value.get("family") == family.section
        )
        removals = tuple(
            FamilyMemberRemoval.model_validate(value)
            for value in (as_toml_array(successor.get("family_removals", ())) or ())
            if isinstance(value, Mapping) and value.get("family") == family.section
        )
        positions = tuple(
            FamilyMemberPosition.model_validate(value)
            for value in (as_toml_array(successor.get("family_positions", ())) or ())
            if isinstance(value, Mapping) and value.get("family") == family.section
        )
    except ValidationError as exc:
        raise RegistryLoadError(f"{context}: invalid {family.section} storage delta: {exc}") from exc
    result = list(inherited)
    by_identity = {_member_identity(member, family): index for index, member in enumerate(result)}
    seen: set[str] = set()
    removed: set[str] = set()
    patched: set[str] = set()
    for declaration in removals:
        if str(declaration.selector.revision) != predecessor_id:
            raise RegistryLoadError(f"{context}: family removal baseline is not predecessor {predecessor_id!r}")
        identity = declaration.selector.id
        if identity not in by_identity or identity in seen:
            raise RegistryLoadError(f"{context}: family removal selector {identity!r} is missing or repeated")
        seen.add(identity)
        removed.add(identity)
    for declaration in overrides:
        if str(declaration.selector.revision) != predecessor_id:
            raise RegistryLoadError(f"{context}: family override baseline is not predecessor {predecessor_id!r}")
        identity = declaration.selector.id
        if identity not in by_identity or identity in seen:
            raise RegistryLoadError(f"{context}: family override selector {identity!r} is missing or repeated")
        seen.add(identity)
        index = by_identity[identity]
        result[index] = _patch_family_table(context, result[index], declaration.fields, declaration.removed_fields)
        result[index] = patch_family_sequences(
            context,
            result[index],
            declaration.sequence_additions,
            declaration.sequence_removals,
            declaration.sequence_order,
        )
        if declaration.replacement_id is not None:
            table = _as_toml_table(result[index])
            if table is None or family.identity is None:
                raise RegistryLoadError(f"{context}: family identity replacement selected a non-table member")
            result[index] = {**table, family.identity: declaration.replacement_id}
        patched.add(identity)
    return (
        tuple(result),
        frozenset(removed),
        tuple((item.id, item.position) for item in positions),
        frozenset(patched),
    )


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


def _refuse_undeclared_repurpose(
    context: str,
    family: _KeyedFamily,
    identity: str,
    inherited: object,
    stated: object,
    *,
    inherited_casillas_by_id: Mapping[str, tuple[object, ...]],
    successor_casillas_by_id: Mapping[str, tuple[object, ...]],
) -> None:
    """Refuse a supersession that changes what the member IS rather than what it declares.

    Superseding in place is the ordinary way an edition restates a member: the
    declaration changes and the identity carries. It is an undeclared repurpose
    when a field carrying the member's identity changes under the same id - a
    binding that changes its provider kind or value channel is no longer the
    same binding, whatever its id says. Reusing an id for a different thing
    makes every earlier edition's reference to it silently wrong, so it must be
    declared as a ``replaced`` evolution naming a new id instead.

    The identity-carrying fields are data on the family, not a branch per
    family, so enrolling a family states its identity fields in one place.
    """
    for path in family.identity_fields:
        before = _field_at(inherited, path)
        after = _field_at(stated, path)
        unchanged = (
            _same_casilla_identity(before, after, inherited_casillas_by_id, successor_casillas_by_id)
            if path in family.casilla_identity_fields
            else before == after
        )
        if not unchanged:
            raise RegistryLoadError(
                f"{context}: states {family.section} {identity!r} with {path} {after!r}, but the inherited member "
                f"carries {before!r}; a change to a field carrying the member's identity is a repurpose, not a "
                f"supersession, so declare it as a replaced evolution naming a new {family.identity}",
            )
    if family.section == "formulas":
        _refuse_reinterpreted_formula_operands(
            context, identity, inherited, stated, inherited_casillas_by_id, successor_casillas_by_id
        )


def _refuse_reinterpreted_formula_operands(
    context: str,
    identity: str,
    inherited: object,
    stated: object,
    inherited_casillas_by_id: Mapping[str, tuple[object, ...]],
    successor_casillas_by_id: Mapping[str, tuple[object, ...]],
) -> None:
    """An unchanged expression cannot silently read different fiscal concepts.

    Expressions are declarations, not immutable formula identity axes: an
    explicitly changed successor expression remains allowed. For an unchanged
    expression, walk the canonical typed tree so nested references receive the
    same protection as direct operands, without rewriting any reference.
    """
    before = FormulaExpression.model_validate(_field_at(inherited, "expression"))
    after = FormulaExpression.model_validate(_field_at(stated, "expression"))
    if before != after:
        return
    for reference in expression_casilla_refs(before):
        if not _same_casilla_identity(reference, reference, inherited_casillas_by_id, successor_casillas_by_id):
            raise RegistryLoadError(
                f"{context}: formulas {identity!r} inherits an unchanged expression whose casilla operand "
                f"{reference!r} no longer identifies the predecessor's concept; state the successor's "
                "expression explicitly with its intended references instead of silently carrying values",
            )


def _same_casilla_identity(
    before: object,
    after: object,
    inherited_by_id: Mapping[str, tuple[object, ...]],
    successor_by_id: Mapping[str, tuple[object, ...]],
) -> bool:
    """Compare unique declared concepts, retaining exact ids only for unchained rows.

    Equal box numbers do not override contradictory continuity. A renumbering
    requires a unique, shared chain on both ends; absent or ambiguous targets
    cannot establish identity.
    """
    before_rows = inherited_by_id.get(before, ()) if isinstance(before, str) else ()
    after_rows = successor_by_id.get(after, ()) if isinstance(after, str) else ()
    if before == after and not before_rows and not after_rows:
        return True
    if len(before_rows) != 1 or len(after_rows) != 1:
        return False
    before_lineage = _row_lineage(before_rows[0])
    after_lineage = _row_lineage(after_rows[0])
    if before_lineage is not None or after_lineage is not None:
        return before_lineage is not None and before_lineage == after_lineage
    return before == after


def _casillas_by_id(rows: tuple[object, ...]) -> dict[str, tuple[object, ...]]:
    """Index casillas once while retaining duplicate rows for ambiguity checks."""
    grouped: dict[str, list[object]] = {}
    for row in rows:
        row_id = _row_id(row)
        if row_id is not None:
            grouped.setdefault(row_id, []).append(row)
    return {row_id: tuple(matches) for row_id, matches in grouped.items()}


def _field_at(member: object, path: str) -> object:
    """Return the value at a dotted ``path`` within ``member``, or ``None`` where it does not resolve."""
    return _family_identity_value(member, path)


def _period_token(value: object) -> str | None:
    """The comparable period token of a member's or selector's period value.

    Members spell a period either bare (``"4T"``) or qualified by its year
    (``"2025 01"``); a selector always spells it bare. Taking the last
    whitespace-separated token and upper-casing it compares the two without
    inventing a canonical form for either.
    """
    if not isinstance(value, str) or not value.strip():
        return None
    return value.split()[-1].upper()


def _selector_periods_for_year(table: Mapping[str, object], year: object) -> object:
    """The periods a selector serves in one filing year, honouring a ``period_overrides`` entry.

    A transition year files a narrower surface than the years around it: an
    orden that applies from the second trimestre or the month of February
    leaves January and the first trimestre with the preceding edition. The flat
    ``periods`` tuple cannot say that, so an override replaces it for the one
    year it names. Reading the flat tuple here would inherit a period-scoped
    member for a period the successor does not file in the transition year,
    which no gate would catch because the member is individually valid.

    Mirrors ``PeriodSelector.periods_for_year`` against the raw table, since
    inheritance runs before typed construction.
    """
    if isinstance(year, int):
        overrides = table.get("period_overrides")
        if isinstance(overrides, list | tuple):
            for override in overrides:
                override_table = _as_toml_table(override)
                if override_table is not None and override_table.get("year") == year:
                    return override_table.get("periods")
    return table.get("periods")


def _selector_covers(selector: object, member: object) -> bool:
    """Whether an edition's ``period_selector`` covers this member's own filing period.

    A period-scoped family states one member per filing period, so a
    predecessor's member is not withheld by a successor that simply files a
    different period - it was never the successor's to state. Inheriting it
    would give an edition a deadline for a period it does not file, which no
    gate would catch because the member is individually valid.

    Coverage is decided by the member's OWN declared ``filing_year`` and
    ``period``, never by its identifier: the identifier is a name, and for this
    family the year inside it is data that a rename can destroy.
    """
    table = _as_toml_table(selector)
    member_table = _as_toml_table(member)
    if table is None or member_table is None:
        return True
    year = member_table.get("filing_year")
    if isinstance(year, int):
        years = table.get("years")
        if isinstance(years, list | tuple) and year not in years:
            return False
        year_from = table.get("year_from")
        if isinstance(year_from, int) and year < year_from:
            return False
        year_to = table.get("year_to")
        if isinstance(year_to, int) and year > year_to:
            return False
    period = _period_token(member_table.get("period"))
    periods = _selector_periods_for_year(table, member_table.get("filing_year"))
    if period is not None and isinstance(periods, list | tuple):
        covered = {token for value in periods if (token := _period_token(value)) is not None}
        if covered and period not in covered:
            return False
    return True


def _member_identity(member: object, family: _KeyedFamily) -> str | None:
    """Return ``member``'s identity value for ``family``, or ``None`` when it states none."""
    table = _as_toml_table(member)
    if table is None:
        return None
    identity = table.get(family.identity)
    return identity if isinstance(identity, str) else None


"""A row's claims about its immediate predecessor, which an inheriting edition never carries forward."""
_ROW_CONSTRAINTS_FIELD: Final = "constraints"
_EXPORT_REFS_FIELD: Final = "export_refs"
_REFERENCE_SECTIONS: Final[Mapping[str, str]] = {
    "formula": "formulas",
    "binding": "bindings",
    "alternate_bindings": "bindings",
}
"""Each casilla reference field, and the edition section whose declarations it names."""
_REVISION_ID_ADAPTER: Final = TypeAdapter(RevisionId)

ModeloRevisionSource = _ModeloRevisionSource
clear_fingerprint_cache = _clear_fingerprint_cache
REVISION_GOVERNANCE_FIELDS = _REVISION_GOVERNANCE_FIELDS
REVISION_MANIFEST_ONLY_FIELDS = _REVISION_MANIFEST_ONLY_FIELDS
type _RegistryPathFingerprint = tuple[str, int, int, str]
type _RegistryPathFingerprints = tuple[_RegistryPathFingerprint, ...]


def _build_modelo_definition_from_data(
    source_path: Path,
    data: Mapping[str, object],
    *,
    validation_context: Mapping[str, object] | None = None,
) -> ModeloDefinition:
    """Validate a merged modelo TOML payload into a ModeloDefinition."""
    _reject_local_catalogues(source_path, data)
    if "modelo" not in data:
        raise RegistryLoadError(f"{source_path}: missing [modelo] table")
    modelo_table = _as_toml_table(data["modelo"])
    if modelo_table is None:
        raise RegistryLoadError(f"{source_path}: [modelo] must be a table")
    modelo_id = modelo_table.get("id")
    modelo_id_for_context = modelo_id if isinstance(modelo_id, str) else source_path.as_posix()
    declared_revisions = _as_toml_table(data.get("revisions"))
    if not declared_revisions:
        raise RegistryLoadError(f"{source_path}: missing [revisions.<id>] tables")
    materialised = _materialise_revisions(source_path, str(modelo_id_for_context), declared_revisions)
    predecessor_declarations = _raw_predecessor_declarations(declared_revisions)
    revisions: dict[str, ModeloRevision] = {}
    for revision_id, raw_revision in materialised.revisions.items():
        raw_revision_table = _as_toml_table(raw_revision)
        if raw_revision_table is None:
            raise RegistryLoadError(f"{source_path}: revision {revision_id!r} must be a table")
        label_origins = materialised.label_origins.get(revision_id)
        if label_origins is not None:
            raw_revision_table = _resolve_inherited_references(
                source_path,
                revision_id=revision_id,
                table=raw_revision_table,
                label_origins=label_origins,
            )
        context = f"{source_path}: revision {revision_id!r}"
        raw_revision_table = _apply_edition_reference_defaults(context, raw_revision_table)
        payload = enroll_revision_localization(
            modelo_id=str(modelo_id_for_context),
            revision_id=revision_id,
            raw_revision=raw_revision_table,
        )
        text_origins = materialised.text_origins.get(revision_id)
        if text_origins is not None:
            payload = _enroll_inherited_label_fallbacks(
                context,
                modelo_id=str(modelo_id_for_context),
                payload=payload,
                label_origins=text_origins,
            )
        payload = _mark_inherited_casillas(context, payload=payload, label_origins=label_origins)
        payload = _compile_revision_projection_semantics(source_path, payload)
        _refuse_authored_export_refs(source_path, revision_id, payload)
        try:
            revision = ModeloRevision.model_validate(payload, context=validation_context)
        except ValidationError as exc:
            raise RegistryLoadError(f"{source_path}: invalid revision {revision_id!r}: {exc}") from exc
        revision = _with_derived_export_refs(source_path, revision, payload)
        _raise_on_ambiguous_revision_identity(
            source_path,
            modelo_id=modelo_id_for_context,
            revision_id=revision_id,
            revision=revision,
        )
        revisions[revision_id] = revision
    try:
        _validate_lineage_sidecars(
            revisions,
            predecessors=predecessor_declarations.named if predecessor_declarations is not None else {},
        )
        revisions = {key: _with_lineage_claims(revision) for key, revision in revisions.items()}
    except RegistryValidationError as exc:
        raise RegistryLoadError(f"{source_path}: invalid lineage attestations: {exc}") from exc
    try:
        return ModeloDefinition.model_validate(
            {
                **modelo_table,
                "title_localization_key": modelo_locale_key(str(modelo_id_for_context), "title"),
                "official_name_localization_key": modelo_locale_key(str(modelo_id_for_context), "official_name"),
                "revisions": revisions,
            },
            context=validation_context,
        )
    except ValidationError as exc:
        raise RegistryLoadError(f"{source_path}: invalid modelo definition: {exc}") from exc


def _with_lineage_claims(revision: ModeloRevision) -> ModeloRevision:
    """Expose target-edge claims to typed consumers, never to the inheritance input.

    Sidecars have already passed membership, uniqueness and exact-edge validation.
    The stored claim has one owner; its typed row view must not suppress a second
    authored owner, even when both spell the same evidence.
    """
    claims = {
        attestation.identity: attestation
        for attestation in revision.lineage_attestations
        if attestation.family == _INHERITED_SECTION
    }
    if not claims:
        return revision
    rows = []
    for casilla in revision.casillas:
        claim = claims.get(str(casilla.continuidad_id))
        if claim is None:
            rows.append(casilla)
            continue
        if casilla.continuidad_origin is not None or casilla.continuidad_evidence is not None:
            raise RegistryValidationError(
                f"revision {revision.id!r} casilla {casilla.id!r} duplicates lineage evidence ownership: "
                "declare the claim on the row or in lineage_attestations, not both",
            )
        rows.append(
            casilla.model_copy(
                update={"continuidad_origin": claim.origin, "continuidad_evidence": claim.evidence},
            ),
        )
    return revision.model_copy(update={"casillas": tuple(rows)})


def _validate_lineage_sidecars(
    revisions: Mapping[str, ModeloRevision],
    *,
    predecessors: Mapping[str, str],
) -> None:
    """Validate authored lineage sidecars against the typed materialised revisions.

    The sidecar is revision-level and therefore must be authored on the
    successor it names.  Family identities come from the same canonical keyed
    family policy the materialiser uses: casillas are keyed by
    ``continuidad_id`` and identifier-keyed families by their declared
    identity.  Building the index from typed revisions means inherited members
    are present while row-local claims remain exactly as authored.
    """
    sidecars: list[LineageAttestation] = []
    members_by_revision: dict[str, dict[str, tuple[str, ...]]] = {}
    for revision_id, revision in revisions.items():
        # Casillas participate in predecessor materialisation through their
        # continuity key, but are intentionally absent from the generic keyed
        # family tuple.  The sidecar validator still needs their canonical
        # membership on both ends of an edge; omitting it made every valid
        # casilla attestation look stale at load time.
        families: dict[str, tuple[str, ...]] = {
            _INHERITED_SECTION: tuple(
                str(member.continuidad_id) for member in revision.casillas if member.continuidad_id is not None
            )
        }
        for family in _CANONICAL_INHERITED_FAMILY_SPECS:
            value = getattr(revision, family.section)
            members = (value,) if family.singleton and value is not None else () if family.singleton else value or ()
            identities = tuple(
                str(identity)
                for member in members
                if family.identity is not None
                and (identity := _family_identity_value(member, family.identity)) is not None
            )
            families[family.section] = identities
        members_by_revision[revision_id] = families
        for attestation in revision.lineage_attestations:
            if attestation.to_revision != revision_id:
                raise RegistryValidationError(
                    f"revision {revision_id!r} authors lineage attestation for target "
                    f"revision {attestation.to_revision!r}; sidecars are edge-local and "
                    "must be authored on their target revision",
                )
            sidecars.append(attestation)
    validate_lineage_attestations(
        sidecars,
        predecessors=predecessors,
        members_by_revision=members_by_revision,
    )


@dataclass(frozen=True, slots=True)
class _RawPredecessorDeclarations:
    """Each edition's predecessor declaration, read from the raw revision tables."""

    named: Mapping[str, str]
    declared_roots: frozenset[str]
    keyless: frozenset[str]


def _raw_predecessor_declarations(raw_revisions: Mapping[str, object]) -> _RawPredecessorDeclarations | None:
    """Project every edition's authored ``predecessor`` onto the three declaration states.

    Returns ``None`` when any edition is not a table or spells its declaration
    in a shape no state admits. Materialisation then does nothing, and typed
    construction refuses the malformed edition with the declaration's own
    error rather than one this projection would have to invent.
    """
    named: dict[str, str] = {}
    declared_roots: set[str] = set()
    keyless: set[str] = set()
    for revision_id, raw_revision in raw_revisions.items():
        table = _as_toml_table(raw_revision)
        if table is None:
            return None
        declaration = table.get(_PREDECESSOR_FIELD)
        if declaration is None:
            keyless.add(revision_id)
        elif isinstance(declaration, str) and _is_revision_id(declaration):
            named[revision_id] = declaration
        elif isinstance(declaration, Mapping) and set(declaration) == {_NO_PREDECESSOR_TABLE_KEY}:
            declared_roots.add(revision_id)
        else:
            return None
    return _RawPredecessorDeclarations(
        named=named,
        declared_roots=frozenset(declared_roots),
        keyless=frozenset(keyless),
    )


def _is_revision_id(value: str) -> bool:
    try:
        _REVISION_ID_ADAPTER.validate_python(value)
    except ValidationError:
        return False
    return True


type _LabelOrigins = tuple[str | None, ...]
"""Per casilla row, in row order: the edition that last stated the row, or ``None`` if its own edition states it."""


@dataclass(frozen=True, slots=True)
class _MaterialisedRevisions:
    """Every edition's raw table after materialisation, with the label origins of the inherited rows.

    The origins travel beside the tables rather than inside them because the
    raw table must stay the exact shape the closed typed model accepts. Only an
    edition that inherits appears in ``label_origins``.
    """

    revisions: Mapping[str, object]
    label_origins: Mapping[str, _LabelOrigins]
    text_origins: Mapping[str, _LabelOrigins] = dataclass_field(default_factory=dict)
    """Per inheriting edition, the edition whose catalogue holds each row's text.

    It differs from ``label_origins`` only for a row a storage patch restates
    without changing its label identity: the patch makes the row stated for
    reference resolution and minimality, but its text still lives where the
    edition that stated the row put it.
    """


@dataclass(frozen=True, slots=True)
class _MaterialisedRevision:
    """One edition resolved against its chain; ``label_origins`` is ``None`` when it inherits nothing."""

    table: Mapping[str, object]
    label_origins: _LabelOrigins | None
    text_origins: _LabelOrigins | None = None


def _materialise_revisions(
    source_path: Path,
    modelo_id: str,
    raw_revisions: Mapping[str, object],
) -> _MaterialisedRevisions:
    """Resolve every edition naming a predecessor into the full raw revision it stands for.

    The output has the shape typed construction already consumes, one raw
    table per edition in declaration order, so nothing downstream can tell a
    materialised edition from one that states every row itself.

    An edition is delta-authored only when its manifest names a predecessor.
    Nothing here infers one: an edition omitting the key, or declaring that no
    predecessor exists, is returned as the identical object it arrived as, and
    a modelo none of whose editions names a predecessor is returned whole.

    Inheritance covers the casilla family and nothing else. Every other family
    is declared in full by every edition. The completeness manifest is excluded
    deliberately, not by omission: its rows are casilla-shaped, but a manifest
    is a derived assertion about its own edition's formula closure, and its
    presence is a graded capability claim, so an inherited one would attest
    support the successor never earned.

    Within the casilla family, rows are matched on ``continuidad_id``:

    - an inherited row is kept unless a stated row carries its lineage, in
      which case the stated row replaces it in its position. A kept row loses
      ``continuidad_origin`` and ``continuidad_evidence`` and is otherwise
      unchanged: both state the row's relationship to the edition before the
      one that stated it, which is false one edition later;
    - a stated row carrying no inherited lineage is new and is appended after
      the inherited rows, in stated order;
    - an inherited row whose lineage the successor retires, through a
      ``retired`` casilla evolution whose ``to_revision`` is the successor, is
      dropped.

    That fixes the materialised row order: inherited rows in the predecessor's
    materialised order, each superseding row in the position of the row it
    supersedes, and new rows after them in stated order. The order is defined
    by this merge, not reproduced from any full copy the edition replaced.

    Refused, because each would otherwise resolve silently to a guess:

    - a stated row whose id collides with an inherited row it does not
      supersede, which is a repurpose nobody declared; two rows without lineage
      sharing an id are refused the same way, since supersession has no key;
    - two stated rows carrying one lineage, or a stated lineage that the
      predecessor carries on more than one row;
    - a stated row carrying a lineage the same edition retires.

    The predecessor graph is checked as a forest first, so the recursion walks
    a tree and a chain resolves its predecessor before the successor. Every
    edge is a storage relationship only; it neither changes nor constrains the
    successor's independently declared capability.

    Where it stops: an inherited row keeps the formula and binding references
    its stating edition authored; the label origins returned beside the rows
    are what lets them be resolved against the successor afterwards. It adds no
    locale identity to the rows either; enrolment afterwards derives every
    row's keys from the edition it now sits in, and the label origins returned
    beside the rows let enrolment add the one fallback an inherited row needs.
    The same origins become each typed row's ``inherited_from`` marker after
    enrolment; the raw rows carry no marker, so a materialised table written
    back as a full copy states nothing the loader would refuse.
    """
    declarations = _raw_predecessor_declarations(raw_revisions)
    storage_named: dict[str, str] = {}
    family_storage_named: dict[str, str] = {}
    for revision_id, raw_revision in raw_revisions.items():
        table = _as_toml_table(raw_revision)
        baseline = None if table is None else table.get(_CASILLA_STORAGE_BASELINE_FIELD)
        if isinstance(baseline, str):
            if baseline == revision_id or baseline not in raw_revisions:
                raise RegistryLoadError(
                    f"{source_path}: revision {revision_id!r} has invalid casilla storage baseline {baseline!r}"
                )
            storage_named[revision_id] = baseline
        family_baseline = None if table is None else table.get(_FAMILY_STORAGE_BASELINE_FIELD)
        if isinstance(family_baseline, str):
            if family_baseline == revision_id or family_baseline not in raw_revisions:
                raise RegistryLoadError(
                    f"{source_path}: revision {revision_id!r} has invalid family storage baseline {family_baseline!r}"
                )
            family_storage_named[revision_id] = family_baseline
    if (declarations is None or not declarations.named) and not storage_named and not family_storage_named:
        return _MaterialisedRevisions(revisions=raw_revisions, label_origins={})
    if declarations is not None and declarations.named:
        try:
            validate_predecessor_forest(
                modelo_id,
                named=declarations.named,
                declared_roots=declarations.declared_roots,
                keyless=declarations.keyless,
            )
        except RegistryValidationError as exc:
            raise RegistryLoadError(f"{source_path}: invalid modelo definition: {exc}") from exc
    semantic_named = {} if declarations is None else declarations.named
    resolved: dict[str, _MaterialisedRevision] = {}
    materialised: dict[str, object] = dict(raw_revisions)
    label_origins: dict[str, _LabelOrigins] = {}
    text_origins: dict[str, _LabelOrigins] = {}
    for revision_id in dict.fromkeys((*semantic_named, *storage_named, *family_storage_named)):
        revision = _materialise_revision(
            source_path,
            raw_revisions,
            semantic_named,
            storage_named,
            family_storage_named,
            revision_id,
            resolved,
        )
        materialised[revision_id] = revision.table
        if revision.label_origins is not None:
            label_origins[revision_id] = revision.label_origins
        if revision.text_origins is not None:
            text_origins[revision_id] = revision.text_origins
    return _MaterialisedRevisions(revisions=materialised, label_origins=label_origins, text_origins=text_origins)


def _materialise_revision(
    source_path: Path,
    raw_revisions: Mapping[str, object],
    named: Mapping[str, str],
    storage_named: Mapping[str, str],
    family_storage_named: Mapping[str, str],
    revision_id: str,
    resolved: dict[str, _MaterialisedRevision],
) -> _MaterialisedRevision:
    """Return one edition with its predecessor chain's casillas resolved into it."""
    cached = resolved.get(revision_id)
    if cached is not None:
        return cached
    table = _as_toml_table(raw_revisions[revision_id])
    if table is None:
        raise RegistryLoadError(f"{source_path}: revision {revision_id!r} must be a table")
    predecessor_id = named.get(revision_id)
    storage_baseline_id = storage_named.get(revision_id)
    family_baseline_id = family_storage_named.get(revision_id)
    casilla_baseline_id = predecessor_id or storage_baseline_id
    family_baseline_id = predecessor_id or family_baseline_id
    result = _MaterialisedRevision(table=table, label_origins=None)
    if casilla_baseline_id is not None or family_baseline_id is not None:
        if casilla_baseline_id is None:
            rows = _raw_casilla_rows(source_path, revision_id, table)
            label_origins = None
            text_origins = None
        else:
            casilla_predecessor = _materialise_revision(
                source_path, raw_revisions, named, storage_named, family_storage_named, casilla_baseline_id, resolved
            )
            relation = "inheriting from" if predecessor_id is not None else "hydrating casillas from"
            rows, label_origins, text_origins = _inherit_casillas(
                f"{source_path}: revision {revision_id!r} {relation} {casilla_baseline_id!r}",
                revision_id=revision_id,
                predecessor_id=casilla_baseline_id,
                inherited=_raw_casilla_rows(source_path, casilla_baseline_id, casilla_predecessor.table),
                inherited_label_origins=casilla_predecessor.label_origins,
                inherited_text_origins=casilla_predecessor.text_origins,
                successor=table,
            )
        merged: dict[str, object] = {**table, _INHERITED_SECTION: rows}
        restated = _restated_families(table)
        if family_baseline_id is not None:
            family_predecessor = _materialise_revision(
                source_path, raw_revisions, named, storage_named, family_storage_named, family_baseline_id, resolved
            )
            asserted = as_toml_array(table.get("scoped_families", ())) or ()
            declined = cleared_family_names(table.get(_CLEARED_FAMILIES_FIELD, ()))
            for family in _KEYED_FAMILIES:
                if family.section in restated:
                    continue
                if family.scoped and family.section not in asserted:
                    _refuse_undecided_scoped_family(
                        f"{source_path}: revision {revision_id!r} inheriting from {family_baseline_id!r}",
                        family=family,
                        inherited=_raw_keyed_members(source_path, family_baseline_id, family_predecessor.table, family),
                        stated=_raw_keyed_members(source_path, revision_id, table, family),
                        declined=declined,
                    )
                    continue
                family_members = inherit_keyed_family(
                    f"{source_path}: revision {revision_id!r} inheriting from {family_baseline_id!r}",
                    revision_id=revision_id,
                    predecessor_id=family_baseline_id,
                    predecessor=family_predecessor.table,
                    storage_only=predecessor_id is None,
                    family=family,
                    inherited=_raw_keyed_members(source_path, family_baseline_id, family_predecessor.table, family),
                    inherited_casillas=_raw_casilla_rows(source_path, family_baseline_id, family_predecessor.table),
                    successor_casillas=rows,
                    successor=table,
                )
                merged[family.section] = (
                    family_members[0]
                    if family.singleton and family_members
                    else (None if family.singleton else family_members)
                )
        result = _MaterialisedRevision(table=merged, label_origins=label_origins, text_origins=text_origins)
    resolved[revision_id] = result
    return result


def _raw_casilla_rows(source_path: Path, revision_id: str, table: Mapping[str, object]) -> tuple[object, ...]:
    rows = as_toml_array(table.get(_INHERITED_SECTION, ()))
    if rows is None:
        raise RegistryLoadError(f"{source_path}: revision {revision_id!r} casillas must be an array")
    return rows


def _inherit_casillas(
    context: str,
    *,
    revision_id: str,
    predecessor_id: str,
    inherited: tuple[object, ...],
    inherited_label_origins: _LabelOrigins | None,
    inherited_text_origins: _LabelOrigins | None,
    successor: Mapping[str, object],
) -> tuple[tuple[object, ...], _LabelOrigins, _LabelOrigins]:
    """Merge the predecessor's materialised casillas with the successor's stated ones.

    Returns the merged rows and, aligned with them, each row's label origin and
    text origin. A storage patch states a row for every purpose except its
    text: unless the patch changes the row's label identity, the text origin
    keeps pointing at the edition that stated the row.
    A kept inherited row takes the origin it already had in the predecessor,
    or the predecessor itself when the predecessor stated it, so the origin of
    a row carried down a chain is the edition that last stated it rather than
    the immediate predecessor, whose catalogue has no entry for it either.
    """
    if inherited_label_origins is not None and len(inherited_label_origins) != len(inherited):
        raise RegistryLoadError(
            f"{context}: the predecessor's label origins cover {len(inherited_label_origins)} of its "
            f"{len(inherited)} casillas",
        )
    stated = as_toml_array(successor.get(_INHERITED_SECTION, ()))
    if stated is None:
        raise RegistryLoadError(f"{context}: casillas must be an array")
    carried: list[tuple[str | None, str | None]] = [
        (
            None if inherited_label_origins is None else inherited_label_origins[index],
            None if inherited_text_origins is None else inherited_text_origins[index],
        )
        for index in range(len(inherited))
    ]
    inherited, carried, storage_overridden, storage_relabelled = _apply_casilla_storage_delta(
        context,
        predecessor_id=predecessor_id,
        inherited=inherited,
        origins=carried,
        successor=successor,
    )
    retired = _retired_lineages(successor, revision_id)
    superseders = _stated_rows_by_lineage(context, stated, retired)
    inherited_lineage_counts = Counter(lineage for row in inherited if (lineage := _row_lineage(row)) is not None)
    ambiguous = sorted(lineage for lineage in superseders if inherited_lineage_counts[lineage] > 1)
    if ambiguous:
        raise RegistryLoadError(
            f"{context}: the predecessor carries lineage {ambiguous!r} on more than one row, so a stated row "
            "carrying it cannot say which one it supersedes",
        )
    rows: list[object] = []
    origins: list[tuple[str | None, str | None]] = []
    kept_lineage_by_id: dict[str, str | None] = {}
    superseded: set[str] = set()
    for index, row in enumerate(inherited):
        lineage = _row_lineage(row)
        if lineage is not None and lineage in retired:
            continue
        if lineage is not None and lineage in superseders:
            rows.append(superseders[lineage])
            origins.append((None, None))
            superseded.add(lineage)
            continue
        rows.append(row if _row_id(row) in storage_overridden else _without_lineage_claims(row))
        carried_statement, carried_text = carried[index]
        origins.append(
            (
                None if _row_id(row) in storage_overridden else carried_statement or predecessor_id,
                None if _row_id(row) in storage_relabelled else carried_text or carried_statement or predecessor_id,
            )
        )
        row_id = _row_id(row)
        if row_id is not None:
            kept_lineage_by_id[row_id] = lineage
    for row in stated:
        lineage = _row_lineage(row)
        row_id = _row_id(row)
        if row_id is not None and row_id in kept_lineage_by_id:
            raise RegistryLoadError(
                f"{context}: stated casilla {row_id!r} of lineage {_lineage_label(lineage)} collides with the "
                f"inherited casilla {row_id!r} of lineage {_lineage_label(kept_lineage_by_id[row_id])}; a stated "
                "row supersedes only the inherited row carrying its own lineage, so declare the repurpose by "
                "keeping the lineage, or retire the inherited lineage",
            )
        if lineage is None or lineage not in superseded:
            rows.append(row)
            origins.append((None, None))
    rows, origins = _apply_casilla_positions(context, rows, origins, successor)
    return (
        tuple(rows),
        tuple(statement for statement, _text in origins),
        tuple(text for _statement, text in origins),
    )


def _apply_casilla_storage_delta(
    context: str,
    *,
    predecessor_id: str,
    inherited: tuple[object, ...],
    origins: list[tuple[str | None, str | None]],
    successor: Mapping[str, object],
) -> tuple[tuple[object, ...], list[tuple[str | None, str | None]], frozenset[str], frozenset[str]]:
    """Apply storage-only patches without deriving a continuity relationship.

    Returns the kept rows and their ``(label, text)`` origins, the ids of every
    patched row, and the ids of the patched rows whose label identity changed.
    Every patched row loses its label origin; only the last also lose their
    text origin, because a provenance-only patch leaves the row's text where
    the edition that stated it put it.
    """
    raw_overrides = as_toml_array(successor.get("casilla_overrides", ())) or ()
    raw_removals = as_toml_array(successor.get("casilla_removals", ())) or ()
    try:
        overrides = tuple(CasillaFieldOverride.model_validate(value) for value in raw_overrides)
        removals = tuple(CasillaMemberRemoval.model_validate(value) for value in raw_removals)
    except ValidationError as exc:
        raise RegistryLoadError(f"{context}: invalid casilla storage delta: {exc}") from exc
    by_id: dict[str, int] = {}
    for index, row in enumerate(inherited):
        row_id = _row_id(row)
        if row_id is None:
            continue
        if row_id in by_id:
            raise RegistryLoadError(f"{context}: predecessor has duplicate casilla storage id {row_id!r}")
        by_id[row_id] = index
    seen: set[str] = set()
    removed: set[str] = set()
    overridden: set[str] = set()
    relabelled: set[str] = set()
    result = list(inherited)
    origins = list(origins)
    for declaration in removals:
        selector = declaration.selector
        if str(selector.revision) != predecessor_id:
            raise RegistryLoadError(
                f"{context}: casilla removal baseline {selector.revision!s} is not predecessor {predecessor_id!r}"
            )
        identity = str(selector.id)
        if identity not in by_id or identity in seen:
            raise RegistryLoadError(f"{context}: casilla removal selector {identity!r} is missing or repeated")
        seen.add(identity)
        removed.add(identity)
    for declaration in overrides:
        selector = declaration.selector
        if str(selector.revision) != predecessor_id:
            raise RegistryLoadError(
                f"{context}: casilla override baseline {selector.revision!s} is not predecessor {predecessor_id!r}"
            )
        identity = str(selector.id)
        if identity not in by_id or identity in seen:
            raise RegistryLoadError(f"{context}: casilla override selector {identity!r} is missing or repeated")
        seen.add(identity)
        table = _as_toml_table(result[by_id[identity]])
        if table is None:
            raise RegistryLoadError(f"{context}: selected casilla {identity!r} is not a table")
        patched = {key: value for key, value in table.items() if key not in _ROW_LINEAGE_CLAIM_FIELDS}
        if _ROW_SOURCE_FIELD in declaration.fields:
            patched.pop(_ROW_SOURCE_ADDITIONS_FIELD, None)
        result[by_id[identity]] = _patch_family_table(
            f"{context}: casilla {identity!r}", patched, declaration.fields, declaration.removed_fields
        )
        resulting_id = _row_id(result[by_id[identity]])
        changes_label_identity = bool(
            _ROW_LABEL_IDENTITY_FIELDS.intersection(declaration.fields)
            or _ROW_LABEL_IDENTITY_FIELDS.intersection(declaration.removed_fields)
        )
        if resulting_id is not None:
            overridden.add(resulting_id)
            if changes_label_identity:
                relabelled.add(resulting_id)
        statement, text = origins[by_id[identity]]
        origins[by_id[identity]] = (None, None if changes_label_identity else text or statement or predecessor_id)
    kept_indexes = [index for index, row in enumerate(result) if (_row_id(row) or "") not in removed]
    kept_rows = tuple(result[index] for index in kept_indexes)
    kept_origins = [origins[index] for index in kept_indexes]
    return kept_rows, kept_origins, frozenset(overridden), frozenset(relabelled)


def _apply_casilla_positions[OriginT](
    context: str,
    rows: list[object],
    origins: list[OriginT],
    successor: Mapping[str, object],
) -> tuple[list[object], list[OriginT]]:
    raw = as_toml_array(successor.get("casilla_positions", ())) or ()
    try:
        positions = tuple(CasillaMemberPosition.model_validate(value) for value in raw)
    except ValidationError as exc:
        raise RegistryLoadError(f"{context}: invalid casilla positions: {exc}") from exc
    seen: set[str] = set()
    # Row ids move with their rows, so one derivation per row serves every
    # declaration; deriving them afresh per declaration made a large edition
    # quadratic in its member count.
    row_ids: list[str | None] = [_row_id(row) for row in rows]
    for declaration in positions:
        identity = str(declaration.id)
        if identity in seen:
            raise RegistryLoadError(f"{context}: duplicate casilla position for {identity!r}")
        seen.add(identity)
        try:
            index = row_ids.index(identity)
        except ValueError:
            index = None
        if index is None or declaration.position >= len(rows):
            raise RegistryLoadError(f"{context}: casilla position for {identity!r} is outside the effective member set")
        row, origin, row_id = rows.pop(index), origins.pop(index), row_ids.pop(index)
        rows.insert(declaration.position, row)
        origins.insert(declaration.position, origin)
        row_ids.insert(declaration.position, row_id)
    return rows, origins


def _without_lineage_claims(row: object) -> object:
    """Return ``row`` without its claims about its predecessor, or ``row`` itself when it states none."""
    table = _as_toml_table(row)
    if table is None or not any(field in table for field in _ROW_LINEAGE_CLAIM_FIELDS):
        return row
    return {key: value for key, value in table.items() if key not in _ROW_LINEAGE_CLAIM_FIELDS}


def _stated_rows_by_lineage(
    context: str,
    stated: tuple[object, ...],
    retired: frozenset[str],
) -> dict[str, object]:
    by_lineage: dict[str, object] = {}
    for row in stated:
        lineage = _row_lineage(row)
        if lineage is None:
            continue
        if lineage in retired:
            raise RegistryLoadError(
                f"{context}: states a casilla of lineage {lineage!r}, which the same edition retires",
            )
        if lineage in by_lineage:
            raise RegistryLoadError(
                f"{context}: states more than one casilla of lineage {lineage!r}, so neither can supersede "
                "the inherited row",
            )
        by_lineage[lineage] = row
    return by_lineage


def _retired_lineages(successor: Mapping[str, object], revision_id: str) -> frozenset[str]:
    """Return the lineages the successor withdraws through a ``retired`` evolution into itself."""
    evolutions = as_toml_array(successor.get(_RETIREMENT_SECTION, ())) or ()
    retired: set[str] = set()
    for raw_evolution in evolutions:
        evolution = _as_toml_table(raw_evolution)
        if evolution is None or evolution.get("to_revision") != revision_id:
            continue
        lineage = evolution.get("continuidad_id")
        if evolution.get("evolution_kind") == CasillaEvolutionKind.RETIRED and isinstance(lineage, str):
            retired.add(lineage)
    from cadrumo.domain.calculations.registry.casilla_structural_succession import CasillaStructuralSuccession

    for raw_relation in as_toml_array(successor.get("casilla_structural_successions", ())) or ():
        relation = CasillaStructuralSuccession.model_validate(raw_relation)
        if relation.to_revision == revision_id:
            retired.update(relation.source_lineages)
    return frozenset(retired)


def _row_lineage(row: object) -> str | None:
    table = _as_toml_table(row)
    lineage = None if table is None else table.get("continuidad_id")
    return lineage if isinstance(lineage, str) else None


def _row_id(row: object) -> str | None:
    table = _as_toml_table(row)
    row_id = None if table is None else table.get("id")
    return row_id if isinstance(row_id, str) else None


def _lineage_label(lineage: str | None) -> str:
    return repr(lineage) if lineage is not None else "(none declared)"


def _apply_edition_reference_defaults(context: str, table: Mapping[str, object]) -> Mapping[str, object]:
    """Fill the edition's declared reference defaults into the casilla rows that state none.

    Three families, each defaulted from its own manifest key: ``casillas``
    from ``casilla_source_refs``, ``bindings`` from ``binding_source_refs``, and
    ``formulas`` from ``formula_source_refs``. The member-side rule is one rule
    for all three; only the casilla family also defaults a ``constraints``
    table and a ``legal_refs``.

    Two defaults for the casilla family, both declared once on the edition's
    manifest:

    - ``casilla_source_refs`` becomes the ``source_refs`` of every casilla row,
      and of every row's ``constraints`` table, that states no ``source_refs``.
      A row or constraints table stating ``additional_source_refs`` instead
      takes the default followed by its additions, duplicates removed and the
      default first, and the additions key is consumed;
    - ``orden_aplicabilidad``, the edition's approving ordenes, becomes the
      ``legal_refs`` of every casilla row and ``constraints`` table that states
      no ``legal_refs``.

    A stated ``source_refs`` or ``legal_refs`` is kept whole, including a stated
    empty array, which typed construction then refuses. A default is never
    merged into a stated value; only additions extend one.

    It runs on the materialised edition, so an inherited CASILLA is defaulted
    from the edition it now sits in: a casilla carries its own lineage and the
    edition it lands in grounds it. Additions are the row's own and so extend
    the default of the edition the row now sits in.

    A keyed-family member is the other case, and :func:`_pin_family_source_default`
    has already bound it to the default effective where it was stated, so it
    arrives here carrying ``source_refs`` and is left alone. Re-grounding it
    would make the successor's source attest a row that source never saw.

    Returns the identical table when it fills nothing, so an edition declaring
    no default and no additions reaches typed construction exactly as authored.
    A default that is absent, empty or not an array fills nothing and is left to
    typed construction, as is a casilla section or row that is not the shape it
    should be.

    Raises:
        RegistryLoadError: When a row or constraints table states both
            ``source_refs`` and ``additional_source_refs``, states additions that
            are not a non-empty array of reference ids, or states additions in
            an edition declaring no ``casilla_source_refs`` for them to extend.
    """
    source_default = as_toml_array(table.get(_EDITION_SOURCE_DEFAULT_FIELD)) or ()
    orden_default = as_toml_array(table.get(_EDITION_ORDEN_FIELD)) or ()
    filled: dict[str, object] = {}
    rows = as_toml_array(table.get(_INHERITED_SECTION, ()))
    if rows:
        defaulted = tuple(
            _default_row_references(context, row, source_default=source_default, orden_default=orden_default)
            for row in rows
        )
        if any(new is not old for new, old in zip(defaulted, rows, strict=True)):
            filled[_INHERITED_SECTION] = defaulted
    for section, default_field in family_source_default_fields():
        section_rows = as_toml_array(table.get(section, ()))
        if not section_rows:
            continue
        family_default = as_toml_array(table.get(default_field)) or ()
        defaulted = tuple(
            _default_family_row_references(
                f"{context}: {section}", row, source_default=family_default, default_field=default_field
            )
            for row in section_rows
        )
        if any(new is not old for new, old in zip(defaulted, section_rows, strict=True)):
            filled[section] = defaulted
    return {**table, **filled} if filled else table


def _default_family_row_references(
    context: str,
    row: object,
    *,
    source_default: tuple[object, ...],
    default_field: str,
) -> object:
    """Return one binding or formula row with the edition's family default filled in.

    The casilla rule without the parts casillas alone have: these families carry
    no ``constraints`` table to default alongside the row, and no
    ``orden_aplicabilidad`` default -- the approving ordenes ground a box's
    existence, not a binding's record position -- so a family row's
    ``legal_refs`` stays exactly as authored.
    """
    table = _as_toml_table(row)
    if table is None:
        return row
    filled = _defaulted_references(
        f"{context} {_row_id(table)!r}",
        table,
        source_default=source_default,
        orden_default=(),
        default_field=default_field,
    )
    return row if filled is table else filled


def _default_row_references(
    context: str,
    row: object,
    *,
    source_default: tuple[object, ...],
    orden_default: tuple[object, ...],
) -> object:
    """Return ``row`` with its references and its constraints' defaulted, or ``row`` itself when nothing changes."""
    table = _as_toml_table(row)
    if table is None:
        return row
    subject = f"{context}: casilla {_row_id(table)!r}"
    filled = _defaulted_references(subject, table, source_default=source_default, orden_default=orden_default)
    constraints = _as_toml_table(table.get(_ROW_CONSTRAINTS_FIELD))
    if constraints is not None:
        filled_constraints = _defaulted_references(
            f"{subject} constraints", constraints, source_default=source_default, orden_default=orden_default
        )
        if filled_constraints is not constraints:
            filled = {**filled, _ROW_CONSTRAINTS_FIELD: filled_constraints}
    return row if filled is table else filled


def _defaulted_references(
    subject: str,
    table: Mapping[str, object],
    *,
    source_default: tuple[object, ...],
    orden_default: tuple[object, ...],
    default_field: str = _EDITION_SOURCE_DEFAULT_FIELD,
) -> Mapping[str, object]:
    """Return one row or constraints table with its references resolved, or ``table`` itself when nothing changes."""
    updates: dict[str, object] = {}
    if _ROW_SOURCE_ADDITIONS_FIELD in table:
        updates[_ROW_SOURCE_FIELD] = _extended_source_default(subject, table, source_default, default_field)
    elif source_default and _ROW_SOURCE_FIELD not in table:
        updates[_ROW_SOURCE_FIELD] = source_default
    if orden_default and _ROW_LEGAL_FIELD not in table:
        updates[_ROW_LEGAL_FIELD] = orden_default
    if not updates:
        return table
    kept = {key: value for key, value in table.items() if key != _ROW_SOURCE_ADDITIONS_FIELD}
    return {**kept, **updates}


def _extended_source_default(
    subject: str,
    table: Mapping[str, object],
    source_default: tuple[object, ...],
    default_field: str = _EDITION_SOURCE_DEFAULT_FIELD,
) -> tuple[object, ...]:
    """Return the edition default followed by the table's additions, each reference once, the default first.

    A default holding anything but reference ids is concatenated unchanged and
    left to typed construction, which refuses it with the field's own error.
    """
    if _ROW_SOURCE_FIELD in table:
        raise RegistryLoadError(
            f"{subject} states both {_ROW_SOURCE_FIELD} and {_ROW_SOURCE_ADDITIONS_FIELD}; {_ROW_SOURCE_FIELD} "
            f"replaces the edition's {default_field} whole while {_ROW_SOURCE_ADDITIONS_FIELD} "
            "extends it, so state one of them",
        )
    if not source_default:
        raise RegistryLoadError(
            f"{subject} states {_ROW_SOURCE_ADDITIONS_FIELD}, but the edition declares no "
            f"{default_field} for them to extend; state {_ROW_SOURCE_FIELD} instead",
        )
    additions = as_toml_array(table.get(_ROW_SOURCE_ADDITIONS_FIELD))
    if not additions or not all(isinstance(item, str) for item in additions):
        raise RegistryLoadError(
            f"{subject} {_ROW_SOURCE_ADDITIONS_FIELD} must be a non-empty array of source reference ids; "
            "omit the key to take the edition default alone",
        )
    if not all(isinstance(item, str) for item in source_default):
        return (*source_default, *additions)
    return tuple(dict.fromkeys((*source_default, *additions)))


def _resolve_inherited_references(
    source_path: Path,
    *,
    revision_id: str,
    table: Mapping[str, object],
    label_origins: _LabelOrigins,
) -> Mapping[str, object]:
    """Point every inherited casilla's formula and binding references at this edition's own declarations.

    An inherited row arrives with the references its stating edition authored,
    which name that edition's formulas and bindings. Each reference is replaced
    by the declaration of this edition carrying the same lineage, as
    :func:`~dev.registry.compiler.identifier_lineage.identifier_lineage`
    defines it: the reference's lineage is taken against the stating edition,
    each declaration's against this one. A reference whose lineage no
    declaration of this edition carries is refused rather than kept, since the
    pointer it holds names another edition's declaration.

    Stated rows are returned untouched; their references are this edition's
    own, and reference validation checks them as authored. A field or row that
    is not the shape it should be is left for typed construction to refuse.

    Returns the identical table when no reference changes, which is always the
    case once identifiers stop embedding an edition key and every inherited
    reference resolves to itself.
    """
    context = f"{source_path}: revision {revision_id!r}"
    rows = _raw_casilla_rows(source_path, revision_id, table)
    if len(rows) != len(label_origins):
        raise RegistryLoadError(
            f"{context}: label origins cover {len(label_origins)} of the edition's {len(rows)} casillas",
        )
    declarations = {
        section: _declarations_by_lineage(table, section, revision_id) for section in _REFERENCE_SECTIONS.values()
    }
    resolved = tuple(
        row
        if origin is None
        else _resolve_row_references(context, row, origin=origin, revision_id=revision_id, declarations=declarations)
        for row, origin in zip(rows, label_origins, strict=True)
    )
    if all(new is old for new, old in zip(resolved, rows, strict=True)):
        return table
    return {**table, _INHERITED_SECTION: resolved}


def _declarations_by_lineage(
    table: Mapping[str, object],
    section: str,
    revision_id: str,
) -> Mapping[str, tuple[str, ...]]:
    """Group the edition's declared identifiers of one section by lineage."""
    by_lineage: dict[str, dict[str, None]] = {}
    for raw in as_toml_array(table.get(section, ())) or ():
        declaration_id = _row_id(raw)
        if declaration_id is not None:
            by_lineage.setdefault(identifier_lineage(declaration_id, revision_id), {})[declaration_id] = None
    return {lineage: tuple(ids) for lineage, ids in by_lineage.items()}


def _resolve_row_references(
    context: str,
    row: object,
    *,
    origin: str,
    revision_id: str,
    declarations: Mapping[str, Mapping[str, tuple[str, ...]]],
) -> object:
    """Return ``row`` with its references resolved, or ``row`` itself when each already names its target."""
    table = _as_toml_table(row)
    if table is None:
        return row
    casilla_id = _row_id(table)
    updates: dict[str, object] = {}
    for field, section in _REFERENCE_SECTIONS.items():
        value = table.get(field)

        def resolve(reference: str, *, field: str = field, section: str = section) -> str:
            return _resolve_reference(
                context,
                casilla_id=casilla_id,
                field=field,
                reference=reference,
                origin=origin,
                revision_id=revision_id,
                section=section,
                declarations=declarations[section],
            )

        if isinstance(value, str):
            resolved: object = resolve(value)
        elif (items := as_toml_array(value)) is not None:
            resolved = tuple(resolve(item) if isinstance(item, str) else item for item in items)
        else:
            continue
        if resolved != value:
            updates[field] = resolved
    if not updates:
        return row
    return {**table, **updates}


def _resolve_reference(
    context: str,
    *,
    casilla_id: str | None,
    field: str,
    reference: str,
    origin: str,
    revision_id: str,
    section: str,
    declarations: Mapping[str, tuple[str, ...]],
) -> str:
    lineage = identifier_lineage(reference, origin)
    candidates = declarations.get(lineage, ())
    if len(candidates) == 1:
        return candidates[0]
    found = (
        f"{len(candidates)} {section} declarations {list(candidates)!r}" if candidates else f"no {section} declaration"
    )
    raise RegistryLoadError(
        f"{context}: inherited casilla {casilla_id!r} {field} reference {reference!r}, stated in revision "
        f"{origin!r}, has lineage {lineage!r}, and revision {revision_id!r} carries {found} of that lineage; "
        "an inherited reference must resolve to exactly one of this edition's own declarations, so declare it "
        "here or state the row in this edition",
    )


def _enroll_inherited_label_fallbacks(
    context: str,
    *,
    modelo_id: str,
    payload: dict[str, object],
    label_origins: _LabelOrigins,
) -> dict[str, object]:
    """Give every inherited casilla the occurrence key of the edition that last stated it.

    Enrolment keys an inherited row to the edition it now sits in, which is the
    right identity, but the label catalogue is authored per edition and holds
    the row's text only under the key of the edition that stated it. That key
    joins the row's resolution chain directly after its own occurrence key and
    ahead of its continuity key: an entry the successor authors for the row
    still wins, the stated edition's exact text comes next, and the lineage-wide
    text stays the last tier. A row whose chain resolves nowhere still raises on
    lookup, exactly as before.

    An alias resolves through one key with no chain, so an inherited row that
    carries aliases is refused here instead of loading with alias labels that
    raise on first read.
    """
    casillas = as_toml_array(payload.get(_INHERITED_SECTION))
    if casillas is None or len(casillas) != len(label_origins):
        raise RegistryLoadError(
            f"{context}: label origins cover {len(label_origins)} casillas but enrolment produced "
            f"{'no casilla array' if casillas is None else len(casillas)}",
        )
    enrolled: list[object] = []
    for casilla, origin in zip(casillas, label_origins, strict=True):
        table = None if origin is None else _as_toml_table(casilla)
        keys = None if table is None else table.get("localization_keys")
        casilla_id = None if table is None else table.get("id")
        # A row enrolment could not key is left for typed construction to refuse.
        if table is None or origin is None or not isinstance(casilla_id, str) or not isinstance(keys, tuple):
            enrolled.append(casilla)
            continue
        if table.get("aliases"):
            raise RegistryLoadError(
                f"{context}: inherited casilla {casilla_id!r} carries aliases, whose labels resolve only under "
                f"this edition's key and have no fallback to {origin!r}; state the row in this edition",
            )
        fallback = casilla_occurrence_locale_key(modelo_id, origin, casilla_id, ModeloLocalizationFieldKind.LABEL)
        enrolled.append({**table, "localization_keys": (*keys[:1], fallback, *keys[1:])})
    return {**payload, _INHERITED_SECTION: tuple(enrolled)}


def _mark_inherited_casillas(
    context: str,
    *,
    payload: dict[str, object],
    label_origins: _LabelOrigins | None,
) -> dict[str, object]:
    """Give every inherited casilla the ``inherited_from`` marker naming the edition that last stated it.

    The marker is the label origins, the one record of where each row is
    stated, carried onto the typed row so a consumer can tell a stated row from
    an inherited one without re-deriving it. A row stated in this edition keeps
    the marker unset.

    Raises:
        RegistryLoadError: When any casilla row authors the marker, since only
            materialisation knows where a row is stated.
    """
    casillas = as_toml_array(payload.get(_INHERITED_SECTION)) or ()
    authored = sorted(
        str(table.get("id"))
        for row in casillas
        if (table := _as_toml_table(row)) is not None and _ROW_INHERITED_FROM_FIELD in table
    )
    if authored:
        raise RegistryLoadError(
            f"{context}: casillas {authored!r} author {_ROW_INHERITED_FROM_FIELD}, which the loader sets on the "
            "rows an edition inherits from its declared predecessor; remove it",
        )
    if label_origins is None:
        return payload
    if len(casillas) != len(label_origins):
        raise RegistryLoadError(
            f"{context}: label origins cover {len(label_origins)} of the edition's {len(casillas)} casillas",
        )
    marked = tuple(
        casilla
        if origin is None or (table := _as_toml_table(casilla)) is None
        else {**table, _ROW_INHERITED_FROM_FIELD: origin}
        for casilla, origin in zip(casillas, label_origins, strict=True)
    )
    return {**payload, _INHERITED_SECTION: marked}


def _raise_on_ambiguous_revision_identity(
    source_path: Path,
    *,
    modelo_id: str,
    revision_id: RevisionId,
    revision: ModeloRevision,
) -> None:
    prefix = f"{source_path}: modelo {modelo_id} revision {revision_id}"
    failures = revision_reference_identity_failures(prefix, revision)
    if failures:
        raise RegistryValidationError(
            "registry revision identity is ambiguous:\n" + "\n".join(f" - {failure}" for failure in failures),
        )


def _refuse_authored_export_refs(source_path: Path, revision_id: str, payload: Mapping[str, object]) -> None:
    """Refuse a casilla row that declares ``export_refs``, which the loader derives from the layouts."""
    rows = as_toml_array(payload.get(_INHERITED_SECTION, ())) or ()
    authored = sorted(
        str(table.get("id"))
        for row in rows
        if (table := _as_toml_table(row)) is not None and _EXPORT_REFS_FIELD in table
    )
    if authored:
        raise RegistryLoadError(
            f"{source_path}: revision {revision_id!r} casillas {authored!r} declare export_refs; a casilla's "
            "export references are derived from the export fields that resolve to it, so remove the key",
        )


def _with_derived_export_refs(
    source_path: Path,
    revision: ModeloRevision,
    payload: Mapping[str, object],
) -> ModeloRevision:
    """Return ``revision`` with every casilla's ``export_refs`` derived from the edition's own layouts.

    The derivation runs on the materialised edition, so an inherited row takes
    the references of the layout it now sits beside and never its origin's.
    Each re-derived row is constructed again from its enrolled payload, so the
    casilla's own coherence rules see the derived value exactly as they would
    an authored one.
    """
    try:
        derived = derive_casilla_export_refs(revision.export_layouts, revision.bindings)
    except RegistryValidationError as exc:
        raise RegistryLoadError(f"{source_path}: invalid revision {revision.id!r}: {exc}") from exc
    if not derived:
        return revision
    declared = {casilla.id for casilla in revision.casillas}
    undeclared = sorted(casilla_id for casilla_id in derived if casilla_id not in declared)
    if undeclared:
        raise RegistryLoadError(
            f"{source_path}: invalid revision {revision.id!r}: export fields resolve to casillas {undeclared!r}, "
            "which the edition does not declare",
        )
    rows = as_toml_array(payload.get(_INHERITED_SECTION, ())) or ()
    casillas = []
    for casilla, row in zip(revision.casillas, rows, strict=True):
        refs = derived.get(casilla.id)
        table = _as_toml_table(row)
        if refs is None or table is None:
            casillas.append(casilla)
            continue
        try:
            casillas.append(CasillaDefinition.model_validate({**table, _EXPORT_REFS_FIELD: refs}))
        except ValidationError as exc:
            raise RegistryLoadError(f"{source_path}: invalid revision {revision.id!r}: {exc}") from exc
    return revision.model_copy(update={_INHERITED_SECTION: tuple(casillas)})


def _passthrough_toml_row(raw: object) -> dict[str, object]:
    """Carry a non-table TOML row through unchanged, so validation still sees it.

    Enrolment adds locale identities; it is not a validator. A row that is not a
    table gets no derived key -- there is no id to derive one from -- but it must
    still reach ``model_validate``, which is what turns a malformed fragment into
    an attributable error. Dropping it here would make it vanish silently
    instead.
    """
    # CAST-RATIONALE-TOML-ROW: raw TOML value, shape confirmed by the isinstance
    # guard in the same expression. One site rather than the three near-identical
    # copies this replaces, so the escape hatch is declared once.
    # nosemgrep: no-cast-in-domain-application
    return dict(cast(Mapping[str, object], raw)) if isinstance(raw, Mapping) else {"value": raw}


def _compile_revision_projection_record(source_path: Path, raw_record: object) -> dict[str, object]:
    record = _as_toml_table(raw_record)
    if record is None:
        return _passthrough_toml_row(raw_record)
    compiled = dict(record)
    fields = as_toml_array(record.get("fields"))
    if fields is not None:
        compiled["fields"] = tuple(compile_export_semantic_field(source_path, raw_field) for raw_field in fields)
    return compiled


def _compile_revision_projection_layout(source_path: Path, raw_layout: object) -> dict[str, object]:
    layout = _as_toml_table(raw_layout)
    if layout is None:
        return _passthrough_toml_row(raw_layout)
    compiled = dict(layout)
    records = as_toml_array(layout.get("records"))
    if records is not None:
        compiled["records"] = tuple(
            _compile_revision_projection_record(source_path, raw_record) for raw_record in records
        )
    return compiled


def _compile_revision_projection_semantics(source_path: Path, payload: Mapping[str, object]) -> dict[str, object]:
    """Compile revision-owned typed tokens before schema construction."""
    compiled = dict(payload)
    declarations = as_toml_array(payload.get("projection_endpoints"))
    if declarations is not None:
        compiled["projection_endpoints"] = tuple(
            compile_projection_endpoint_declaration(source_path, raw_declaration) for raw_declaration in declarations
        )
    layouts = as_toml_array(payload.get("export_layouts"))
    if layouts is not None:
        compiled["export_layouts"] = tuple(
            _compile_revision_projection_layout(source_path, raw_layout) for raw_layout in layouts
        )
    return compiled


@lru_cache(maxsize=64)
def _load_modelo_directory_cached(
    directory: str,
    fingerprints: _RegistryPathFingerprints,
    tax_id_format: object | None = None,
) -> ModeloDefinition:
    del fingerprints
    resolved = Path(directory)
    manifest_data = _load_modelo_manifest(resolved)
    merged_revisions = _load_modelo_revisions(resolved)
    if not merged_revisions:
        raise RegistryLoadError(f"{resolved}: no revisions found in revisions/")
    merged: dict[str, object] = {**manifest_data, "revisions": merged_revisions}
    validation_context = None
    if tax_id_format is not None:
        from cadrumo.core.identity.documents import TAX_ID_FORMAT_CONTEXT

        validation_context = {TAX_ID_FORMAT_CONTEXT: tax_id_format}
    return _build_modelo_definition_from_data(resolved, merged, validation_context=validation_context)


def _load_modelo_manifest(resolved: Path) -> dict[str, object]:
    """Load the directory-mode manifest.toml and reject inlined [revisions]."""
    manifest_path = resolved / "manifest.toml"
    manifest_data = freeze_toml(read_toml(manifest_path, error_factory=RegistryLoadError))
    if "revisions" in manifest_data:
        raise RegistryLoadError(
            f"{manifest_path}: directory-mode manifest must not declare [revisions]; "
            "revision data lives in revisions/<id>/revision.toml",
        )
    return manifest_data


def _load_modelo_revisions(resolved: Path) -> dict[str, object]:
    """Merge every ``revisions/<id>/`` fragment directory into one ``{revision_id: raw}`` map.

    A missing ``revisions/`` directory returns an empty dict; the caller raises
    if no revisions land. Each revision directory contributes its
    ``revision.toml`` metadata plus its section fragments under the directory's
    own id.
    """
    revisions_dir = resolved / "revisions"
    if not revisions_dir.is_dir():
        return {}
    merged_revisions: dict[str, object] = {}
    for path in scan_directory(revisions_dir, select=DirectoryEntryKind.FILES):
        raise RegistryLoadError(
            f"{path}: revision files are not a supported layout; "
            "each revision must be a revisions/<id>/ directory containing revision.toml",
        )
    for path in scan_directory(revisions_dir, select=DirectoryEntryKind.DIRECTORIES):
        _merge_revision_directory(path, merged_revisions)
    return merged_revisions


def _merge_revision_directory(path: Path, merged_revisions: dict[str, object]) -> None:
    """Merge a ``revisions/{id}/`` fragment tree into ``merged_revisions``."""
    revision_id = path.name
    if revision_id in merged_revisions:
        raise RegistryLoadError(f"{path}: revision {revision_id!r} is declared more than once")
    revision_manifest = path / "revision.toml"
    if not revision_manifest.is_file():
        raise RegistryLoadError(f"{path}: revision fragment directory must contain revision.toml")
    section_fragments = revision_section_fragment_paths(_revision_section_directories(path))
    merged_revision: dict[str, object] = {}
    _merge_revision_manifest(revision_manifest, revision_id, merged_revision)
    for fragment_path in section_fragments:
        _merge_revision_fragment(fragment_path, revision_id, merged_revision)
    merged_revisions[revision_id] = merged_revision


def _revision_section_directories(path: Path) -> tuple[Path, ...]:
    # require_root: the caller has already resolved this revision fragment
    # directory and read its revision.toml, so an unreadable path here is a
    # broken tree, not an empty revision. Silently returning no sections would
    # compile a revision with none of its casillas.
    return tuple(
        entry
        for entry in scan_directory(path, select=DirectoryEntryKind.DIRECTORIES, require_root=True)
        if entry.name != "locales"
    )


@lru_cache(maxsize=128)
def _load_catalogue_file_cached(
    path: str,
    byte_count: int,
    modified_ns: int,
    content_digest: str,
) -> RegistryCatalogues:
    del byte_count, modified_ns, content_digest
    source_path = Path(path)
    data = freeze_toml(read_toml(source_path, error_factory=RegistryLoadError))
    if "parameters" in data:
        raise RegistryLoadError(
            f"{source_path}: retired global [parameters] catalogue section is forbidden; "
            "author a governed fact instead",
        )
    legal = _validate_catalogue_section(
        source_path,
        raw=data.get("legal"),
        kind="legal reference",
        model=LegalReference,
    )
    sources = _validate_catalogue_section(
        source_path,
        raw=data.get("sources") or data.get("source"),
        kind="source reference",
        model=SourceReference,
    )
    supported_filing_years = None
    raw_supported_filing_years = data.get("supported_filing_years")
    if raw_supported_filing_years is not None:
        try:
            supported_filing_years = SupportedFilingYearsCatalogue.model_validate(raw_supported_filing_years)
        except ValidationError as exc:
            raise RegistryLoadError(f"{source_path}: invalid supported_filing_years catalogue: {exc}") from exc
    sociedades_annual_manual_coverage = None
    raw_sociedades_annual_manual_coverage = data.get("sociedades_annual_manual_coverage")
    if raw_sociedades_annual_manual_coverage is not None:
        try:
            sociedades_annual_manual_coverage = SociedadesAnnualManualCoverageCatalogue.model_validate(
                raw_sociedades_annual_manual_coverage,
            )
        except ValidationError as exc:
            raise RegistryLoadError(
                f"{source_path}: invalid sociedades_annual_manual_coverage catalogue: {exc}",
            ) from exc
    return RegistryCatalogues(
        legal=legal,
        sources=sources,
        supported_filing_years=supported_filing_years,
        sociedades_annual_manual_coverage=sociedades_annual_manual_coverage,
    )


def _validate_catalogue_section[T: BaseModel](
    source_path: Path,
    *,
    raw: object,
    kind: str,
    model: type[T],
) -> dict[str, T]:
    """Validate one ``{id: payload}`` section of a catalogue TOML into typed records.

    Returns an empty dict when ``raw`` is not a dict (the section is
    absent or malformed at the top level — the absent case is
    legitimate for catalogues that don't declare every section).
    Each ``(id, payload)`` pair is fed through ``model.model_validate``
    with ``id`` injected; type-shape errors raise the typed
    ``RegistryLoadError`` envelope so the catalogue loader's failure
    mode stays uniform across the legal and source sections.
    """
    table = _as_toml_table(raw)
    if table is None:
        return {}
    out: dict[str, T] = {}
    for ref_id, payload in table.items():
        payload_table = _as_toml_table(payload)
        if payload_table is None:
            raise RegistryLoadError(f"{source_path}: malformed {kind} entry")
        try:
            out[ref_id] = model.model_validate({"id": ref_id, **payload_table})
        except ValidationError as exc:
            raise RegistryLoadError(f"{source_path}: invalid {kind} {ref_id!r}: {exc}") from exc
    return out


def _validate_legal_directory(legal_dir: Path) -> None:
    """Require the shared legal catalogue to remain one flat TOML directory."""
    if not legal_dir.is_dir():
        return
    for entry in scan_directory(legal_dir):
        if entry.is_dir():
            raise RegistryLoadError(f"{entry}: unrecognized legal directory; legal catalogues must be flat")
        if not entry.is_file() or entry.suffix != ".toml":
            raise RegistryLoadError(
                f"{entry}: unrecognized legal catalogue file; legal catalogues must use the '.toml' suffix",
            )


def _refresh_modelo_directory_fingerprints_after_load_error(
    resolved: Path,
    initial_error: RegistryLoadError,
) -> _RegistryPathFingerprints:
    try:
        return collect_modelo_directory_fingerprints(resolved)
    except RegistryLoadError as refresh_error:
        raise RegistryLoadError(
            f"{resolved}: modelo directory changed during load. "
            f"Initial failure: {initial_error}; refresh failure: {refresh_error}",
            registry_failure=RegistryFailureClassification(
                condition=RegistryFailureCondition.TREE_QUIESCENT,
                facts={
                    "path": str(resolved),
                    "registry_tree_quiescent": False,
                    "operation": "modelo_directory_refresh",
                },
            ),
        ) from refresh_error


def _refresh_registry_tree_fingerprints_after_load_error(
    resolved: Path,
    initial_error: RegistryLoadError,
) -> _RegistryPathFingerprints:
    try:
        return collect_registry_tree_fingerprints(resolved, use_cache=False)
    except RegistryLoadError as refresh_error:
        raise RegistryLoadError(
            f"{resolved}: registry tree changed during load. "
            f"Initial failure: {initial_error}; refresh failure: {refresh_error}",
            registry_failure=RegistryFailureClassification(
                condition=RegistryFailureCondition.TREE_QUIESCENT,
                facts={"path": str(resolved), "registry_tree_quiescent": False, "operation": "registry_tree_refresh"},
            ),
        ) from refresh_error


def _toml_fingerprint(path: Path) -> _RegistryPathFingerprint:
    """Return the ``(path, size, mtime_ns, content_digest)`` fingerprint for one TOML file.

    Delegates to :func:`~dev.registry.compiler.loader_cache.toml_file_fingerprint`,
    the shared primitive that makes mutable-tree fingerprints content-sensitive
    (a same-size, same-mtime rewrite still re-keys every cache above the
    loader) while the read-only bundled tree keeps the cheap stat-only form.
    """
    return toml_file_fingerprint(path)


#: This module's docstring already states the boundary this enforces: a
#: caller OUTSIDE the package cannot bind to a compilation step or cache this
#: module does not promise. Within the package, :mod:`loader` is the one
#: sanctioned consumer of the compilation internals below, so this lists every
#: name it (and the module's own test suite) actually reaches across the
#: module boundary -- never a wildcard, and never widened to symbols nothing
#: outside this file uses.
__all__ = [
    "_RegistryPathFingerprints",
    "_load_catalogue_file_cached",
    "_load_modelo_directory_cached",
    "_refresh_modelo_directory_fingerprints_after_load_error",
    "_refresh_registry_tree_fingerprints_after_load_error",
    "_toml_fingerprint",
    "_validate_legal_directory",
]
