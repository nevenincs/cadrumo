"""Remove only authored override leaves the independent assessor proves redundant."""

from __future__ import annotations

from collections.abc import Mapping, MutableMapping, Sequence
from pathlib import Path
from typing import cast

import tomlkit

from cadrumo.domain.calculations.registry.keyed_families import CASILLAS_FAMILY

from . import edition_delta_assessment as _edition_delta_assessment
from . import edition_delta_fields as _edition_delta_fields
from . import edition_delta_payload as _edition_delta_payload

__all__ = ("prune_redundant_override_leaves",)


def _redundant_by_revision(findings: Sequence[Mapping[str, object]]) -> dict[str, list[Mapping[str, object]]]:
    by_revision: dict[str, list[Mapping[str, object]]] = {}
    for item in findings:
        revision = item.get("revision")
        if isinstance(revision, str):
            by_revision.setdefault(revision, []).append(item)
    return by_revision


def _targets_for_family(
    findings: Sequence[Mapping[str, object]], family: str | None
) -> dict[tuple[str, str], set[tuple[str, ...]]]:
    targets: dict[tuple[str, str], set[tuple[str, ...]]] = {}
    for finding in findings:
        finding_family = finding.get("family")
        if _out_of_family_group(finding_family, family):
            continue
        member, fields = finding.get("member"), finding.get("fields")
        if not isinstance(finding_family, str) or not isinstance(member, str) or not isinstance(fields, list):
            continue
        targets.setdefault((finding_family, member), set()).update(_field_paths(fields))
    return targets


def _out_of_family_group(finding_family: object, family: str | None) -> bool:
    if family is not None:
        return finding_family != family
    return finding_family == CASILLAS_FAMILY


def _field_paths(fields: list[object]) -> set[tuple[str, ...]]:
    return {
        tuple(field.split("."))
        for field in fields
        if isinstance(field, str) and field.split(".")[-1] not in _edition_delta_fields._EDITION_DEFAULTED_FIELDS
    }


def _operation_identity(operation: object) -> tuple[object, object, object]:
    if not isinstance(operation, Mapping):
        return None, None, None
    selector = operation.get("selector")
    member = selector.get("id") if isinstance(selector, Mapping) else None
    fields = operation.get("fields")
    return (
        member,
        fields.get("id", member) if isinstance(fields, Mapping) else member,
        fields if isinstance(fields, Mapping) else None,
    )


def _operation_family(operation: object, family: str | None) -> object:
    if family is not None:
        return CASILLAS_FAMILY
    return operation.get("family") if isinstance(operation, Mapping) else None


def _operation_paths(
    operation: object,
    family: str | None,
    targets: Mapping[tuple[str, str], set[tuple[str, ...]]],
) -> tuple[object, set[tuple[str, ...]]]:
    member, effective_member, fields = _operation_identity(operation)
    operation_family = str(_operation_family(operation, family))
    paths = targets.get((operation_family, str(effective_member)), set()) | targets.get(
        (operation_family, str(member)), set()
    )
    return fields, paths


def _has_non_field_effect(operation: object) -> bool:
    if not isinstance(operation, Mapping):
        return False
    return any(
        operation.get(key)
        for key in (
            "removed_fields",
            "restate_provenance",
            "restate_identity",
            "replacement_id",
            "sequence_additions",
            "sequence_removals",
            "sequence_order",
        )
    )


def _prune_operation(
    operation: object,
    family: str | None,
    targets: Mapping[tuple[str, str], set[tuple[str, ...]]],
) -> tuple[bool, int]:
    fields, paths = _operation_paths(operation, family, targets)
    removed = sum(int(_edition_delta_payload._remove_toml_leaf(fields, path)) for path in paths)
    keep = bool(fields) or _has_non_field_effect(operation)
    return keep, removed


def _prune_operation_group(
    revision: MutableMapping[str, object],
    operation_name: str,
    findings: Sequence[Mapping[str, object]],
    family: str | None,
) -> int:
    operations = revision.get(operation_name)
    if not isinstance(operations, list):
        return 0
    targets = _targets_for_family(findings, family)
    kept: list[object] = []
    removed = 0
    for operation in operations:
        retain, count = _prune_operation(operation, family, targets)
        removed += count
        if retain:
            kept.append(operation)
    operations.clear()
    operations.extend(kept)
    if not operations:
        del revision[operation_name]
    return removed


def _prune_revision(document: object, revision_id: str, findings: Sequence[Mapping[str, object]]) -> int:
    root = cast(Mapping[str, object], document)
    revisions = cast(Mapping[str, object], root["revisions"])
    revision = cast(MutableMapping[str, object], revisions[revision_id])
    return sum(
        _prune_operation_group(revision, name, findings, family)
        for family, name in ((CASILLAS_FAMILY, "casilla_overrides"), (None, "family_overrides"))
    )


def prune_redundant_override_leaves(modelo_dir: Path) -> int:
    """Delete override leaves the assessor reports equal to their hydrated baseline; return how many were removed."""
    assessment = _edition_delta_assessment.assess_migration_state(modelo_dir)
    redundant = [
        item
        for item in assessment.unresolved_duplication
        if item.get("reason") == "authored override equals hydrated baseline"
    ]
    removed = 0
    for revision_id, findings in _redundant_by_revision(redundant).items():
        manifest_path = modelo_dir / "revisions" / revision_id / _edition_delta_fields._MANIFEST
        document = tomlkit.parse(manifest_path.read_text(encoding="utf-8"))
        removed += _prune_revision(document, revision_id, findings)
        manifest_path.write_text(tomlkit.dumps(document), encoding="utf-8", newline="\n")
    return removed
