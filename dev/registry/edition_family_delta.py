"""Collapse keyed declaration families for any modelo candidate."""

from __future__ import annotations

import hashlib
import shutil
from collections.abc import Mapping, MutableMapping
from pathlib import Path

import tomlkit

from cadrumo.domain.calculations.registry.cleared_families import cleared_family_names
from cadrumo.domain.calculations.registry.errors import RegistryLoadError
from cadrumo.domain.calculations.registry.keyed_families import (
    KEYED_FAMILY_SPECS,
    family_source_default_fields,
    inline_family_source_default,
)
from cadrumo.domain.calculations.registry.revision_order import ordered_revisions
from dev.registry.compiler.edition_materialisation import materialise_edition
from dev.registry.compiler.loader import inherit_keyed_family, load_modelo_declarations, load_modelo_directory

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


def _table(value: Mapping[str, object]) -> object:
    table = tomlkit.inline_table()
    for key, item in value.items():
        table[key] = item
    return table


def _authored_member_ids(revision_dir: Path, revision_id: str, family: str, identity: str) -> set[str]:
    """Return identities physically stated in one family directory."""
    identities: set[str] = set()
    for path in sorted((revision_dir / family).glob("*.toml")):
        document = tomlkit.parse(path.read_text(encoding="utf-8"))
        value = document["revisions"][revision_id][family]
        members = (value,) if isinstance(value, Mapping) else value
        identities.update(str(member[identity]) for member in members)
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
        if not isinstance(raw_current, Mapping):
            raise RuntimeError(f"revision {revision_id} is not a mapping")
        raw_baseline = (
            raw_current.get("family_storage_baseline")
            or raw_current.get("casilla_storage_baseline")
            or raw_current.get("predecessor")
        )
        if not isinstance(raw_baseline, str):
            continue
        predecessor_id = raw_baseline
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
        existing_positions = {
            (str(operation.get("family")), str(operation.get("id")), operation.get("position"))
            for operation in positions
            if isinstance(operation, Mapping)
        }
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
        for spec in KEYED_FAMILY_SPECS:
            section_dir = revision_dir / spec.section
            if spec.identity is None or not section_dir.is_dir():
                continue
            # A restated family inherits nothing, so collapsing its members
            # without also lifting the restatement would delete them. The
            # restatement is converted into the ordinary delta instead: the
            # predecessor-only members become explicit removals below, and the
            # closing equality check proves the hydrated family unchanged.
            if spec.section in restated_sections:
                _drop_restatement(revision, spec.section)
                revision_changed = True
            old_raw = predecessor.get(spec.section)
            new_raw = current.get(spec.section)
            old_members = (
                (old_raw,)
                if spec.singleton and isinstance(old_raw, Mapping)
                else tuple(old_raw)
                if isinstance(old_raw, list | tuple)
                else ()
            )
            new_members = (
                (new_raw,)
                if spec.singleton and isinstance(new_raw, Mapping)
                else tuple(new_raw)
                if isinstance(new_raw, list | tuple)
                else ()
            )
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
            authored_ids = _authored_member_ids(revision_dir, revision_id, spec.section, spec.identity)
            replacements: dict[str, str] = {}
            if (spec.singleton or spec.period_scoped) and len(old) == len(new) == 1:
                replacements[next(iter(old))] = next(iter(new))
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
            positions_before = len(positions)
            for identity, successor_identity in sorted(common.items()):
                if identity in existing_override_ids:
                    continue
                fields, removed, sequence_additions, sequence_removals, sequence_order = _difference(
                    old[identity], new[successor_identity], identity=spec.identity
                )
                reaffirm = False
                try:
                    inherit_keyed_family(
                        f"modelo {before.id} family conversion",
                        revision_id=revision_id,
                        predecessor_id=predecessor_id,
                        predecessor=predecessor,
                        storage_only=True,
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
            removed_identities = set(old) - set(new) - set(replacements)
            for identity in sorted(removed_identities):
                if identity in existing_removal_ids:
                    continue
                entry = tomlkit.table()
                entry["family"] = spec.section
                entry["selector"] = _table({"revision": predecessor_id, "id": identity})
                removals.append(entry)
            effective_order = [str(item[spec.identity]) for item in new_members]
            natural = [
                replacements.get(str(item[spec.identity]), str(item[spec.identity]))
                for item in old_members
                if str(item[spec.identity]) in new or str(item[spec.identity]) in replacements
            ] + [str(item[spec.identity]) for item in new_members if str(item[spec.identity]) in additions]
            working = list(natural)
            family_position_count = 0
            for position, identity in enumerate(effective_order):
                if position < len(working) and working[position] == identity:
                    continue
                working.remove(identity)
                working.insert(position, identity)
                coordinate = (spec.section, identity, position)
                if coordinate in existing_positions:
                    continue
                entry = tomlkit.table()
                entry["family"] = spec.section
                entry["id"] = identity
                entry["position"] = position
                positions.append(entry)
                existing_positions.add(coordinate)
                family_position_count += 1
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
                or len(positions) != positions_before
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
                            for item in additions
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
                            + 2 * family_position_count
                            + sequence_removal_count
                            + sequence_order_count
                        ),
                    }
                )
        if revision_changed:
            revision.setdefault("family_storage_baseline", predecessor_id)
        if overrides:
            revision["family_overrides"] = overrides
        if removals:
            revision["family_removals"] = removals
        if positions:
            revision["family_positions"] = positions
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
