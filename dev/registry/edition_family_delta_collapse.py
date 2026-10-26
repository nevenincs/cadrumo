"""Collapse keyed declaration families and prove hydrated equality."""

from __future__ import annotations

import shutil
from collections.abc import Mapping
from pathlib import Path

from cadrumo.domain.calculations.registry.keyed_families import KEYED_FAMILY_SPECS
from cadrumo.domain.calculations.registry.revision_order import ordered_revisions
from dev.registry.compiler.edition_materialisation import materialise_edition
from dev.registry.compiler.loader import load_modelo_declarations, load_modelo_directory

from .edition_family_delta import _digest, _effective
from .edition_family_delta_collapse_family import collapse_family
from .edition_family_delta_collapse_revision import prepare_revision, write_revision
from .edition_family_delta_collapse_state import CollapseInput

__all__ = ("collapse_keyed_families",)


def collapse_keyed_families(source: Path, candidate: Path) -> dict[str, object]:
    """Collapse every eligible keyed family and prove hydrated equality."""
    if not candidate.exists():
        shutil.copytree(source, candidate)
    from dev.registry.edition_delta_assessment import assess_migration_state

    source_digest = _digest(source)
    if assess_migration_state(source).minimal:
        return _unchanged_result(source_digest, candidate)
    inputs = _load_collapse_inputs(source, candidate, source_digest)
    counts: list[dict[str, object]] = []
    for typed_revision in ordered_revisions(inputs.before):
        state = prepare_revision(inputs, candidate, typed_revision, counts)
        if state is None:
            continue
        for spec in KEYED_FAMILY_SPECS:
            collapse_family(state, spec)
        write_revision(state)
    return _prove_collapse_result(inputs, candidate, counts)


def _unchanged_result(source_digest: str, candidate: Path) -> dict[str, object]:
    return {"source_digest": source_digest, "candidate_digest": _digest(candidate), "by_revision_family": []}


def _load_collapse_inputs(source: Path, candidate: Path, source_digest: str) -> CollapseInput:
    before = load_modelo_directory(source)
    source_raw = _revision_declarations(load_modelo_declarations(source), before.id, "")
    resolved = {revision_id: materialise_edition(source, revision_id).table for revision_id in before.revisions}
    candidate_raw = _revision_declarations(load_modelo_declarations(candidate), before.id, " candidate")
    return CollapseInput(source_digest, before, source_raw, resolved, candidate_raw)


def _revision_declarations(declarations: Mapping[str, object], modelo_id: object, label: str) -> Mapping[str, object]:
    revisions = declarations["revisions"]
    if not isinstance(revisions, Mapping):
        raise RuntimeError(f"modelo {modelo_id}{label} revisions are not a mapping")
    return {str(revision_id): revision for revision_id, revision in revisions.items()}


def _prove_collapse_result(
    inputs: CollapseInput, candidate: Path, counts: list[dict[str, object]]
) -> dict[str, object]:
    after = load_modelo_directory(candidate)
    for revision_id in inputs.before.revisions:
        left = _effective(inputs.before.revisions[revision_id].model_dump(mode="json"))
        right = _effective(after.revisions[revision_id].model_dump(mode="json"))
        _assert_revision_unchanged(revision_id, left, right)
    return {
        "source_digest": inputs.source_digest,
        "candidate_digest": _digest(candidate),
        "by_revision_family": counts,
    }


def _assert_revision_unchanged(revision_id: str, left: object, right: object) -> None:
    if left == right:
        return
    if not isinstance(left, Mapping) or not isinstance(right, Mapping):
        raise RuntimeError(f"candidate changes hydrated revision {revision_id}; fields=['<root>']")
    differing = sorted(key for key in set(left) | set(right) if left.get(key) != right.get(key))
    raise RuntimeError(f"candidate changes hydrated revision {revision_id}; fields={differing!r}")
