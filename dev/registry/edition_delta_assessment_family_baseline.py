"""Resolve the baseline and typed members used by a family comparison."""

from __future__ import annotations

from collections.abc import Mapping

from cadrumo.domain.calculations.registry.keyed_families import CASILLAS_FAMILY, family_identity_value
from cadrumo.domain.calculations.registry.revision_order import revision_windows_intersect

from .edition_delta_assessment_lineage import technical_root
from .edition_delta_assessment_state import FamilyBaseline, FamilyRun


def _baseline(family: FamilyRun) -> FamilyBaseline:
    spec = family.spec
    declared_predecessor = family.raw.get("predecessor")
    storage_baseline = family.raw.get(
        "casilla_storage_baseline" if spec.section == CASILLAS_FAMILY else "family_storage_baseline"
    )
    baseline_id = _declared_baseline(storage_baseline, declared_predecessor)
    explicit_root = isinstance(declared_predecessor, Mapping)
    stated_root = explicit_root and not technical_root(family.raw)
    adjacent = _adjacent_revision(family, stated_root)
    candidate_id = baseline_id or adjacent
    return FamilyBaseline(
        candidate_id=candidate_id,
        baseline_id=baseline_id,
        explicit_root=explicit_root,
        stated_root=stated_root,
        net_of_edition_tokens=baseline_id is None and spec.section == CASILLAS_FAMILY,
        storage_support_missing=family.previous is not None and baseline_id is None and spec.inherited,
    )


def _declared_baseline(storage: object, predecessor: object) -> str | None:
    if isinstance(storage, str):
        return storage
    return predecessor if isinstance(predecessor, str) else None


def _adjacent_revision(family: FamilyRun, stated_root: bool) -> str | None:
    if family.previous is None:
        return None
    if stated_root and revision_windows_intersect(family.run.definition.revisions[family.previous], family.revision):
        return None
    return family.previous


def _typed_family_members(
    family: FamilyRun,
    predecessor: object,
) -> tuple[object, ...] | None:
    value = getattr(predecessor, family.spec.section, None)
    members = _typed_members_value(value, family.spec.singleton)
    if isinstance(members, list | tuple):
        return tuple(members)
    family.blocked.append(
        {
            "revision": family.revision_id,
            "family": family.spec.section,
            "reason": "typed_family_shape_unsupported",
        }
    )
    return None


def _current_family_members(family: FamilyRun) -> tuple[object, ...] | None:
    value = getattr(family.revision, family.spec.section, None)
    members = _typed_members_value(value, family.spec.singleton)
    return tuple(members) if isinstance(members, list | tuple) else None


def _typed_members_value(value: object, singleton: bool) -> object:
    return (() if value is None else (value,)) if singleton else value


def _family_index(members: tuple[object, ...], family: FamilyRun) -> dict[object, object]:
    identity = _identity_path(family)
    return {family_identity_value(member, identity): member for member in members}


def _identity_path(family: FamilyRun) -> str:
    if family.spec.section == CASILLAS_FAMILY or family.spec.identity is None:
        return family.spec.storage_identity
    return family.spec.identity
