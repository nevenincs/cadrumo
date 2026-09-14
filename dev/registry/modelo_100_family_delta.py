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
            additions = result.pop("additional_source_refs", ())
            result["source_refs"] = list(dict.fromkeys((*default, *additions)))
    return result


def _difference(
    left: Mapping[str, object], right: Mapping[str, object], *, identity: str
) -> tuple[dict[str, object], list[str]]:
    fields: dict[str, object] = {}
    removed: list[str] = []
    for key in sorted(set(left) | set(right)):
        if key == identity:
            continue
        if key not in right:
            removed.append(key)
        elif key not in left or left[key] != right[key]:
            fields[key] = right[key]
    return fields, removed


def _remove_members(revision_dir: Path, revision_id: str, family: str, keep: set[str], identity: str) -> None:
    section_dir = revision_dir / family
    if not section_dir.is_dir():
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
    before = load_modelo_directory(source)
    raw = _load_modelo_revisions(source)
    counts: list[dict[str, object]] = []
    for revision_id in ("2021", "2022", "2023", "2024", "2025"):
        predecessor_id = str(raw[revision_id]["casilla_storage_baseline"])
        current, predecessor = raw[revision_id], raw[predecessor_id]
        revision_dir = candidate / "revisions" / revision_id
        manifest_path = revision_dir / "revision.toml"
        manifest = tomlkit.parse(manifest_path.read_text(encoding="utf-8"))
        revision = manifest["revisions"][revision_id]
        if "family_storage_baseline" in revision:
            continue
        revision["family_storage_baseline"] = predecessor_id
        overrides = tomlkit.aot()
        removals = tomlkit.aot()
        positions = tomlkit.aot()
        for spec in KEYED_FAMILY_SPECS:
            if spec.period_scoped or spec.identity is None:
                continue
            old_members = tuple(predecessor.get(spec.section, ()))
            new_members = tuple(current.get(spec.section, ()))
            old = {
                str(item[spec.identity]): _normalise(item, predecessor, spec.source_default_key) for item in old_members
            }
            new = {str(item[spec.identity]): _normalise(item, current, spec.source_default_key) for item in new_members}
            additions = set(new) - set(old)
            keep = set(additions)
            family_overrides = 0
            payload = 0
            for identity in sorted(set(old) & set(new)):
                fields, removed = _difference(old[identity], new[identity], identity=spec.identity)
                reaffirm = False
                try:
                    _refuse_undeclared_repurpose(
                        "modelo 100 family conversion",
                        spec,
                        identity,
                        old[identity],
                        new[identity],
                        inherited_casillas=tuple(
                            item.model_dump(mode="python") for item in before.revisions[predecessor_id].casillas
                        ),
                        successor_casillas=tuple(
                            item.model_dump(mode="python") for item in before.revisions[revision_id].casillas
                        ),
                    )
                except RegistryLoadError:
                    reaffirm = True
                if not fields and not removed and not reaffirm:
                    continue
                entry = tomlkit.table()
                entry["family"] = spec.section
                entry["selector"] = _table({"revision": predecessor_id, "id": identity})
                if fields:
                    entry["fields"] = _table(fields)
                    payload += len(fields)
                if removed:
                    entry["removed_fields"] = removed
                if reaffirm:
                    entry["restate_identity"] = True
                overrides.append(entry)
                family_overrides += 1
            for identity in sorted(set(old) - set(new)):
                entry = tomlkit.table()
                entry["family"] = spec.section
                entry["selector"] = _table({"revision": predecessor_id, "id": identity})
                removals.append(entry)
            effective_order = [str(item[spec.identity]) for item in new_members]
            natural = [str(item[spec.identity]) for item in old_members if str(item[spec.identity]) in new] + [
                str(item[spec.identity]) for item in new_members if str(item[spec.identity]) in additions
            ]
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
            _remove_members(revision_dir, revision_id, spec.section, keep, spec.identity)
            counts.append(
                {
                    "revision": revision_id,
                    "family": spec.section,
                    "authored_payload_fields_before": sum(len(item) - 1 for item in new_members),
                    "authored_payload_fields_after": sum(len(new[item]) - 1 for item in additions) + payload,
                    "overrides": family_overrides,
                    "additions": len(additions),
                    "removals": len(set(old) - set(new)),
                    "structural_overhead": (
                        2 * family_overrides + 2 * len(set(old) - set(new)) + 2 * family_position_count
                    ),
                }
            )
        if overrides:
            revision["family_overrides"] = overrides
        if removals:
            revision["family_removals"] = removals
        if positions:
            revision["family_positions"] = positions
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
