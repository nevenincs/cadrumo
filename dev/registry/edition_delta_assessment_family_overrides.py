"""Measure repeated leaves in explicit family and casilla override operations."""

from __future__ import annotations

from collections.abc import Mapping

from cadrumo.domain.calculations.registry.schema import ModeloRevision

from . import edition_delta_fields as fields
from . import edition_delta_payload as payload
from . import edition_delta_source as source
from .compiler.casilla_identity import LINEAGE_CLAIM_FIELDS
from .edition_delta_assessment_state import FamilyRun
from .edition_family_delta import STATED_WHOLE_SEQUENCES, restates_stated_whole_sequence


def _compare_family_override_operations(
    family: FamilyRun,
    inherited_by_id: Mapping[object, object],
    current_by_id: Mapping[object, object],
) -> None:
    operations = family.raw.get("family_overrides", ())
    if isinstance(operations, list | tuple):
        for operation in operations:
            _compare_family_override(family, operation, inherited_by_id, current_by_id)


def _compare_family_override(
    family: FamilyRun,
    operation: object,
    inherited_by_id: Mapping[object, object],
    current_by_id: Mapping[object, object],
) -> None:
    if not isinstance(operation, Mapping) or operation.get("family") != family.spec.section:
        return
    selector = operation.get("selector")
    override_fields = operation.get("fields", {})
    if not isinstance(selector, Mapping) or not isinstance(override_fields, Mapping):
        family.blocked.append(
            {"revision": family.revision_id, "family": family.spec.section, "reason": "invalid_override"}
        )
        return
    member_id = selector.get("id")
    current_id = operation.get("replacement_id", member_id)
    inherited = inherited_by_id.get(member_id)
    current = current_by_id.get(current_id)
    inherited_dump = payload._model_value(inherited)
    current_dump = payload._model_value(current)
    if not isinstance(inherited_dump, Mapping) or not isinstance(current_dump, Mapping):
        family.blocked.append(
            {
                "revision": family.revision_id,
                "family": family.spec.section,
                "member": member_id,
                "reason": "override_baseline_member_missing",
            }
        )
        return
    _record_whole_sequence_override(family, operation, member_id)
    inherited_leaves = payload._stated_leaves(inherited)
    current_leaves = payload._leaf_values(current_dump)
    _count_override_leaves(family, member_id, override_fields, inherited_leaves, current_leaves)


def _record_whole_sequence_override(family: FamilyRun, operation: Mapping[str, object], member_id: object) -> None:
    if not restates_stated_whole_sequence(family.spec.section, operation):
        return
    family.unresolved.append(
        {
            "revision": family.revision_id,
            "family": family.spec.section,
            "member": member_id,
            "fields": [STATED_WHOLE_SEQUENCES[family.spec.section]],
            "reason": "per-edition sequence folded into an override; state the member",
        }
    )


def _count_override_leaves(
    family: FamilyRun,
    member_id: object,
    override_fields: Mapping[str, object],
    inherited: Mapping[tuple[str, ...], object],
    current: Mapping[tuple[str, ...], object],
) -> None:
    for path in payload._leaf_values(override_fields):
        if path in inherited and path in current and payload._typed_equal(current[path], inherited[path]):
            family.row["redundant_overrides"] += 1
            family.unresolved.append(
                {
                    "revision": family.revision_id,
                    "family": family.spec.section,
                    "member": member_id,
                    "fields": [".".join(path)],
                    "reason": "authored override equals hydrated baseline",
                }
            )
        else:
            family.row["genuine_overrides"] += 1


def _compare_casilla_overrides(
    family: FamilyRun,
    predecessor: ModeloRevision,
) -> None:
    baseline_rows = {str(item.id): item for item in predecessor.casillas}
    overrides = source._members(family.raw, "casilla_overrides") or ()
    for override in overrides:
        _compare_casilla_override(family, baseline_rows, override)


def _compare_casilla_override(
    family: FamilyRun,
    baseline_rows: Mapping[str, object],
    override: Mapping[str, object],
) -> None:
    selector = override.get("selector", {})
    override_fields = override.get("fields", {})
    if not isinstance(selector, Mapping) or not isinstance(override_fields, Mapping):
        family.blocked.append(
            {"revision": family.revision_id, "family": family.spec.section, "reason": "invalid_override"}
        )
        return
    member_id = str(selector.get("id"))
    inherited = baseline_rows.get(member_id)
    if inherited is None:
        family.blocked.append(
            {
                "revision": family.revision_id,
                "family": family.spec.section,
                "member": member_id,
                "reason": "override_baseline_member_missing",
            }
        )
        return
    _count_casilla_override_fields(family, member_id, override_fields, payload._stated_leaves(inherited))


def _count_casilla_override_fields(
    family: FamilyRun,
    member_id: str,
    override_fields: Mapping[str, object],
    baseline_leaves: Mapping[tuple[str, ...], object],
) -> None:
    for path, value in payload._leaf_values(override_fields).items():
        if _casilla_override_is_forced(family, path):
            family.row["genuine_overrides"] += 1
        elif path in baseline_leaves and payload._typed_equal(value, baseline_leaves[path]):
            family.row["redundant_overrides"] += 1
            family.unresolved.append(
                {
                    "revision": family.revision_id,
                    "family": family.spec.section,
                    "member": member_id,
                    "fields": [".".join(path)],
                    "reason": "authored override equals hydrated baseline",
                }
            )
        else:
            family.row["genuine_overrides"] += 1


def _casilla_override_is_forced(family: FamilyRun, path: tuple[str, ...]) -> bool:
    return bool(path and (path[0] in LINEAGE_CLAIM_FIELDS or path[-1] in fields._EDITION_DEFAULTED_FIELDS))
