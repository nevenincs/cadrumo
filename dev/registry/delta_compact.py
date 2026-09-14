"""Source-only delta reduction proved against every materialised declaration.

This preserves an existing predecessor graph; it does not create continuity,
upgrade support, publish authority, or claim that an export scenario ran.
"""

from __future__ import annotations

import json
import shutil
import tempfile
from collections.abc import Mapping
from dataclasses import replace
from pathlib import Path
from typing import cast

from cadrumo.domain.calculations.registry.schema import ModeloDefinition

from .compact import canonical, fingerprint, publish_staged_tree
from .compiler.loader import load_modelo_directory, modelo_fact_scope
from .default_elision import complete_value
from .edition_delta_migration import plan_drop, stage_declaration_drop
from .edition_round_trip import localization_differences
from .transformation_proof import prove_transformation, snapshot_definition


def semantic_value(definition: ModeloDefinition) -> dict[str, object]:
    """Compare all fields except the two explicitly representation-local casilla fields."""
    value = cast(dict[str, object], complete_value(definition))
    revisions = cast(dict[str, dict[str, object]], value["revisions"])
    for revision in revisions.values():
        for casilla in cast(list[dict[str, object]], revision["casillas"]):
            del casilla["inherited_from"]
            del casilla["localization_keys"]
    return value


def differences(before: ModeloDefinition, after: ModeloDefinition) -> list[str]:
    """Check every semantic field, then apply the canonical locale-chain and label proof."""
    proof = prove_transformation(
        snapshot_definition(semantic_value(before), locale_fields={}),
        snapshot_definition(semantic_value(after), locale_fields={}),
    )
    found = [] if proof.is_equivalent else [str(proof.first_mismatch)]
    for identity, revision in before.revisions.items():
        if identity in after.revisions:
            found.extend(
                localization_differences(
                    modelo_id=str(before.id),
                    sibling_revision_ids=frozenset(before.revisions) - {identity},
                    reference=revision,
                    live=after.revisions[identity],
                )
            )
    return found


def changed_identities(before: ModeloDefinition, after: ModeloDefinition, section: str) -> set[str]:
    """Find members a proposed family drop actually changes, including descendants."""
    left = cast(dict[str, dict[str, object]], semantic_value(before)["revisions"])
    right = cast(dict[str, dict[str, object]], semantic_value(after)["revisions"])
    identity_key = "continuidad_id" if section == "casillas" else "id"
    changed: set[str] = set()
    for revision_id, revision in left.items():
        old_rows = cast(list[Mapping[str, object]], revision[section])
        new_rows = cast(list[Mapping[str, object]], right[revision_id][section])
        old = {str(row[identity_key]): row for row in old_rows if row.get(identity_key) is not None}
        new = {str(row[identity_key]): row for row in new_rows if row.get(identity_key) is not None}
        changed.update(key for key in old.keys() | new.keys() if canonical(old.get(key)) != canonical(new.get(key)))
    return changed


def compact_deltas(directory: Path, work: Path, *, apply: bool = False) -> dict[str, object]:
    """Accept only drop groups whose whole-modelo materialisation is unchanged."""
    directory, work = directory.resolve(strict=True), work.resolve()
    if work.exists() or work.is_relative_to(directory) or directory.is_relative_to(work):
        raise ValueError("work must be new and outside the modelo")
    before_files = fingerprint(directory)
    before = load_modelo_directory(directory)
    original, staged = work / "original", work / "staged"
    shutil.copytree(directory, original)
    shutil.copytree(directory, staged)
    if fingerprint(original) != before_files or fingerprint(staged) != before_files:
        raise ValueError("source changed while staging delta reduction")
    accepted: list[dict[str, object]] = []
    rejected: list[dict[str, object]] = []
    trials = 0
    for edition in plan_drop(staged, before).editions:
        for family in edition.families:
            if not family.dropped:
                continue
            if family.lineage_attestations:
                rejected.append(
                    {
                        "revision": edition.revision_id,
                        "family": family.section,
                        "members": family.dropped,
                        "reason": "requires evidence relocation, not pure omission",
                    }
                )
                continue
            selected = family
            while selected.dropped:
                trials += 1
                trial = work / f"trial-{trials}"
                shutil.copytree(staged, trial)
                stage_declaration_drop(trial, replace(edition, families=(selected,)))
                with modelo_fact_scope(directory):
                    candidate = load_modelo_directory(trial)
                mismatch = differences(before, candidate)
                if not mismatch:
                    accepted.append(
                        {"revision": edition.revision_id, "family": family.section, "members": selected.dropped}
                    )
                    staged = trial
                    break
                changed = changed_identities(before, candidate, selected.section)
                remaining = tuple(identity for identity in selected.dropped if identity not in changed)
                rejected.append(
                    {
                        "revision": edition.revision_id,
                        "family": family.section,
                        "members": tuple(identity for identity in selected.dropped if identity in changed)
                        or selected.dropped,
                        "reason": mismatch,
                    }
                )
                if remaining == selected.dropped:
                    break
                selected = replace(selected, dropped=remaining)
    with modelo_fact_scope(directory):
        after = load_modelo_directory(staged)
    if differences(before, after):
        raise ValueError("final delta proof failed; nothing published")
    result: dict[str, object] = {
        "modelo": directory.name,
        "accepted": accepted,
        "rejected": rejected,
        "dropped_members": sum(len(cast(tuple[str, ...], row["members"])) for row in accepted),
        "semantic_and_locale_equality": True,
        "rendered_export_bytes": "not run; complete export inputs compared",
        "applied": False,
        "backup": str(original),
        "before_fingerprint": before_files,
        "after_fingerprint": fingerprint(staged),
    }
    if apply:
        publish_staged_tree(directory, staged, original, before_files)
        if differences(before, load_modelo_directory(directory)):
            raise ValueError("live tree changed after final delta proof; backup retained")
        result["applied"] = True
    (work / "proof.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def main() -> int:
    """Rehearse or apply existing-graph source reduction, recording refusals explicitly."""
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--modelo", action="append", required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    work = Path(tempfile.mkdtemp(prefix="cadrumo-registry-delta-source-"))
    print(work, flush=True)
    results: list[dict[str, object]] = []
    for identity in args.modelo:
        result = compact_deltas(
            Path("src/cadrumo/_data/registry/aeat/modelos") / identity, work / identity, apply=args.apply
        )
        results.append(result)
        (work / "summary.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
        print(identity, result["dropped_members"], result["rejected"], flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
