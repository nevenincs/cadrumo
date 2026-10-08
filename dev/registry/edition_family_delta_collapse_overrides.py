"""Build and append keyed-family overrides against their stored baseline."""

from __future__ import annotations

from collections.abc import Mapping, MutableMapping, Sequence

import tomlkit

from cadrumo.domain.calculations.registry.errors import RegistryLoadError
from cadrumo.domain.calculations.registry.keyed_families import KeyedFamilySpec
from dev.registry.compiler.keyed_family_inheritance import inherit_keyed_family

from .edition_family_delta import _payload_field_count, _table, restates_stated_whole_sequence
from .edition_family_delta_collapse_state import FamilyCounts, FamilyState, RevisionState
from .edition_family_delta_difference import _difference


def _append_common_overrides(revision: RevisionState, family: FamilyState, counts: FamilyCounts) -> None:
    for identity, successor_identity in sorted(family.common.items()):
        _append_member_override(revision, family, counts, identity, successor_identity)


def _append_member_override(
    revision: RevisionState,
    family: FamilyState,
    counts: FamilyCounts,
    identity: str,
    successor_identity: str,
) -> None:
    if identity in family.existing_override_ids:
        return
    spec = family.spec
    fields, removed, sequence_additions, sequence_removals, sequence_order = _difference(
        family.old[identity], family.new[successor_identity], identity=family.identity
    )
    if restates_stated_whole_sequence(
        spec.section, _sequence_operation(fields, removed, sequence_additions, sequence_removals, sequence_order)
    ):
        family.keep.add(successor_identity)
        return
    reaffirm = _needs_identity_reaffirmation(revision, family, identity, successor_identity)
    if _same_identity_without_delta(
        identity, successor_identity, fields, removed, sequence_additions, sequence_removals, sequence_order, reaffirm
    ):
        return
    entry = _override_entry(
        revision,
        family,
        identity,
        successor_identity,
        fields,
        removed,
        sequence_additions,
        sequence_removals,
        sequence_order,
        reaffirm,
        counts,
    )
    revision.overrides.append(entry)
    counts.overrides += 1


def _sequence_operation(
    fields: Mapping[str, object],
    removed: Sequence[str],
    additions: Mapping[str, list[object]],
    removals: Mapping[str, list[int]],
    order: Mapping[str, list[int]],
) -> Mapping[str, object]:
    return {
        "fields": fields,
        "removed_fields": removed,
        "sequence_additions": additions,
        "sequence_removals": removals,
        "sequence_order": order,
    }


def _needs_identity_reaffirmation(
    revision: RevisionState, family: FamilyState, identity: str, successor_identity: str
) -> bool:
    spec = family.spec
    member = family.new[successor_identity]
    try:
        inherit_keyed_family(
            f"modelo {revision.before.id} family conversion",
            revision_id=revision.revision_id,
            predecessor_id=revision.predecessor_id,
            predecessor=revision.predecessor,
            family=spec,
            inherited=(family.old[identity],),
            inherited_casillas=tuple(
                item.model_dump(mode="python") for item in revision.before.revisions[revision.predecessor_id].casillas
            ),
            successor_casillas=tuple(
                item.model_dump(mode="python") for item in revision.before.revisions[revision.revision_id].casillas
            ),
            # The successor states the member in the family's own shape: a
            # singleton family is one table, never an array of one.
            successor={spec.section: member if spec.singleton else (member,)},
        )
    except RegistryLoadError:
        return True
    return False


def _same_identity_without_delta(
    identity: str,
    successor_identity: str,
    fields: Mapping[str, object],
    removed: Sequence[str],
    additions: Mapping[str, list[object]],
    removals: Mapping[str, list[int]],
    order: Mapping[str, list[int]],
    reaffirm: bool,
) -> bool:
    return not any((fields, removed, additions, removals, order, reaffirm)) and successor_identity == identity


def _override_entry(
    revision: RevisionState,
    family: FamilyState,
    identity: str,
    successor_identity: str,
    fields: dict[str, object],
    removed: list[str],
    additions: dict[str, list[object]],
    removals: dict[str, list[int]],
    order: dict[str, list[int]],
    reaffirm: bool,
    counts: FamilyCounts,
) -> object:
    entry = tomlkit.table()
    entry["family"] = family.spec.section
    entry["selector"] = _table({"revision": revision.predecessor_id, "id": identity})
    if successor_identity != identity:
        entry["replacement_id"] = successor_identity
    _append_override_details(entry, fields, removed, additions, removals, order, reaffirm, counts)
    return entry


def _append_override_details(
    entry: MutableMapping[str, object],
    fields: Mapping[str, object],
    removed: Sequence[str],
    additions: Mapping[str, list[object]],
    removals: Mapping[str, list[int]],
    order: Mapping[str, list[int]],
    reaffirm: bool,
    counts: FamilyCounts,
) -> None:
    if fields:
        entry["fields"] = _table(fields)
        counts.payload += _payload_field_count(fields)
    if removed:
        entry["removed_fields"] = list(removed)
    if additions:
        entry["sequence_additions"] = _table(additions)
        counts.payload += _payload_field_count(additions)
        counts.sequence_additions += sum(len(items) for items in additions.values())
    if removals:
        entry["sequence_removals"] = _table(removals)
        counts.sequence_removals += sum(len(items) for items in removals.values())
    if order:
        entry["sequence_order"] = _table(order)
        counts.sequence_order += sum(len(items) for items in order.values())
    if reaffirm:
        entry["restate_identity"] = True


def _skip_empty_scope(revision: RevisionState, spec: KeyedFamilySpec, family: FamilyState) -> bool:
    return spec.scoped and spec.section not in revision.scoped_families and family.keep >= set(family.new)
