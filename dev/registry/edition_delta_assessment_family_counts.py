"""Count authored storage fields and physical bytes for one family."""

from __future__ import annotations

from collections.abc import Mapping

from cadrumo.domain.calculations.registry.cleared_families import cleared_family_names
from cadrumo.domain.calculations.registry.keyed_families import CASILLAS_FAMILY

from . import edition_delta_payload as payload
from . import edition_delta_source as source
from .edition_delta_assessment_state import FamilyRun


def _family_bytes(family: FamilyRun) -> int:
    family_dir = family.run.modelo_dir / "revisions" / family.revision_id / family.spec.section
    return sum(path.stat().st_size for path in family_dir.rglob("*") if path.is_file())


def _count_authored_payload(family: FamilyRun, authored: tuple[Mapping[str, object], ...]) -> None:
    for member in authored:
        _add_field_counts(family, member)
    _count_casilla_operations(family)
    _count_family_operations(family)
    _count_cleared_family(family)


def _add_field_counts(family: FamilyRun, value: object) -> None:
    count, overhead = payload._field_count(value, structural=False)
    family.row["authored_payload_fields"] += count
    family.row["structural_overhead"] += overhead


def _count_casilla_operations(family: FamilyRun) -> None:
    if family.spec.section != CASILLAS_FAMILY:
        return
    overrides = source._members(family.raw, "casilla_overrides") or ()
    for override in overrides:
        fields_value = override.get("fields", {})
        _add_field_counts(family, fields_value)
        family.row["structural_overhead"] += 1
    family.row["removals"] += len(source._members(family.raw, "casilla_removals") or ())
    positions = source._members(family.raw, "casilla_positions") or ()
    family.row["structural_overhead"] += 2 * len(positions)


def _count_family_operations(family: FamilyRun) -> None:
    for operation_name in ("family_overrides", "family_removals", "family_positions"):
        operations = family.raw.get(operation_name, ())
        if not isinstance(operations, list | tuple):
            family.blocked.append(
                {"revision": family.revision_id, "family": operation_name, "reason": "operation_shape_unsupported"}
            )
            continue
        _count_operation_kind(family, operation_name, operations)


def _count_operation_kind(family: FamilyRun, name: str, operations: list[object] | tuple[object, ...]) -> None:
    for operation in operations:
        if not isinstance(operation, Mapping) or operation.get("family") != family.spec.section:
            continue
        if name == "family_overrides":
            _count_override_payload(family, operation)
        elif name == "family_removals":
            family.row["removals"] += 1
        family.row["structural_overhead"] += _operation_overhead(operation)


def _count_override_payload(family: FamilyRun, operation: Mapping[str, object]) -> None:
    _add_field_counts(family, operation.get("fields", {}))
    removed_fields = operation.get("removed_fields", ())
    if not isinstance(removed_fields, list | tuple):
        family.blocked.append(
            {"revision": family.revision_id, "family": family.spec.section, "reason": "operation_shape_unsupported"}
        )
        return
    family.row["removals"] += len(removed_fields)


def _operation_overhead(operation: Mapping[str, object]) -> int:
    return len(payload._leaf_values({key: value for key, value in operation.items() if key != "fields"}))


def _count_cleared_family(family: FamilyRun) -> None:
    if family.spec.section not in cleared_family_names(family.raw.get("cleared_families", ())):
        return
    family.row["removals"] += 1
    family.row["structural_overhead"] += 1
