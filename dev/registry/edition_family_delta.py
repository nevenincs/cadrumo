"""Collapse keyed declaration families for any modelo candidate.

Each keyed family an edition states is rewritten as the storage delta the
loader applies against the edition's family baseline, and the candidate is
accepted only when every edition hydrates exactly as the source did. Four rules
decide what the delta holds:

- **The baseline is the one the authored tree names.** A named predecessor,
  then a family storage baseline, decide it as the loader does. A casilla
  storage baseline the author declared alone is a decision about casillas and
  leaves the families as authored; only an edition that declared no ancestry at
  all takes the baseline the casilla pass has just planned for it.
- **A per-edition sequence is stated, not overridden.** An export layout's
  records transcribe one official record design. A layout whose records differ
  from its baseline stays stated whole in the edition rather than folded into
  an override that removes the baseline's records and re-adds them; an existing
  override of that kind is turned back into the stated layout.
- **A period is never removed twice.** The loader withholds a period-scoped
  member the edition does not file on every edge, so no removal is written for
  one, and an existing removal of one is dropped as redundant.
- **Order is restored with the fewest positions.** The members already in the
  target order are left in place and every other one is moved once, so the
  family's positions are the minimal set for the loader's sequential moves, not
  a greedy set appended to positions already declared.
"""

from __future__ import annotations

import hashlib
import shutil
from collections.abc import Mapping, MutableMapping, Sequence
from pathlib import Path
from types import MappingProxyType
from typing import Final

import tomlkit

from cadrumo.core.toml import render_toml
from cadrumo.domain.calculations.registry.cleared_families import cleared_family_names
from cadrumo.domain.calculations.registry.errors import RegistryLoadError
from cadrumo.domain.calculations.registry.keyed_families import (
    KEYED_FAMILY_SPECS,
    KeyedFamilySpec,
    family_source_default_fields,
    inline_family_source_default,
)
from cadrumo.domain.calculations.registry.revision_order import ordered_revisions
from dev.registry.compiler.edition_materialisation import materialise_edition
from dev.registry.compiler.loader import inherit_keyed_family, load_modelo_declarations, load_modelo_directory
from dev.registry.compiler.loader_materialisation import selector_covers

__all__ = [
    "STATED_WHOLE_SEQUENCES",
    "collapse_keyed_families",
    "minimal_positions",
    "restates_stated_whole_sequence",
]

_REPRESENTATION_FIELDS = {
    "inherited_from",
    "casillas",
    "predecessor",
    "casilla_source_refs",
    "casilla_storage_baseline",
    "casilla_overrides",
    "casilla_removals",
    "casilla_positions",
    "lineage_attestations",
    "family_storage_baseline",
    "family_overrides",
    "family_removals",
    "family_positions",
    "cleared_families",
    "scoped_families",
    "restated_families",
    # An edition-level ``<family>_source_refs`` only defaults its members'
    # ``source_refs``; the hydrated members carry the resolved references, so
    # lifting a shared run into the default changes representation, not meaning.
    *(field for _section, field in family_source_default_fields(include_casillas=True)),
}

#: Per family, the member sequence each edition states for itself. An export
#: layout's records are one official record design transcribed; an edition
#: whose records differ states its layout, because an override could only
#: remove the baseline's records and re-add every record of its own.
STATED_WHOLE_SEQUENCES: Final[Mapping[str, str]] = MappingProxyType({"export_layouts": "records"})

_FRAGMENT_NAME: Final = "0001-declarations.toml"


def restates_stated_whole_sequence(section: str, operation: Mapping[str, object]) -> bool:
    """Whether a family override rewrites a sequence its family states whole per edition."""
    sequence = STATED_WHOLE_SEQUENCES.get(section)
    if sequence is None:
        return False
    paths: list[str] = []
    fields = operation.get("fields")
    if isinstance(fields, Mapping):
        paths.extend(str(key) for key in fields)
    removed = operation.get("removed_fields")
    if isinstance(removed, list | tuple):
        paths.extend(str(path) for path in removed)
    for key in ("sequence_additions", "sequence_removals", "sequence_order"):
        value = operation.get(key)
        if isinstance(value, Mapping):
            paths.extend(str(path) for path in value)
    return any(path == sequence or path.startswith(f"{sequence}.") for path in paths)


def _digest(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def _effective(value: object) -> object:
    if isinstance(value, Mapping):
        return {key: _effective(item) for key, item in value.items() if key not in _REPRESENTATION_FIELDS}
    if isinstance(value, list | tuple):
        return [_effective(item) for item in value]
    return value


def _plain(value: object) -> object:
    """A materialised value as plain dicts and lists, the shapes TOML writers accept."""
    if isinstance(value, Mapping):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [_plain(item) for item in value]
    return value


def _difference(
    left: Mapping[str, object], right: Mapping[str, object], *, identity: str
) -> tuple[dict[str, object], list[str], dict[str, list[object]], dict[str, list[int]], dict[str, list[int]]]:
    fields: dict[str, object] = {}
    removed: list[str] = []
    additions: dict[str, list[object]] = {}
    removals: dict[str, list[int]] = {}
    orders: dict[str, list[int]] = {}

    def visit(old: Mapping[str, object], new: Mapping[str, object], prefix: str = "") -> dict[str, object]:
        patch: dict[str, object] = {}
        for key in sorted(set(old) | set(new)):
            path = f"{prefix}.{key}" if prefix else key
            old_value = old.get(key)
            new_value = new.get(key)
            if not prefix and key == identity:
                continue
            if key not in new:
                removed.append(path)
            elif key not in old:
                patch[key] = new[key]
            elif isinstance(old_value, Mapping) and isinstance(new_value, Mapping):
                nested = visit(old_value, new_value, path)
                if nested:
                    patch[key] = nested
            elif isinstance(old_value, list | tuple) and isinstance(new_value, list | tuple):
                _sequence_difference(path, list(old_value), list(new_value), additions, removals, orders)
            elif old_value != new_value:
                patch[key] = new_value
        return patch

    fields.update(visit(left, right))
    return fields, removed, additions, removals, orders


def _sequence_difference(
    path: str,
    old: list[object],
    new: list[object],
    additions: dict[str, list[object]],
    removals: dict[str, list[int]],
    orders: dict[str, list[int]],
) -> None:
    used_new: set[int] = set()
    kept: list[object] = []
    removed = []
    for old_index, item in enumerate(old):
        match = next(
            (index for index, candidate in enumerate(new) if index not in used_new and candidate == item), None
        )
        if match is None:
            removed.append(old_index)
        else:
            used_new.add(match)
            kept.append(item)
    added = [item for index, item in enumerate(new) if index not in used_new]
    natural = [*kept, *added]
    used_natural: set[int] = set()
    order: list[int] = []
    for item in new:
        index = next(i for i, candidate in enumerate(natural) if i not in used_natural and candidate == item)
        used_natural.add(index)
        order.append(index)
    if removed:
        removals[path] = removed
    if added:
        additions[path] = added
    if order != list(range(len(natural))):
        orders[path] = order


def _longest_ordered_run(sequence: Sequence[int]) -> set[int]:
    """Indexes into ``sequence`` of one longest strictly increasing subsequence, chosen deterministically."""
    tails: list[int] = []
    previous: list[int | None] = [None] * len(sequence)
    for index, value in enumerate(sequence):
        low, high = 0, len(tails)
        while low < high:
            middle = (low + high) // 2
            if sequence[tails[middle]] < value:
                low = middle + 1
            else:
                high = middle
        previous[index] = tails[low - 1] if low > 0 else None
        if low == len(tails):
            tails.append(index)
        else:
            tails[low] = index
    kept: set[int] = set()
    cursor = tails[-1] if tails else None
    while cursor is not None:
        kept.add(cursor)
        cursor = previous[cursor]
    return kept


def minimal_positions(natural: Sequence[str], target: Sequence[str], *, subject: str) -> tuple[tuple[str, int], ...]:
    """The fewest ``(identity, position)`` moves that turn ``natural`` into ``target``.

    The loader applies positions one after another, each removing its member
    and inserting it at the stated index. Members already in target order - one
    longest run of them - never move; every other member moves once, in target
    order, to just after the nearest member already where it belongs. No set of
    moves is smaller, since every member left unmoved keeps its relative order.
    """
    if sorted(natural) != sorted(target) or len(set(target)) != len(target):
        raise RuntimeError(f"{subject}: merge order {list(natural)!r} is not a permutation of {list(target)!r}")
    target_index = {identity: index for index, identity in enumerate(target)}
    settled = {natural[index] for index in _longest_ordered_run([target_index[identity] for identity in natural])}
    working = list(natural)
    moves: list[tuple[str, int]] = []
    for index, identity in enumerate(target):
        if identity in settled:
            continue
        working.remove(identity)
        anchor = next((target[earlier] for earlier in range(index - 1, -1, -1) if target[earlier] in settled), None)
        position = 0 if anchor is None else working.index(anchor) + 1
        working.insert(position, identity)
        settled.add(identity)
        moves.append((identity, position))
    if working != list(target):
        raise RuntimeError(f"{subject}: minimal positions do not reconstruct the family order")
    return tuple(moves)


def _payload_field_count(value: object) -> int:
    if isinstance(value, Mapping):
        return sum(_payload_field_count(item) for item in value.values())
    if isinstance(value, list | tuple):
        return sum(_payload_field_count(item) for item in value)
    return 1


def _remove_members(
    revision_dir: Path,
    revision_id: str,
    family: str,
    keep: set[str],
    identity: str,
    *,
    singleton: bool,
) -> None:
    section_dir = revision_dir / family
    if not section_dir.is_dir():
        return
    if singleton and not keep:
        for path in section_dir.glob("*.toml"):
            path.unlink()
        section_dir.rmdir()
        return
    for path in sorted(section_dir.glob("*.toml")):
        document = tomlkit.parse(path.read_text(encoding="utf-8"))
        members = document["revisions"][revision_id][family]
        retained = [member for member in members if str(member.get(identity)) in keep]
        if retained:
            members.clear()
            members.extend(retained)
            path.write_text(tomlkit.dumps(document), encoding="utf-8", newline="\n")
        else:
            path.unlink()
    if section_dir.is_dir() and not any(section_dir.iterdir()):
        section_dir.rmdir()


def _state_members(revision_dir: Path, revision_id: str, family: str, members: Sequence[Mapping[str, object]]) -> None:
    """State ``members`` in the family's fragment, appending to the one already authored."""
    section_dir = revision_dir / family
    fragments = sorted(section_dir.glob("*.toml")) if section_dir.is_dir() else []
    if not fragments:
        section_dir.mkdir(exist_ok=True)
        (section_dir / _FRAGMENT_NAME).write_text(
            render_toml({"revisions": {revision_id: {family: [_plain(member) for member in members]}}}),
            encoding="utf-8",
            newline="\n",
        )
        return
    path = fragments[0]
    document = tomlkit.parse(path.read_text(encoding="utf-8"))
    stated = document["revisions"][revision_id][family]
    for member in members:
        stated.append(tomlkit.item(_plain(member)))
    path.write_text(tomlkit.dumps(document), encoding="utf-8", newline="\n")


def _table(value: Mapping[str, object]) -> object:
    table = tomlkit.inline_table()
    for key, item in value.items():
        table[key] = item
    return table


def _authored_member_order(revision_dir: Path, revision_id: str, family: str, identity: str) -> list[str]:
    """Return identities physically stated in one family directory, in the order the loader reads them."""
    identities: list[str] = []
    for path in sorted((revision_dir / family).glob("*.toml")):
        document = tomlkit.parse(path.read_text(encoding="utf-8"))
        value = document["revisions"][revision_id][family]
        members = (value,) if isinstance(value, Mapping) else value
        identities.extend(str(member[identity]) for member in members)
    return identities


def _restated_sections(revision: Mapping[str, object]) -> set[str]:
    """Return the keyed families one edition restates in full rather than inherits."""
    declared = revision.get("restated_families") or ()
    if not isinstance(declared, list | tuple):
        return set()
    return {str(entry["family"]) for entry in declared if isinstance(entry, Mapping) and "family" in entry}


def _drop_restatement(revision: MutableMapping[str, object], section: str) -> None:
    """Remove one family's restatement, and the declaration once it restates nothing."""
    declared = revision["restated_families"]
    if not isinstance(declared, list):
        raise RuntimeError(f"restated_families is not an array while lifting {section!r}")
    retained = [entry for entry in declared if not (isinstance(entry, Mapping) and entry.get("family") == section)]
    if retained:
        declared.clear()
        declared.extend(retained)
    else:
        del revision["restated_families"]


def _family_baseline(authored: Mapping[str, object], planned: Mapping[str, object]) -> str | None:
    """The edition a revision's keyed families are stored against, or ``None`` when they stay as authored.

    The authored tree decides, in the loader's order: a named predecessor, then
    a family storage baseline. A casilla storage baseline declared alone is the
    author's decision about casillas, and the families stay as authored. Only an
    edition that declared no ancestry at all takes the one the casilla pass has
    just planned for it.
    """
    for key in ("predecessor", "family_storage_baseline"):
        value = authored.get(key)
        if isinstance(value, str):
            return value
    if isinstance(authored.get("casilla_storage_baseline"), str):
        return None
    for key in ("predecessor", "family_storage_baseline", "casilla_storage_baseline"):
        value = planned.get(key)
        if isinstance(value, str):
            return value
    return None


def _family_members(table: Mapping[str, object], spec: KeyedFamilySpec) -> tuple[Mapping[str, object], ...]:
    raw = table.get(spec.section)
    candidates: tuple[object, ...] = (raw,) if spec.singleton else tuple(raw) if isinstance(raw, list | tuple) else ()
    members: list[Mapping[str, object]] = []
    for item in candidates:
        if isinstance(item, Mapping):
            members.append({str(key): value for key, value in item.items()})
    return tuple(members)


def _selector_id(operation: object) -> str | None:
    selector = operation.get("selector") if isinstance(operation, Mapping) else None
    member = selector.get("id") if isinstance(selector, Mapping) else None
    return None if member is None else str(member)


def _replace_operations(operations: list[object], retained: Sequence[object]) -> bool:
    """Keep only ``retained`` in ``operations``; return whether anything was dropped."""
    if len(retained) == len(operations):
        return False
    kept = list(retained)
    operations.clear()
    operations.extend(kept)
    return True


def collapse_keyed_families(source: Path, candidate: Path) -> dict[str, object]:
    """Collapse every eligible keyed family and prove hydrated equality."""
    if not candidate.exists():
        shutil.copytree(source, candidate)
    from dev.registry.edition_delta_migration import assess_migration_state

    source_digest = _digest(source)
    initial = assess_migration_state(source)
    if initial.minimal:
        digest = _digest(candidate)
        return {"source_digest": source_digest, "candidate_digest": digest, "by_revision_family": []}
    before = load_modelo_directory(source)
    source_declarations = load_modelo_declarations(source)
    source_raw = source_declarations["revisions"]
    if not isinstance(source_raw, Mapping):
        raise RuntimeError(f"modelo {before.id} revisions are not a mapping")
    resolved = {revision_id: materialise_edition(source, revision_id).table for revision_id in before.revisions}
    # Baseline declarations come from the candidate because the casilla pass
    # may just have introduced its predecessor. Effective family values and
    # order come from the untouched source captured before that representation
    # change.
    candidate_declarations = load_modelo_declarations(candidate)
    candidate_raw = candidate_declarations["revisions"]
    if not isinstance(candidate_raw, Mapping):
        raise RuntimeError(f"modelo {before.id} candidate revisions are not a mapping")
    # The typed loader is the consumer contract, including its final member
    # ordering. Raw declarations below are used only to discover each explicit
    # storage baseline; their family union order is not authoritative.
    counts: list[dict[str, object]] = []
    for typed_revision in ordered_revisions(before):
        revision_id = str(typed_revision.id)
        raw_current = candidate_raw[revision_id]
        authored_current = source_raw.get(revision_id)
        if not isinstance(raw_current, Mapping) or not isinstance(authored_current, Mapping):
            raise RuntimeError(f"revision {revision_id} is not a mapping")
        predecessor_id = _family_baseline(authored_current, raw_current)
        if predecessor_id is None:
            continue
        current = resolved[revision_id]
        predecessor = resolved[predecessor_id]
        if not isinstance(current, Mapping) or not isinstance(predecessor, Mapping):
            raise RuntimeError(f"revision {revision_id} or its baseline {predecessor_id} is not a mapping")
        revision_dir = candidate / "revisions" / revision_id
        manifest_path = revision_dir / "revision.toml"
        manifest = tomlkit.parse(manifest_path.read_text(encoding="utf-8"))
        revision = manifest["revisions"][revision_id]
        overrides = revision.get("family_overrides") or tomlkit.aot()
        removals = revision.get("family_removals") or tomlkit.aot()
        positions = revision.get("family_positions") or tomlkit.aot()
        restated_sections = _restated_sections(revision)
        scoped_families = list(revision.get("scoped_families", ()))
        scoped_sections = {spec.section for spec in KEYED_FAMILY_SPECS if spec.scoped}
        operated_sections = {
            str(operation.get("family"))
            for operations in (overrides, removals, positions)
            for operation in operations
            if isinstance(operation, Mapping) and operation.get("family") is not None
        } | cleared_family_names(revision.get("cleared_families", ()))
        missing_scopes = sorted((operated_sections & scoped_sections) - set(scoped_families))
        scoped_families.extend(missing_scopes)
        revision_changed = bool(missing_scopes)
        period_selector = current.get("period_selector")
        for spec in KEYED_FAMILY_SPECS:
            if not spec.period_scoped or spec.identity is None:
                continue
            baseline_members = {str(member.get(spec.identity)): member for member in _family_members(predecessor, spec)}
            # The loader withholds a baseline member of another period on
            # every edge, so a removal naming one removes nothing.
            revision_changed |= _replace_operations(
                removals,
                [
                    operation
                    for operation in removals
                    if not (
                        isinstance(operation, Mapping)
                        and operation.get("family") == spec.section
                        and (member := baseline_members.get(_selector_id(operation) or "")) is not None
                        and not selector_covers(period_selector, member)
                    )
                ],
            )
        for spec in KEYED_FAMILY_SPECS:
            section_dir = revision_dir / spec.section
            if spec.identity is None:
                continue
            new_raw = current.get(spec.section)
            new_members = (
                (new_raw,)
                if spec.singleton and isinstance(new_raw, Mapping)
                else tuple(new_raw)
                if isinstance(new_raw, list | tuple)
                else ()
            )
            restating = [
                operation
                for operation in overrides
                if isinstance(operation, Mapping)
                and operation.get("family") == spec.section
                and restates_stated_whole_sequence(spec.section, operation)
            ]
            if restating:
                # A per-edition sequence folded into an override is stated
                # again as the member it hydrates to; the family pass below
                # then treats it like any other stated member.
                by_identity = {str(member[spec.identity]): member for member in new_members}
                _state_members(
                    revision_dir,
                    revision_id,
                    spec.section,
                    [
                        by_identity[str(operation.get("replacement_id") or _selector_id(operation))]
                        for operation in restating
                    ],
                )
                restating_ids = {id(operation) for operation in restating}
                _replace_operations(
                    overrides, [operation for operation in overrides if id(operation) not in restating_ids]
                )
                revision_changed = True
            if not section_dir.is_dir():
                continue
            # A restated family inherits nothing, so collapsing its members
            # without also lifting the restatement would delete them. The
            # restatement is converted into the ordinary delta instead: the
            # predecessor-only members become explicit removals below, and the
            # closing equality check proves the hydrated family unchanged.
            if spec.section in restated_sections:
                _drop_restatement(revision, spec.section)
                revision_changed = True
            old_members = _family_members(predecessor, spec)
            typed_current_raw = typed_revision.model_dump(mode="python", exclude_none=True).get(spec.section)
            typed_current_members = (
                (typed_current_raw,)
                if spec.singleton and isinstance(typed_current_raw, Mapping)
                else tuple(typed_current_raw)
                if isinstance(typed_current_raw, list | tuple)
                else ()
            )
            typed_order = [str(item[spec.identity]) for item in typed_current_members]
            new_by_identity = {str(item[spec.identity]): item for item in new_members}
            if set(typed_order) == set(new_by_identity):
                new_members = tuple(new_by_identity[identity] for identity in typed_order)
            old = {
                str(item[spec.identity]): inline_family_source_default(item, predecessor, spec.source_default_key)
                for item in old_members
            }
            new = {
                str(item[spec.identity]): inline_family_source_default(item, current, spec.source_default_key)
                for item in new_members
            }
            authored_order = _authored_member_order(revision_dir, revision_id, spec.section, spec.identity)
            authored_ids = set(authored_order)
            replacements: dict[str, str] = {}
            if (spec.singleton or spec.period_scoped) and len(old) == len(new) == 1:
                replacements[next(iter(old))] = next(iter(new))
            # A declared rename keeps its member in place under the new identity.
            for operation in overrides:
                if not isinstance(operation, Mapping) or operation.get("family") != spec.section:
                    continue
                replacement_id = operation.get("replacement_id")
                member_id = _selector_id(operation)
                if replacement_id is not None and member_id is not None:
                    replacements[member_id] = str(replacement_id)
            additions = set(new) - set(old) - set(replacements.values())
            keep = set(additions)
            family_overrides = 0
            payload = 0
            sequence_addition_count = 0
            sequence_removal_count = 0
            sequence_order_count = 0
            common = {identity: identity for identity in set(old) & set(new)} | replacements
            existing_override_ids = {
                str(selector.get("id"))
                for operation in overrides
                if isinstance(operation, Mapping)
                and operation.get("family") == spec.section
                and isinstance((selector := operation.get("selector")), Mapping)
            }
            existing_removal_ids = {
                str(selector.get("id"))
                for operation in removals
                if isinstance(operation, Mapping)
                and operation.get("family") == spec.section
                and isinstance((selector := operation.get("selector")), Mapping)
            }
            overlap = authored_ids & existing_override_ids
            if overlap:
                raise RuntimeError(
                    f"revision {revision_id} family {spec.section} both states and overrides members "
                    f"{sorted(overlap)!r}; refusing an ambiguous collapse"
                )
            overrides_before = len(overrides)
            removals_before = len(removals)
            for identity, successor_identity in sorted(common.items()):
                if identity in existing_override_ids:
                    continue
                fields, removed, sequence_additions, sequence_removals, sequence_order = _difference(
                    old[identity], new[successor_identity], identity=spec.identity
                )
                if restates_stated_whole_sequence(
                    spec.section,
                    {
                        "fields": fields,
                        "removed_fields": removed,
                        "sequence_additions": sequence_additions,
                        "sequence_removals": sequence_removals,
                        "sequence_order": sequence_order,
                    },
                ):
                    keep.add(successor_identity)
                    continue
                reaffirm = False
                try:
                    inherit_keyed_family(
                        f"modelo {before.id} family conversion",
                        revision_id=revision_id,
                        predecessor_id=predecessor_id,
                        predecessor=predecessor,
                        section=spec.section,
                        identity=spec.identity,
                        identity_fields=spec.identity_fields,
                        casilla_identity_fields=spec.casilla_identity_fields,
                        period_scoped=spec.period_scoped,
                        inherited=(old[identity],),
                        inherited_casillas=tuple(
                            item.model_dump(mode="python") for item in before.revisions[predecessor_id].casillas
                        ),
                        successor_casillas=tuple(
                            item.model_dump(mode="python") for item in before.revisions[revision_id].casillas
                        ),
                        successor={spec.section: (new[successor_identity],)},
                    )
                except RegistryLoadError:
                    reaffirm = True
                if (
                    not any((fields, removed, sequence_additions, sequence_removals, sequence_order, reaffirm))
                    and successor_identity == identity
                ):
                    continue
                entry = tomlkit.table()
                entry["family"] = spec.section
                entry["selector"] = _table({"revision": predecessor_id, "id": identity})
                if successor_identity != identity:
                    entry["replacement_id"] = successor_identity
                if fields:
                    entry["fields"] = _table(fields)
                    payload += _payload_field_count(fields)
                if removed:
                    entry["removed_fields"] = removed
                if sequence_additions:
                    entry["sequence_additions"] = _table(sequence_additions)
                    payload += _payload_field_count(sequence_additions)
                    sequence_addition_count += sum(len(items) for items in sequence_additions.values())
                if sequence_removals:
                    entry["sequence_removals"] = _table(sequence_removals)
                    sequence_removal_count += sum(len(items) for items in sequence_removals.values())
                if sequence_order:
                    entry["sequence_order"] = _table(sequence_order)
                    sequence_order_count += sum(len(items) for items in sequence_order.values())
                if reaffirm:
                    entry["restate_identity"] = True
                overrides.append(entry)
                family_overrides += 1
            if spec.scoped and spec.section not in scoped_families and keep >= set(new):
                # The edition states this per-edition family whole and adopts
                # none of its baseline's members, which is what an unasserted
                # scope already means; asserting it only to remove every
                # baseline member again would store nothing.
                continue
            removed_identities = {
                identity
                for identity in set(old) - set(new) - set(replacements)
                if not (spec.period_scoped and not selector_covers(period_selector, old[identity]))
            }
            for identity in sorted(removed_identities):
                if identity in existing_removal_ids:
                    continue
                entry = tomlkit.table()
                entry["family"] = spec.section
                entry["selector"] = _table({"revision": predecessor_id, "id": identity})
                removals.append(entry)
            # The loader's order before positions: the baseline's members in
            # its order, each superseded or renamed in place, then the stated
            # new members in the order the fragments state them.
            stated_additions = [identity for identity in authored_order if identity in additions]
            natural = [
                replacements.get(str(item[spec.identity]), str(item[spec.identity]))
                for item in old_members
                if str(item[spec.identity]) in new or str(item[spec.identity]) in replacements
            ] + [
                *stated_additions,
                *(
                    str(item[spec.identity])
                    for item in new_members
                    if str(item[spec.identity]) in additions and str(item[spec.identity]) not in stated_additions
                ),
            ]
            moves = minimal_positions(
                natural,
                [str(item[spec.identity]) for item in new_members],
                subject=f"modelo {before.id} revision {revision_id} family {spec.section}",
            )
            declared_moves = [
                (str(operation.get("id")), operation.get("position"))
                for operation in positions
                if isinstance(operation, Mapping) and operation.get("family") == spec.section
            ]
            positions_changed = declared_moves != list(moves)
            if positions_changed:
                _replace_operations(
                    positions,
                    [
                        operation
                        for operation in positions
                        if not (isinstance(operation, Mapping) and operation.get("family") == spec.section)
                    ],
                )
                for identity, position in moves:
                    entry = tomlkit.table()
                    entry["family"] = spec.section
                    entry["id"] = identity
                    entry["position"] = position
                    positions.append(entry)
            removed_authored = authored_ids - keep
            if removed_authored:
                _remove_members(
                    revision_dir,
                    revision_id,
                    spec.section,
                    keep,
                    spec.identity,
                    singleton=spec.singleton,
                )
            content_changed = bool(
                removed_authored
                or len(overrides) != overrides_before
                or len(removals) != removals_before
                or positions_changed
            )
            scoped_added = spec.scoped and spec.section not in scoped_families and content_changed
            if scoped_added:
                scoped_families.append(spec.section)
            family_changed = content_changed or scoped_added
            revision_changed |= family_changed
            if family_changed:
                counts.append(
                    {
                        "revision": revision_id,
                        "family": spec.section,
                        "authored_payload_fields_before": sum(
                            _payload_field_count({key: value for key, value in item.items() if key != spec.identity})
                            for item in new.values()
                        ),
                        "authored_payload_fields_after": sum(
                            _payload_field_count(
                                {key: value for key, value in new[item].items() if key != spec.identity}
                            )
                            for item in keep
                        )
                        + payload,
                        "overrides": family_overrides,
                        "additions": len(additions),
                        "removals": len(removed_identities),
                        "sequence_additions": sequence_addition_count,
                        "sequence_removals": sequence_removal_count,
                        "sequence_order_positions": sequence_order_count,
                        "structural_overhead": (
                            2 * family_overrides
                            + 2 * len(removed_identities)
                            + 2 * len(moves)
                            + sequence_removal_count
                            + sequence_order_count
                        ),
                    }
                )
        if revision_changed:
            revision.setdefault("family_storage_baseline", predecessor_id)
        for key, operations in (
            ("family_overrides", overrides),
            ("family_removals", removals),
            ("family_positions", positions),
        ):
            if operations:
                revision[key] = operations
            elif key in revision:
                del revision[key]
        if scoped_families:
            revision["scoped_families"] = scoped_families
        if revision_changed:
            manifest_path.write_text(tomlkit.dumps(manifest), encoding="utf-8", newline="\n")
    after = load_modelo_directory(candidate)
    for revision_id in before.revisions:
        left = _effective(before.revisions[revision_id].model_dump(mode="json"))
        right = _effective(after.revisions[revision_id].model_dump(mode="json"))
        if left != right:
            if not isinstance(left, Mapping) or not isinstance(right, Mapping):
                raise RuntimeError(f"candidate changes hydrated revision {revision_id}; fields=['<root>']")
            differing = sorted(key for key in set(left) | set(right) if left.get(key) != right.get(key))
            raise RuntimeError(f"candidate changes hydrated revision {revision_id}; fields={differing!r}")
    return {"source_digest": source_digest, "candidate_digest": _digest(candidate), "by_revision_family": counts}
