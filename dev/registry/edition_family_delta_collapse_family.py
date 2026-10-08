"""Convert one inherited keyed family into its minimal authored delta."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

import tomlkit

from cadrumo.domain.calculations.registry.keyed_families import (
    KeyedFamilySpec,
    inline_family_source_default,
)
from cadrumo.domain.calculations.registry.schema import ModeloRevision
from dev.registry.compiler.keyed_family_period_scope import selector_covers

from .edition_family_delta import (
    _authored_member_order,
    _drop_restatement,
    _family_members,
    _payload_field_count,
    _remove_members,
    _replace_operations,
    _selector_id,
    _state_members,
    _table,
    restates_stated_whole_sequence,
)
from .edition_family_delta_collapse_overrides import _append_common_overrides, _skip_empty_scope
from .edition_family_delta_collapse_state import FamilyChange, FamilyCounts, FamilyState, RevisionState
from .edition_family_delta_difference import minimal_positions


def collapse_family(state: RevisionState, spec: KeyedFamilySpec) -> bool:
    """Rewrite one keyed family of a candidate revision as overrides, removals and positions; report a change.

    A family without an identity field has no members to match against its predecessor and is left as authored.
    """
    identity = spec.identity
    if identity is None:
        return False
    new_members = _raw_members(state.current, spec)
    _restore_sequence_restatements(state, spec, identity, new_members)
    section_dir = state.revision_dir / spec.section
    if not section_dir.is_dir():
        return False
    if spec.section in state.restated_sections:
        _drop_restatement(state.revision, spec.section)
        state.revision_changed = True
    family = _family_state(state, spec, identity, new_members)
    counts = FamilyCounts()
    _append_common_overrides(state, family, counts)
    if _skip_empty_scope(state, spec, family):
        return False
    removed_identities = _append_removals(state, family)
    moves, positions_changed = _restore_family_order(state, family)
    removed_authored = _remove_redundant_authored(state, family)
    changed = _family_content_changed(state, family, positions_changed, removed_authored)
    if changed:
        _record_family_change(state, family, counts, removed_identities, moves)
    state.revision_changed |= changed
    return changed


def _raw_members(table: Mapping[str, object], spec: KeyedFamilySpec) -> tuple[Mapping[str, object], ...]:
    raw = table.get(spec.section)
    if spec.singleton and isinstance(raw, Mapping):
        return (_string_keyed(raw),)
    if isinstance(raw, list | tuple):
        return tuple(_string_keyed(item) for item in raw if isinstance(item, Mapping))
    return ()


def _string_keyed(member: Mapping[object, object]) -> Mapping[str, object]:
    return {str(key): value for key, value in member.items()}


def _restore_sequence_restatements(
    state: RevisionState,
    spec: KeyedFamilySpec,
    identity: str,
    new_members: tuple[Mapping[str, object], ...],
) -> None:
    restating = [
        operation
        for operation in state.overrides
        if isinstance(operation, Mapping)
        and operation.get("family") == spec.section
        and restates_stated_whole_sequence(spec.section, operation)
    ]
    if not restating:
        return
    _state_restatements(state, spec, identity, new_members, restating)
    restating_ids = {id(operation) for operation in restating}
    retained = [operation for operation in state.overrides if id(operation) not in restating_ids]
    _replace_operations(state.overrides, retained)
    state.revision_changed = True


def _state_restatements(
    state: RevisionState,
    spec: KeyedFamilySpec,
    identity: str,
    new_members: tuple[Mapping[str, object], ...],
    restating: Sequence[Mapping[str, object]],
) -> None:
    by_identity = {str(member[identity]): member for member in new_members}
    members = [by_identity[str(operation.get("replacement_id") or _selector_id(operation))] for operation in restating]
    _state_members(state.revision_dir, state.revision_id, spec.section, members)


def _family_state(
    revision: RevisionState,
    spec: KeyedFamilySpec,
    identity: str,
    source_members: tuple[Mapping[str, object], ...],
) -> FamilyState:
    old_members = _family_members(revision.predecessor, spec)
    new_members, typed_order = _typed_members(revision.typed_revision, spec, identity, source_members)
    if set(typed_order) == {str(item[identity]) for item in new_members}:
        by_identity = {str(item[identity]): item for item in new_members}
        new_members = tuple(by_identity[member_id] for member_id in typed_order)
    old = _inlined_members(old_members, revision.predecessor, spec, identity)
    new = _inlined_members(new_members, revision.current, spec, identity)
    authored_order = _authored_member_order(revision.revision_dir, revision.revision_id, spec.section, identity)
    authored_ids = set(authored_order)
    replacements = _declared_replacements(revision, spec, old, new)
    additions = set(new) - set(old) - set(replacements.values())
    existing_override_ids = _operation_member_ids(revision.overrides, spec.section)
    existing_removal_ids = _operation_member_ids(revision.removals, spec.section)
    overlap = authored_ids & existing_override_ids
    if overlap:
        raise RuntimeError(
            f"revision {revision.revision_id} family {spec.section} both states and overrides members "
            f"{sorted(overlap)!r}; refusing an ambiguous collapse"
        )
    return FamilyState(
        spec=spec,
        identity=identity,
        old_members=old_members,
        new_members=new_members,
        old=old,
        new=new,
        authored_order=authored_order,
        authored_ids=authored_ids,
        replacements=replacements,
        additions=additions,
        keep=set(additions),
        common={member_id: member_id for member_id in set(old) & set(new)} | replacements,
        existing_override_ids=existing_override_ids,
        existing_removal_ids=existing_removal_ids,
        overrides_before=len(revision.overrides),
        removals_before=len(revision.removals),
    )


def _typed_members(
    revision: ModeloRevision,
    spec: KeyedFamilySpec,
    identity: str,
    source_members: tuple[Mapping[str, object], ...],
) -> tuple[tuple[Mapping[str, object], ...], list[str]]:
    raw = revision.model_dump(mode="python", exclude_none=True).get(spec.section)
    typed_members = _raw_members({spec.section: raw}, spec)
    typed_order = [str(item[identity]) for item in typed_members]
    return source_members, typed_order


def _inlined_members(
    members: tuple[Mapping[str, object], ...], table: Mapping[str, object], spec: KeyedFamilySpec, identity: str
) -> dict[str, Mapping[str, object]]:
    return {str(item[identity]): inline_family_source_default(item, table, spec.source_default_key) for item in members}


def _declared_replacements(
    revision: RevisionState,
    spec: KeyedFamilySpec,
    old: Mapping[str, Mapping[str, object]],
    new: Mapping[str, Mapping[str, object]],
) -> dict[str, str]:
    replacements: dict[str, str] = {}
    if (spec.singleton or spec.period_scoped) and len(old) == len(new) == 1:
        replacements[next(iter(old))] = next(iter(new))
    for operation in revision.overrides:
        if not isinstance(operation, Mapping) or operation.get("family") != spec.section:
            continue
        replacement_id = operation.get("replacement_id")
        member_id = _selector_id(operation)
        if replacement_id is not None and member_id is not None:
            replacements[member_id] = str(replacement_id)
    return replacements


def _operation_member_ids(operations: Sequence[object], section: str) -> set[str]:
    return {
        str(selector.get("id"))
        for operation in operations
        if isinstance(operation, Mapping)
        and operation.get("family") == section
        and isinstance((selector := operation.get("selector")), Mapping)
    }


def _append_removals(revision: RevisionState, family: FamilyState) -> set[str]:
    spec = family.spec
    removed = {
        identity
        for identity in set(family.old) - set(family.new) - set(family.replacements)
        if not (spec.period_scoped and not _period_covers(revision.period_selector, family.old[identity]))
    }
    for identity in sorted(removed):
        if identity in family.existing_removal_ids:
            continue
        entry = tomlkit.table()
        entry["family"] = spec.section
        entry["selector"] = _table({"revision": revision.predecessor_id, "id": identity})
        revision.removals.append(entry)
    return removed


def _period_covers(period_selector: object, member: Mapping[str, object]) -> bool:
    return selector_covers(period_selector, member)


def _restore_family_order(revision: RevisionState, family: FamilyState) -> tuple[tuple[tuple[str, int], ...], bool]:
    spec = family.spec
    stated_additions = [identity for identity in family.authored_order if identity in family.additions]
    natural = _natural_order(family, stated_additions)
    target = [str(item[family.identity]) for item in family.new_members]
    moves = minimal_positions(
        natural,
        target,
        subject=f"modelo {revision.before.id} revision {revision.revision_id} family {spec.section}",
    )
    declared = [
        (str(operation.get("id")), operation.get("position"))
        for operation in revision.positions
        if isinstance(operation, Mapping) and operation.get("family") == spec.section
    ]
    changed = declared != list(moves)
    if changed:
        _write_positions(revision, spec.section, moves)
    return moves, changed


def _natural_order(family: FamilyState, stated_additions: list[str]) -> list[str]:
    identity = family.identity
    inherited = [
        family.replacements.get(str(item[identity]), str(item[identity]))
        for item in family.old_members
        if str(item[identity]) in family.new or str(item[identity]) in family.replacements
    ]
    authored = [
        str(item[identity])
        for item in family.new_members
        if str(item[identity]) in family.additions and str(item[identity]) not in stated_additions
    ]
    return inherited + stated_additions + authored


def _write_positions(revision: RevisionState, section: str, moves: Sequence[tuple[str, int]]) -> None:
    retained = [
        operation
        for operation in revision.positions
        if not (isinstance(operation, Mapping) and operation.get("family") == section)
    ]
    _replace_operations(revision.positions, retained)
    for identity, position in moves:
        entry = tomlkit.table()
        entry["family"] = section
        entry["id"] = identity
        entry["position"] = position
        revision.positions.append(entry)


def _remove_redundant_authored(revision: RevisionState, family: FamilyState) -> set[str]:
    removed = family.authored_ids - family.keep
    if removed:
        _remove_members(
            revision.revision_dir,
            revision.revision_id,
            family.spec.section,
            family.keep,
            family.identity,
            singleton=family.spec.singleton,
        )
    return removed


def _family_content_changed(
    revision: RevisionState,
    family: FamilyState,
    positions_changed: bool,
    removed_authored: set[str],
) -> bool:
    return bool(
        removed_authored
        or len(revision.overrides) != family.overrides_before
        or len(revision.removals) != family.removals_before
        or positions_changed
    )


def _record_family_change(
    revision: RevisionState,
    family: FamilyState,
    counts: FamilyCounts,
    removed_identities: set[str],
    moves: Sequence[tuple[str, int]],
) -> None:
    change = _family_change(family, counts, removed_identities, moves)
    revision.counts.append(change.report(revision.revision_id, family.spec.section))
    if family.spec.scoped and family.spec.section not in revision.scoped_families:
        revision.scoped_families.append(family.spec.section)


def _family_change(
    family: FamilyState,
    counts: FamilyCounts,
    removed_identities: set[str],
    moves: Sequence[tuple[str, int]],
) -> FamilyChange:
    return FamilyChange(
        family_overrides=counts.overrides,
        additions=len(family.additions),
        removals=len(removed_identities),
        sequence_additions=counts.sequence_additions,
        sequence_removals=counts.sequence_removals,
        sequence_order_positions=counts.sequence_order,
        structural_overhead=(
            2 * counts.overrides
            + 2 * len(removed_identities)
            + 2 * len(moves)
            + counts.sequence_removals
            + counts.sequence_order
        ),
        authored_payload_fields_before=_payload_before(family),
        authored_payload_fields_after=_payload_after(family, counts),
    )


def _payload_before(family: FamilyState) -> int:
    identity = family.identity
    return sum(
        _payload_field_count({key: value for key, value in member.items() if key != identity})
        for member in family.new.values()
    )


def _payload_after(family: FamilyState, counts: FamilyCounts) -> int:
    identity = family.identity
    retained = sum(
        _payload_field_count({key: value for key, value in family.new[item].items() if key != identity})
        for item in family.keep
    )
    return retained + counts.payload


__all__ = ("collapse_family",)
