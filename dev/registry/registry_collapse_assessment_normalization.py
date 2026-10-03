"""Authored-baseline classification for registry collapse findings."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import replace
from pathlib import Path
from typing import cast

from dev.registry.compiler.loader import load_modelo_declarations
from dev.registry.edition_delta_assessment import MigrationAssessment

from .registry_collapse_values import _same_typed_value


def _record_override_reclassifications(
    revision_id: str,
    revision: Mapping[str, object],
    required: set[tuple[str, str]],
    vacated_storage_ids: set[tuple[str, str]],
) -> bool:
    default = revision.get("casilla_source_refs")
    overrides = revision.get("casilla_overrides", ())
    if not isinstance(overrides, list | tuple):
        return False
    for override in cast(Sequence[object], overrides):
        if not isinstance(override, Mapping):
            continue
        selector, fields = override.get("selector"), override.get("fields")
        if not isinstance(selector, Mapping) or not isinstance(fields, Mapping):
            continue
        member, source_refs = selector.get("id"), fields.get("source_refs")
        replacement_id = fields.get("id")
        if isinstance(member, str) and isinstance(replacement_id, str) and replacement_id != member:
            vacated_storage_ids.add((revision_id, member))
        if _requires_authored_source_override(member, source_refs, default):
            required.add((revision_id, cast(str, member)))
    return True


def _requires_authored_source_override(member: object, source_refs: object, default: object) -> bool:
    return (
        isinstance(member, str)
        and isinstance(source_refs, list | tuple)
        and isinstance(default, list | tuple)
        and not _same_typed_value(tuple(source_refs), tuple(default))
    )


def _predecessor_lineages(rows: object) -> Mapping[str, object] | None:
    if not isinstance(rows, list | tuple):
        return None
    return {
        str(row.get("id")): row.get("continuidad_id")
        for item in cast(Sequence[object], rows)
        if isinstance(item, Mapping) and isinstance((row := cast(Mapping[str, object], item)).get("id"), str)
    }


def _record_lineage_reclassifications(
    revision_id: str,
    revision: Mapping[str, object],
    declarations: Mapping[str, object],
    vacated_storage_ids: set[tuple[str, str]],
) -> None:
    predecessor_id = revision.get("casilla_storage_baseline", revision.get("predecessor"))
    predecessor = declarations.get(predecessor_id) if isinstance(predecessor_id, str) else None
    if not isinstance(predecessor, Mapping):
        return
    predecessor_lineages = _predecessor_lineages(predecessor.get("casillas", ()))
    current_rows = revision.get("casillas", ())
    if predecessor_lineages is None or not isinstance(current_rows, list | tuple):
        return
    for item in cast(Sequence[object], current_rows):
        if not isinstance(item, Mapping):
            continue
        member, lineage = item.get("id"), item.get("continuidad_id")
        if _reuses_storage_id_for_new_lineage(member, lineage, predecessor_lineages):
            vacated_storage_ids.add((revision_id, cast(str, member)))


def _reuses_storage_id_for_new_lineage(
    member: object,
    lineage: object,
    predecessor_lineages: Mapping[str, object],
) -> bool:
    return (
        isinstance(member, str)
        and isinstance(lineage, str)
        and isinstance(predecessor_lineages.get(member), str)
        and lineage != predecessor_lineages[member]
    )


def _reclassification_keys(
    declarations: Mapping[str, object],
) -> tuple[set[tuple[str, str]], set[tuple[str, str]]]:
    required: set[tuple[str, str]] = set()
    vacated_storage_ids: set[tuple[str, str]] = set()
    for raw_revision_id, raw_revision in declarations.items():
        if not isinstance(raw_revision, Mapping):
            continue
        revision_id = str(raw_revision_id)
        if not _record_override_reclassifications(revision_id, raw_revision, required, vacated_storage_ids):
            continue
        _record_lineage_reclassifications(revision_id, raw_revision, declarations, vacated_storage_ids)
    return required, vacated_storage_ids


def _is_provenance_reclassification(finding: Mapping[str, object], required: set[tuple[str, str]]) -> bool:
    revision_id, member = finding.get("revision"), finding.get("member")
    return (
        finding.get("reason") == "authored override equals hydrated baseline"
        and finding.get("family") == "casillas"
        and finding.get("fields") == ["source_refs"]
        and isinstance(revision_id, str)
        and isinstance(member, str)
        and (revision_id, member) in required
    )


def _is_addition_reclassification(finding: Mapping[str, object], vacated_storage_ids: set[tuple[str, str]]) -> bool:
    revision_id, member = finding.get("revision"), finding.get("member")
    return (
        finding.get("reason") == "authored value equals hydrated baseline"
        and finding.get("family") == "casillas"
        and isinstance(finding.get("fields"), list)
        and isinstance(revision_id, str)
        and isinstance(member, str)
        and (revision_id, member) in vacated_storage_ids
    )


def _reclassified_findings(
    assessment: MigrationAssessment,
    required: set[tuple[str, str]],
    vacated_storage_ids: set[tuple[str, str]],
) -> tuple[tuple[Mapping[str, object], ...], tuple[Mapping[str, object], ...]]:
    provenance = tuple(
        finding for finding in assessment.unresolved_duplication if _is_provenance_reclassification(finding, required)
    )
    additions = tuple(
        finding
        for finding in assessment.unresolved_duplication
        if _is_addition_reclassification(finding, vacated_storage_ids)
    )
    return provenance, additions


def _finding_revision_counts(
    findings: Sequence[Mapping[str, object]],
) -> dict[str, int]:
    counts: dict[str, int] = {}
    for finding in findings:
        revision_id = cast(str, finding["revision"])
        counts[revision_id] = counts.get(revision_id, 0) + 1
    return counts


def _addition_counts(
    findings: Sequence[Mapping[str, object]],
) -> tuple[dict[str, int], dict[str, set[str]]]:
    leaves: dict[str, int] = {}
    members: dict[str, set[str]] = {}
    for finding in findings:
        revision_id = cast(str, finding["revision"])
        fields = cast(list[object], finding["fields"])
        leaves[revision_id] = leaves.get(revision_id, 0) + len(fields)
        members.setdefault(revision_id, set()).add(cast(str, finding["member"]))
    return leaves, members


def _adjusted_family_row(
    row: Mapping[str, object],
    provenance_counts: Mapping[str, int],
    addition_leaves: Mapping[str, int],
    addition_members: Mapping[str, set[str]],
) -> Mapping[str, object]:
    if row.get("family") != "casillas":
        return row
    revision_id = str(row.get("revision"))
    provenance_count = provenance_counts.get(revision_id, 0)
    addition_leaf_count = addition_leaves.get(revision_id, 0)
    addition_member_count = len(addition_members.get(revision_id, ()))
    if not provenance_count and not addition_leaf_count:
        return row
    updated = dict(row)
    old_redundant = updated.get("redundant_overrides", 0)
    old_genuine = updated.get("genuine_overrides", 0)
    old_additions = updated.get("additions", 0)
    updated["redundant_overrides"] = (
        (old_redundant if isinstance(old_redundant, int) else 0) - provenance_count - addition_leaf_count
    )
    updated["genuine_overrides"] = (old_genuine if isinstance(old_genuine, int) else 0) + provenance_count
    updated["additions"] = (old_additions if isinstance(old_additions, int) else 0) + addition_member_count
    return updated


def _adjusted_family_rows(
    assessment: MigrationAssessment,
    provenance_counts: Mapping[str, int],
    addition_leaves: Mapping[str, int],
    addition_members: Mapping[str, set[str]],
) -> tuple[Mapping[str, object], ...]:
    return tuple(
        _adjusted_family_row(row, provenance_counts, addition_leaves, addition_members)
        for row in assessment.by_revision_family
    )


def _without_reclassified_findings(
    assessment: MigrationAssessment,
    reclassified: Sequence[Mapping[str, object]],
) -> tuple[Mapping[str, object], ...]:
    identities = {id(finding) for finding in reclassified}
    return tuple(finding for finding in assessment.unresolved_duplication if id(finding) not in identities)


def normalized_assessment(modelo_dir: Path, assessment: MigrationAssessment) -> MigrationAssessment:
    """Correct hydrated-baseline aliases that are not authored duplication."""
    raw_declarations = load_modelo_declarations(modelo_dir).get("revisions", {})
    if not isinstance(raw_declarations, Mapping):
        return assessment
    required, vacated_storage_ids = _reclassification_keys(cast(Mapping[str, object], raw_declarations))
    provenance, additions = _reclassified_findings(assessment, required, vacated_storage_ids)
    reclassified = (*provenance, *additions)
    if not reclassified:
        return assessment
    provenance_counts = _finding_revision_counts(provenance)
    addition_leaves, addition_members = _addition_counts(additions)
    addition_leaf_total = sum(addition_leaves.values())
    addition_member_total = sum(len(members) for members in addition_members.values())
    return replace(
        assessment,
        genuine_overrides=assessment.genuine_overrides + len(provenance),
        redundant_overrides=assessment.redundant_overrides - len(provenance) - addition_leaf_total,
        additions=assessment.additions + addition_member_total,
        unresolved_duplication=_without_reclassified_findings(assessment, reclassified),
        by_revision_family=_adjusted_family_rows(
            assessment,
            provenance_counts,
            addition_leaves,
            addition_members,
        ),
    )
