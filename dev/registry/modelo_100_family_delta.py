"""Stage a lossless keyed-family delta candidate for the live Modelo 100."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from collections.abc import Mapping
from pathlib import Path

import tomlkit

from cadrumo.domain.calculations.registry.errors import RegistryLoadError
from cadrumo.domain.calculations.registry.keyed_families import KEYED_FAMILY_SPECS
from dev.registry.compiler._loader_internals import _load_modelo_revisions, _refuse_undeclared_repurpose
from dev.registry.compiler.edition_materialisation import materialise_edition
from dev.registry.compiler.loader import load_modelo_directory

_ROOT = Path(__file__).resolve().parents[2]
_LIVE = _ROOT / "src/cadrumo/_data/registry/aeat/modelos/100"
_REPRESENTATION_FIELDS = {
    "inherited_from",
    "family_storage_baseline",
    "family_overrides",
    "family_removals",
    "family_positions",
    "cleared_families",
    "scoped_families",
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


def _normalise(member: Mapping[str, object], table: Mapping[str, object], default_key: str | None) -> dict[str, object]:
    result = dict(member)
    if default_key is not None and "source_refs" not in result:
        default = table.get(default_key)
        if isinstance(default, list | tuple) and default:
            raw_additions = result.pop("additional_source_refs", ())
            additions = raw_additions if isinstance(raw_additions, list | tuple) else ()
            result["source_refs"] = list(dict.fromkeys((*default, *additions)))
    return result


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


def convert(source: Path, candidate: Path) -> dict[str, object]:
    """Convert ``source`` into ``candidate`` and prove hydrated equality."""
    if not candidate.exists():
        shutil.copytree(source, candidate)
    from dev.registry.edition_delta_migration import assess_migration_state

    initial = assess_migration_state(source)
    if initial.minimal:
        digest = _digest(candidate)
        return {"source_digest": _digest(source), "candidate_digest": digest, "by_revision_family": []}
    before = load_modelo_directory(source)
    raw = _load_modelo_revisions(source)
    counts: list[dict[str, object]] = []
    for revision_id in ("2021", "2022", "2023", "2024", "2025"):
        raw_current = raw[revision_id]
        if not isinstance(raw_current, Mapping):
            raise RuntimeError(f"revision {revision_id} is not a mapping")
        predecessor_id = str(
            raw_current.get("family_storage_baseline") or raw_current["casilla_storage_baseline"]
        )
        current = materialise_edition(source, revision_id).table
        predecessor = materialise_edition(source, predecessor_id).table
        revision_dir = candidate / "revisions" / revision_id
        manifest_path = revision_dir / "revision.toml"
        manifest = tomlkit.parse(manifest_path.read_text(encoding="utf-8"))
        revision = manifest["revisions"][revision_id]
        revision.setdefault("family_storage_baseline", predecessor_id)
        overrides = revision.get("family_overrides") or tomlkit.aot()
        removals = revision.get("family_removals") or tomlkit.aot()
        positions = revision.get("family_positions") or tomlkit.aot()
        scoped_families = list(revision.get("scoped_families", ()))
        converted_families = {
            str(operation.get("family"))
            for operations in (overrides, removals, positions)
            for operation in operations
            if isinstance(operation, Mapping) and operation.get("family") is not None
        } | set(scoped_families) | set(revision.get("cleared_families", ()))
        for spec in KEYED_FAMILY_SPECS:
            section_dir = revision_dir / spec.section
            if spec.identity is None or spec.section in converted_families or not section_dir.is_dir():
                continue
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
            old = {
                str(item[spec.identity]): _normalise(item, predecessor, spec.source_default_key) for item in old_members
            }
            new = {str(item[spec.identity]): _normalise(item, current, spec.source_default_key) for item in new_members}
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
            for identity, successor_identity in sorted(common.items()):
                fields, removed, sequence_additions, sequence_removals, sequence_order = _difference(
                    old[identity], new[successor_identity], identity=spec.identity
                )
                reaffirm = False
                try:
                    _refuse_undeclared_repurpose(
                        "modelo 100 family conversion",
                        spec,
                        identity,
                        old[identity],
                        new[successor_identity],
                        inherited_casillas=tuple(
                            item.model_dump(mode="python") for item in before.revisions[predecessor_id].casillas
                        ),
                        successor_casillas=tuple(
                            item.model_dump(mode="python") for item in before.revisions[revision_id].casillas
                        ),
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
                entry = tomlkit.table()
                entry["family"] = spec.section
                entry["id"] = identity
                entry["position"] = position
                positions.append(entry)
                family_position_count += 1
            _remove_members(
                revision_dir,
                revision_id,
                spec.section,
                keep,
                spec.identity,
                singleton=spec.singleton,
            )
            if spec.scoped and spec.section not in scoped_families:
                scoped_families.append(spec.section)
            counts.append(
                {
                    "revision": revision_id,
                    "family": spec.section,
                    "authored_payload_fields_before": sum(
                        _payload_field_count({key: value for key, value in item.items() if key != spec.identity})
                        for item in new.values()
                    ),
                    "authored_payload_fields_after": sum(
                        _payload_field_count({key: value for key, value in new[item].items() if key != spec.identity})
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
        if overrides:
            revision["family_overrides"] = overrides
        if removals:
            revision["family_removals"] = removals
        if positions:
            revision["family_positions"] = positions
        if scoped_families:
            revision["scoped_families"] = scoped_families
        manifest_path.write_text(tomlkit.dumps(manifest), encoding="utf-8", newline="\n")
    after = load_modelo_directory(candidate)
    for revision_id in before.revisions:
        left = _effective(before.revisions[revision_id].model_dump(mode="json"))
        right = _effective(after.revisions[revision_id].model_dump(mode="json"))
        if left != right:
            raise RuntimeError(f"candidate changes hydrated revision {revision_id}")
    return {"source_digest": _digest(source), "candidate_digest": _digest(candidate), "by_revision_family": counts}


def main() -> int:
    """Run the isolated Modelo 100 family conversion command."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=_LIVE)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    report = convert(args.source.resolve(), args.candidate.resolve())
    rendered = json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    if args.report is not None:
        args.report.write_text(rendered, encoding="utf-8", newline="\n")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
