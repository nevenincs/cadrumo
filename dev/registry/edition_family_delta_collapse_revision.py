"""Prepare and write one revision's keyed-family representation changes."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import cast

import tomlkit

from cadrumo.domain.calculations.registry.cleared_families import cleared_family_names
from cadrumo.domain.calculations.registry.keyed_families import KEYED_FAMILY_SPECS
from cadrumo.domain.calculations.registry.schema import ModeloDefinition, ModeloRevision
from dev.registry.compiler.keyed_family_period_scope import selector_covers

from .edition_family_delta import (
    _family_baseline,
    _family_members,
    _replace_operations,
    _restated_sections,
    _selector_id,
)
from .edition_family_delta_collapse_state import CollapseInput, RevisionState


def prepare_revision(
    inputs: CollapseInput,
    candidate: Path,
    typed_revision: ModeloRevision,
    counts: list[dict[str, object]],
) -> RevisionState | None:
    """Load one candidate revision's manifest and operations for collapse; ``None`` when it has no family baseline."""
    revision_id = str(typed_revision.id)
    raw_current = inputs.candidate_raw[revision_id]
    authored_current = inputs.source_raw.get(revision_id)
    if not isinstance(raw_current, Mapping) or not isinstance(authored_current, Mapping):
        raise RuntimeError(f"revision {revision_id} is not a mapping")
    predecessor_id = _family_baseline(authored_current, raw_current)
    if predecessor_id is None:
        return None
    current = inputs.resolved[revision_id]
    predecessor = inputs.resolved[predecessor_id]
    if not isinstance(current, Mapping) or not isinstance(predecessor, Mapping):
        raise RuntimeError(f"revision {revision_id} or its baseline {predecessor_id} is not a mapping")
    state = _read_revision_state(
        inputs.before,
        typed_revision,
        revision_id,
        predecessor_id,
        current,
        predecessor,
        candidate,
        counts,
    )
    _add_missing_scopes(state)
    _remove_unfileable_period_removals(state)
    return state


def _read_revision_state(
    before: ModeloDefinition,
    typed_revision: ModeloRevision,
    revision_id: str,
    predecessor_id: str,
    current: Mapping[str, object],
    predecessor: Mapping[str, object],
    candidate: Path,
    counts: list[dict[str, object]],
) -> RevisionState:
    revision_dir = _candidate_revision_dir(candidate, revision_id)
    manifest_path = revision_dir / "revision.toml"
    manifest = tomlkit.parse(manifest_path.read_text(encoding="utf-8"))
    revision = manifest["revisions"][revision_id]
    overrides = revision.get("family_overrides") or tomlkit.aot()
    removals = revision.get("family_removals") or tomlkit.aot()
    positions = revision.get("family_positions") or tomlkit.aot()
    scoped_families = list(revision.get("scoped_families", ()))
    return RevisionState(
        before=before,
        typed_revision=typed_revision,
        revision_id=revision_id,
        predecessor_id=predecessor_id,
        current=current,
        predecessor=predecessor,
        revision_dir=revision_dir,
        manifest_path=manifest_path,
        manifest=manifest,
        revision=revision,
        overrides=cast(list[object], overrides),
        removals=cast(list[object], removals),
        positions=cast(list[object], positions),
        restated_sections=_restated_sections(revision),
        scoped_families=scoped_families,
        period_selector=current.get("period_selector"),
        counts=counts,
    )


def _candidate_revision_dir(candidate: Path, revision_id: str) -> Path:
    return candidate / "revisions" / revision_id


def _add_missing_scopes(state: RevisionState) -> None:
    operated_sections = _operation_families(state.overrides, state.removals, state.positions)
    operated_sections.update(cleared_family_names(state.revision.get("cleared_families", ())))
    scoped_sections = {spec.section for spec in KEYED_FAMILY_SPECS if spec.scoped}
    missing = sorted((operated_sections & scoped_sections) - set(state.scoped_families))
    state.scoped_families.extend(missing)
    state.revision_changed = bool(missing)


def _operation_families(*operations: object) -> set[str]:
    return {
        str(operation.get("family"))
        for collection in operations
        for operation in _items(collection)
        if isinstance(operation, Mapping) and operation.get("family") is not None
    }


def _items(value: object) -> Iterable[object]:
    return value if isinstance(value, Iterable) and not isinstance(value, str | bytes | Mapping) else ()


def _remove_unfileable_period_removals(state: RevisionState) -> None:
    for spec in KEYED_FAMILY_SPECS:
        if not spec.period_scoped or spec.identity is None:
            continue
        baseline = {str(member.get(spec.identity)): member for member in _family_members(state.predecessor, spec)}
        retained = _fileable_removals(state.removals, spec.section, baseline, state.period_selector)
        state.revision_changed |= _replace_operations(state.removals, retained)


def _fileable_removals(
    removals: object,
    section: str,
    baseline: Mapping[str, Mapping[str, object]],
    period_selector: object,
) -> list[object]:
    return [
        operation
        for operation in _items(removals)
        if not _is_unfileable_period_removal(operation, section, baseline, period_selector)
    ]


def _is_unfileable_period_removal(
    operation: object,
    section: str,
    baseline: Mapping[str, Mapping[str, object]],
    period_selector: object,
) -> bool:
    if not isinstance(operation, Mapping) or operation.get("family") != section:
        return False
    member = baseline.get(_selector_id(operation) or "")
    if member is None:
        return False
    return not selector_covers(period_selector, member)


def write_revision(state: RevisionState) -> None:
    """Store the revision's family operations and rewrite its manifest when the collapse changed it."""
    if state.revision_changed:
        state.revision.setdefault("family_storage_baseline", state.predecessor_id)
    _store_operations(state)
    if state.scoped_families:
        state.revision["scoped_families"] = state.scoped_families
    if state.revision_changed:
        state.manifest_path.write_text(tomlkit.dumps(state.manifest), encoding="utf-8", newline="\n")


def _store_operations(state: RevisionState) -> None:
    for key, operations in (
        ("family_overrides", state.overrides),
        ("family_removals", state.removals),
        ("family_positions", state.positions),
    ):
        if operations:
            state.revision[key] = operations
        elif key in state.revision:
            del state.revision[key]


__all__ = ("prepare_revision", "write_revision")
