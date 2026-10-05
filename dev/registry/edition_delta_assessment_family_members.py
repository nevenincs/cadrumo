"""Compare authored member fields with the payload inherited from a baseline."""

from __future__ import annotations

from collections.abc import Mapping

from cadrumo.domain.calculations.registry.keyed_families import CASILLAS_FAMILY, family_identity_value

from . import edition_delta_fields as fields
from . import edition_delta_payload as payload
from .compiler.casilla_identity import LINEAGE_CLAIM_FIELDS
from .edition_delta_assessment_family_baseline import _identity_path
from .edition_delta_assessment_lineage import edition_neutral
from .edition_delta_assessment_state import FamilyBaseline, FamilyRun
from .edition_family_delta import STATED_WHOLE_SEQUENCES


def _compare_authored_members(
    family: FamilyRun,
    baseline: FamilyBaseline,
    authored: tuple[Mapping[str, object], ...],
    inherited_by_id: Mapping[object, object],
    current_by_id: Mapping[object, object],
) -> set[object]:
    authored_ids: set[object] = set()
    for member in authored:
        _compare_authored_member(family, baseline, member, inherited_by_id, current_by_id, authored_ids)
    return authored_ids


def _compare_authored_member(
    family: FamilyRun,
    baseline: FamilyBaseline,
    member: Mapping[str, object],
    inherited_by_id: Mapping[object, object],
    current_by_id: Mapping[object, object],
    authored_ids: set[object],
) -> None:
    identity = family_identity_value(member, _identity_path(family))
    authored_ids.add(identity)
    inherited = inherited_by_id.get(identity)
    if inherited is None or _is_new_casilla_lineage(family, member, inherited):
        family.row["additions"] += 1
        return
    if not isinstance(inherited, Mapping) and not hasattr(inherited, "model_dump"):
        family.blocked.append(
            {
                "revision": family.revision_id,
                "family": family.spec.section,
                "member": identity,
                "reason": "typed_family_shape_unsupported",
            }
        )
        return
    differences = _member_differences(family, baseline, member, identity, inherited, current_by_id)
    _record_member_counts(family, baseline, identity, differences)


def _is_new_casilla_lineage(family: FamilyRun, member: Mapping[str, object], inherited: object) -> bool:
    if family.spec.section != CASILLAS_FAMILY:
        return False
    stated_lineage = member.get(fields._LINEAGE)
    inherited_lineage = getattr(inherited, fields._LINEAGE, None)
    return (
        stated_lineage is not None and inherited_lineage is not None and str(stated_lineage) != str(inherited_lineage)
    )


def _member_differences(
    family: FamilyRun,
    baseline: FamilyBaseline,
    member: Mapping[str, object],
    identity: object,
    inherited: object,
    current_by_id: Mapping[object, object],
) -> tuple[list[str], list[str]]:
    authored_leaves = _authored_leaves(member)
    baseline_leaves = payload._stated_leaves(inherited)
    current_leaves = _current_member_leaves(current_by_id.get(identity))
    same = _same_authored_paths(family, baseline, authored_leaves, current_leaves, baseline_leaves)
    _respect_stated_whole_sequence(family, authored_leaves, same)
    different = [".".join(path) for path in authored_leaves if path not in same]
    equal = [".".join(path) for path in authored_leaves if path in same]
    return different, equal


def _authored_leaves(member: Mapping[str, object]) -> dict[tuple[str, ...], object]:
    return {
        path: value
        for path, value in payload._leaf_values(dict(member)).items()
        if path and path[0] not in payload._STRUCTURAL_FIELDS and path[0] not in LINEAGE_CLAIM_FIELDS
    }


def _current_member_leaves(member: object) -> dict[tuple[str, ...], object]:
    value = payload._model_value(member)
    return payload._leaf_values(value) if isinstance(value, Mapping) else {}


def _same_authored_paths(
    family: FamilyRun,
    baseline: FamilyBaseline,
    authored: Mapping[tuple[str, ...], object],
    current: Mapping[tuple[str, ...], object],
    inherited: Mapping[tuple[str, ...], object],
) -> set[tuple[str, ...]]:
    return {
        path
        for path in authored
        if path in current
        and path in inherited
        and _typed_reference_equal(family, baseline, path, current[path], inherited[path])
    }


def _typed_reference_equal(
    family: FamilyRun,
    baseline: FamilyBaseline,
    path: tuple[str, ...],
    current: object,
    inherited: object,
) -> bool:
    if baseline.net_of_edition_tokens and path[0] in fields._REFERENCE_SECTIONS:
        current = edition_neutral(current, family.revision_id)
        inherited = edition_neutral(inherited, baseline.candidate_id)
    return payload._typed_equal(current, inherited)


def _respect_stated_whole_sequence(
    family: FamilyRun,
    authored: Mapping[tuple[str, ...], object],
    same: set[tuple[str, ...]],
) -> None:
    sequence = STATED_WHOLE_SEQUENCES.get(family.spec.section)
    if sequence is not None and any(path[0] == sequence and path not in same for path in authored):
        same.clear()


def _record_member_counts(
    family: FamilyRun,
    baseline: FamilyBaseline,
    identity: object,
    differences: tuple[list[str], list[str]],
) -> None:
    different, equal = differences
    family.row["genuine_overrides"] += len(different)
    family.row["redundant_overrides"] += len(equal)
    if not equal:
        return
    _record_equal_member_fields(family, baseline, identity, equal)


def _record_equal_member_fields(
    family: FamilyRun, baseline: FamilyBaseline, identity: object, equal: list[str]
) -> None:
    if baseline.baseline_id is None:
        reason = (
            "explicit root restates the edition before it; reusing its storage would inherit this"
            if baseline.stated_root
            else "technical root prevents supported inheritance"
        )
        family.unresolved.append(
            {
                "revision": family.revision_id,
                "family": family.spec.section,
                "member": identity,
                "fields": sorted(equal),
                "reason": reason,
            }
        )
        return
    reason = "authored value equals hydrated baseline"
    if baseline.storage_support_missing:
        reason = "family delta support absent; casilla baseline does not compact this family"
        family.blocked.append(
            {"revision": family.revision_id, "family": family.spec.section, "reason": "delta_support_missing"}
        )
    family.unresolved.append(
        {
            "revision": family.revision_id,
            "family": family.spec.section,
            "member": identity,
            "fields": sorted(equal),
            "reason": reason,
        }
    )


def _count_inherited_payload(
    family: FamilyRun,
    current_members: tuple[object, ...] | None,
    inherited_by_id: Mapping[object, object],
    authored_ids: set[object],
) -> None:
    if current_members is None:
        return
    for member in current_members:
        identity = family_identity_value(member, _identity_path(family))
        inherited = inherited_by_id.get(identity)
        if identity in authored_ids or inherited is None:
            continue
        family.row["inherited_payload_fields"] += _equal_inherited_leaf_count(member, inherited)


def _equal_inherited_leaf_count(current_member: object, inherited_member: object) -> int:
    current_dump = payload._model_value(current_member)
    inherited_dump = payload._model_value(inherited_member)
    if not isinstance(current_dump, Mapping) or not isinstance(inherited_dump, Mapping):
        return 0
    current_leaves = payload._leaf_values(current_dump)
    inherited_leaves = payload._leaf_values(inherited_dump)
    return sum(
        1
        for path, value in current_leaves.items()
        if path
        and path[0] not in payload._STRUCTURAL_FIELDS
        and path in inherited_leaves
        and payload._typed_equal(value, inherited_leaves[path])
    )
