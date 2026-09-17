"""Verify registry-wide declaration collapse without mutating live authority inputs."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass, replace
from datetime import date
from enum import StrEnum
from pathlib import Path
from typing import Final, TypedDict, cast
from uuid import uuid4

import tomlkit

from cadrumo.domain.calculations.registry.authority import (
    IndexedRegistryAuthority,
    PinnedAuthorityOperation,
    ValidatedRegistryAuthority,
)
from cadrumo.domain.calculations.registry.facts.resolution import (
    BracketFactQuery,
    EntitySetFactQuery,
    EventFactQuery,
    GovernedFactQuery,
    MappingFactQuery,
    MultiOutputFactQuery,
    OverrideFactQuery,
    ScalarFactQuery,
)
from cadrumo.domain.calculations.registry.facts.schema import GovernedFactFamily
from cadrumo.domain.calculations.registry.keyed_families import CANONICAL_FAMILY_SPECS
from cadrumo.domain.calculations.registry.revision_order import revisions_coexist
from cadrumo.domain.calculations.registry.schema import (
    REVISION_SCHEMA_FAMILY_FIELDS,
    ModeloDefinition,
    ModeloRevision,
    SupportedFilingYearsCatalogue,
)
from cadrumo.domain.calculations.registry.schema_surfaces import CasillaDefinition
from cadrumo.domain.calculations.registry.temporal import (
    RevisionSelectionMetadata,
    revision_temporal_resolution,
    select_revision,
)
from dev._paths import REPO_ROOT
from dev.registry.compiler.authority import compile_validated_authority
from dev.registry.compiler.loader import clear_registry_tree_cache, load_modelo_declarations, load_modelo_directory
from dev.registry.compiler.loader_cache import discover_modelo_sources
from dev.registry.compiler.source_evidence_fingerprint import collect_source_evidence_fingerprints
from dev.registry.edition_delta_migration import (
    MigrationAssessment,
    assess_migration_state,
    migrate_modelo,
)
from dev.registry.edition_round_trip import copy_registry_tree
from dev.registry.pipeline.authority_publication import publish_sqlite_authority_candidate

_MODELOS: Final = "modelos"
_REPRESENTATION_ONLY: Final = frozenset(
    {
        "inherited_from",
        "predecessor",
        "casilla_storage_baseline",
        "casilla_overrides",
        "casilla_removals",
        "casilla_positions",
        "lineage_attestations",
        "family_storage_baseline",
        "family_overrides",
        "family_removals",
        "family_positions",
        "cleared_families",
        "scoped_families",
    }
)
_TOOL_INPUTS: Final = (
    "dev/registry/registry_collapse_verification.py",
    "dev/registry/edition_delta_migration.py",
    "dev/registry/edition_family_delta.py",
    "dev/registry/compiler/loader.py",
    "dev/registry/compiler/loader_materialisation.py",
    "dev/registry/compiler/edition_materialisation.py",
    "dev/registry/compiler/authority.py",
    "dev/registry/compiler/authority_database.py",
    "dev/registry/pipeline/authority_publication.py",
    "src/cadrumo/domain/calculations/registry/keyed_families.py",
    "src/cadrumo/domain/calculations/registry/schema.py",
    "src/cadrumo/domain/calculations/registry/temporal.py",
    "src/cadrumo/domain/calculations/registry/authority.py",
    "src/cadrumo/domain/calculations/registry/facts/resolution.py",
)
_FACT_QUERY_TYPES: Final = {
    GovernedFactFamily.SCALAR: ScalarFactQuery,
    GovernedFactFamily.BRACKET: BracketFactQuery,
    GovernedFactFamily.MAPPING: MappingFactQuery,
    GovernedFactFamily.ENTITY_SET: EntitySetFactQuery,
    GovernedFactFamily.OVERRIDE: OverrideFactQuery,
    GovernedFactFamily.EVENT: EventFactQuery,
    GovernedFactFamily.MULTI_OUTPUT: MultiOutputFactQuery,
}
_EXPECTED_ASSESSMENT_FAMILIES: Final = REVISION_SCHEMA_FAMILY_FIELDS | frozenset(
    spec.section for spec in CANONICAL_FAMILY_SPECS if spec.singleton
)
_TECHNICAL_ROOT_CAUSES: Final = frozenset(
    {
        "overlapping_predecessor",
        "row_order",
        "unretired_withdrawal",
        "predecessor_row_without_lineage",
        "ambiguous_lineage",
        "undeclared_repurpose",
        "transformation_failed",
    }
)


class ModeloOutcome(StrEnum):
    """Closed per-model result vocabulary for registry-wide execution."""

    ALREADY_MINIMAL = "already_minimal"
    CONVERTED = "converted_candidate"
    PARTIAL = "partially_converted"
    REFUSED = "refused"
    UNASSESSED = "unassessed_dependency"


class CheckStatus(StrEnum):
    """Machine-readable status for one verification limb."""

    PASSED = "passed"
    FAILED = "failed"
    UNRESOLVED = "unresolved"
    NOT_APPLICABLE = "not_applicable"


class RootEligibility(StrEnum):
    """Storage-baseline eligibility of one revision/family edge."""

    EXISTING_INHERITANCE = "valid_existing_inheritance"
    CANDIDATE = "storage_baseline_candidate"
    INCOMPATIBLE = "incompatible_branch"
    UNRESOLVED = "unresolved_baseline_eligibility"
    FIRST_REVISION = "first_revision"


@dataclass(frozen=True, slots=True)
class FingerprintEntry:
    """One immutable file-content receipt."""

    path: str
    sha256: str
    bytes: int


@dataclass(frozen=True, slots=True)
class RequestCoordinate:
    """One canonical temporal request exercised by the verifier."""

    filing_year: int
    period: str
    on: str | None
    revision_id: str | None
    case: str


@dataclass(frozen=True, slots=True)
class ComparisonResult:
    """One independent verification result and its exact differences."""

    status: CheckStatus
    checked: int
    differences: tuple[Mapping[str, object], ...] = ()
    detail: str | None = None


class FindingTransition(TypedDict):
    """Exact finding-set delta between two measurements."""

    removed: list[str]
    added: list[str]
    unchanged: int


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def fingerprint_tree(root: Path) -> tuple[FingerprintEntry, ...]:
    """Fingerprint every file beneath ``root`` in deterministic path order."""
    resolved = root.resolve(strict=True)
    return tuple(
        FingerprintEntry(path.relative_to(resolved).as_posix(), _sha256(path), path.stat().st_size)
        for path in sorted(item for item in resolved.rglob("*") if item.is_file())
    )


def fingerprint_paths(paths: Iterable[Path], *, relative_to: Path) -> tuple[FingerprintEntry, ...]:
    """Fingerprint explicit files, retaining a stable repository-relative identity."""
    root = relative_to.resolve(strict=True)
    return tuple(
        FingerprintEntry(path.resolve(strict=True).relative_to(root).as_posix(), _sha256(path), path.stat().st_size)
        for path in sorted({item.resolve(strict=True) for item in paths})
    )


def fingerprint_digest(entries: Iterable[FingerprintEntry]) -> str:
    """Return one digest that commits to file names, sizes, and contents."""
    digest = hashlib.sha256()
    for entry in entries:
        digest.update(entry.path.encode())
        digest.update(b"\0")
        digest.update(str(entry.bytes).encode())
        digest.update(b"\0")
        digest.update(entry.sha256.encode())
        digest.update(b"\0")
    return f"sha256:{digest.hexdigest()}"


def _typed_projection(value: object) -> object:
    dump = getattr(value, "model_dump", None)
    if callable(dump):
        return _typed_projection(dump(mode="json"))
    if isinstance(value, Mapping):
        return {
            str(key): _typed_projection(child) for key, child in value.items() if str(key) not in _REPRESENTATION_ONLY
        }
    if isinstance(value, list | tuple):
        return [_typed_projection(child) for child in value]
    return value


def _first_difference(left: object, right: object, path: str = "$") -> Mapping[str, object] | None:
    if type(left) is not type(right):
        return {"location": path, "before": left, "after": right, "reason": "type_changed"}
    if isinstance(left, Mapping) and isinstance(right, Mapping):
        if tuple(left) != tuple(right):
            return {
                "location": path,
                "before": list(left),
                "after": list(right),
                "reason": "mapping_keys_or_order_changed",
            }
        for key in left:
            difference = _first_difference(left[key], right[key], f"{path}.{key}")
            if difference is not None:
                return difference
        return None
    if isinstance(left, list) and isinstance(right, list):
        if len(left) != len(right):
            return {"location": path, "before": len(left), "after": len(right), "reason": "length_changed"}
        for index, (before, after) in enumerate(zip(left, right, strict=True)):
            difference = _first_difference(before, after, f"{path}[{index}]")
            if difference is not None:
                return difference
        return None
    return None if left == right else {"location": path, "before": left, "after": right, "reason": "value_changed"}


def compare_modelos(before: ModeloDefinition, after: ModeloDefinition) -> ComparisonResult:
    """Compare complete typed meaning after validating storage-sidecar projection."""
    sidecar_gaps = (*_lineage_attestation_projection_gaps(before), *_lineage_attestation_projection_gaps(after))
    if sidecar_gaps:
        return ComparisonResult(CheckStatus.FAILED, len(before.revisions), sidecar_gaps)
    left, right = _typed_projection(before), _typed_projection(after)
    difference = _first_difference(left, right)
    return ComparisonResult(
        status=CheckStatus.PASSED if difference is None else CheckStatus.FAILED,
        checked=len(before.revisions),
        differences=() if difference is None else (difference,),
    )


def _lineage_attestation_projection_gaps(modelo: ModeloDefinition) -> tuple[Mapping[str, object], ...]:
    """Require every excluded lineage sidecar to repeat its effective casilla provenance."""
    gaps: list[Mapping[str, object]] = []
    for revision_id, revision in modelo.revisions.items():
        by_lineage: dict[str, list[CasillaDefinition]] = {}
        for casilla in revision.casillas:
            if casilla.continuidad_id is not None:
                by_lineage.setdefault(str(casilla.continuidad_id), []).append(casilla)
        for attestation in revision.lineage_attestations:
            if attestation.family != "casillas" or attestation.continuidad_id is None:
                gaps.append(
                    {
                        "location": f"$.revisions.{revision_id}.lineage_attestations",
                        "reason": "unsupported_lineage_attestation_projection",
                        "family": attestation.family,
                    }
                )
                continue
            matches = by_lineage.get(str(attestation.continuidad_id), ())
            if len(matches) != 1:
                gaps.append(
                    {
                        "location": f"$.revisions.{revision_id}.lineage_attestations",
                        "reason": "lineage_attestation_target_not_unique",
                        "continuidad_id": str(attestation.continuidad_id),
                    }
                )
                continue
            casilla = matches[0]
            projected = {
                "origin": casilla.continuidad_origin,
                "evidence": casilla.continuidad_evidence,
                "legal_refs": casilla.legal_refs,
                "source_refs": casilla.source_refs,
            }
            authored = {
                "origin": attestation.origin,
                "evidence": attestation.evidence,
                "legal_refs": attestation.legal_refs,
                "source_refs": attestation.source_refs,
            }
            if _typed_projection(projected) != _typed_projection(authored):
                gaps.append(
                    {
                        "location": f"$.revisions.{revision_id}.lineage_attestations.{attestation.continuidad_id}",
                        "reason": "lineage_attestation_provenance_differs_from_hydrated_casilla",
                    }
                )
    return tuple(gaps)


def normalized_assessment(modelo_dir: Path, assessment: MigrationAssessment) -> MigrationAssessment:
    """Correct hydrated-baseline aliases that are not authored duplication.

    Besides successor-default provenance overrides, a full row whose storage id
    was vacated by an inherited member's id-changing override is a new addition.
    Equal required leaves on that new row are not redundant overrides of the
    displaced predecessor member.
    """
    raw_declarations = load_modelo_declarations(modelo_dir).get("revisions", {})
    if not isinstance(raw_declarations, Mapping):
        return assessment
    declarations = cast(Mapping[str, object], raw_declarations)
    required: set[tuple[str, str]] = set()
    vacated_storage_ids: set[tuple[str, str]] = set()
    for revision_id, raw_revision in declarations.items():
        if not isinstance(raw_revision, Mapping):
            continue
        revision_table = cast(Mapping[str, object], raw_revision)
        default = revision_table.get("casilla_source_refs")
        overrides = revision_table.get("casilla_overrides", ())
        if not isinstance(overrides, list | tuple):
            continue
        for override in cast(Sequence[object], overrides):
            if not isinstance(override, Mapping):
                continue
            operation = cast(Mapping[str, object], override)
            selector, fields = operation.get("selector"), operation.get("fields")
            if not isinstance(selector, Mapping) or not isinstance(fields, Mapping):
                continue
            selector_table = cast(Mapping[str, object], selector)
            fields_table = cast(Mapping[str, object], fields)
            member, source_refs = selector_table.get("id"), fields_table.get("source_refs")
            replacement_id = fields_table.get("id")
            if isinstance(member, str) and isinstance(replacement_id, str) and replacement_id != member:
                vacated_storage_ids.add((str(revision_id), member))
            if (
                isinstance(member, str)
                and isinstance(source_refs, list | tuple)
                and isinstance(default, list | tuple)
                and not _same_typed_value(
                    tuple(cast(Sequence[object], source_refs)), tuple(cast(Sequence[object], default))
                )
            ):
                required.add((str(revision_id), member))
        predecessor_id = revision_table.get("casilla_storage_baseline", revision_table.get("predecessor"))
        predecessor = declarations.get(predecessor_id) if isinstance(predecessor_id, str) else None
        if not isinstance(predecessor, Mapping):
            continue
        predecessor_table = cast(Mapping[str, object], predecessor)
        current_rows = revision_table.get("casillas", ())
        predecessor_rows = predecessor_table.get("casillas", ())
        if not isinstance(current_rows, list | tuple) or not isinstance(predecessor_rows, list | tuple):
            continue
        predecessor_lineages = {
            str(row.get("id")): row.get("continuidad_id")
            for item in cast(Sequence[object], predecessor_rows)
            if isinstance(item, Mapping) and isinstance((row := cast(Mapping[str, object], item)).get("id"), str)
        }
        for item in cast(Sequence[object], current_rows):
            if not isinstance(item, Mapping):
                continue
            row = cast(Mapping[str, object], item)
            member, lineage = row.get("id"), row.get("continuidad_id")
            if (
                isinstance(member, str)
                and isinstance(lineage, str)
                and isinstance(predecessor_lineages.get(member), str)
                and lineage != predecessor_lineages[member]
            ):
                vacated_storage_ids.add((str(revision_id), member))
    provenance_reclassified = tuple(
        finding
        for finding in assessment.unresolved_duplication
        if finding.get("reason") == "authored override equals hydrated baseline"
        and finding.get("family") == "casillas"
        and finding.get("fields") == ["source_refs"]
        and isinstance(finding.get("revision"), str)
        and isinstance(finding.get("member"), str)
        and (cast(str, finding["revision"]), cast(str, finding["member"])) in required
    )
    addition_reclassified = tuple(
        finding
        for finding in assessment.unresolved_duplication
        if finding.get("reason") == "authored value equals hydrated baseline"
        and finding.get("family") == "casillas"
        and isinstance(finding.get("fields"), list)
        and isinstance(finding.get("revision"), str)
        and isinstance(finding.get("member"), str)
        and (cast(str, finding["revision"]), cast(str, finding["member"])) in vacated_storage_ids
    )
    reclassified = (*provenance_reclassified, *addition_reclassified)
    if not reclassified:
        return assessment
    identities = {id(finding) for finding in reclassified}
    provenance_counts: dict[str, int] = {}
    for finding in provenance_reclassified:
        revision_id = cast(str, finding["revision"])
        provenance_counts[revision_id] = provenance_counts.get(revision_id, 0) + 1
    addition_leaves: dict[str, int] = {}
    addition_members: dict[str, set[str]] = {}
    for finding in addition_reclassified:
        revision_id = cast(str, finding["revision"])
        fields = cast(list[object], finding["fields"])
        addition_leaves[revision_id] = addition_leaves.get(revision_id, 0) + len(fields)
        addition_members.setdefault(revision_id, set()).add(cast(str, finding["member"]))
    by_revision_family: list[Mapping[str, object]] = []
    for row in assessment.by_revision_family:
        revision_id = str(row.get("revision"))
        provenance_count = provenance_counts.get(revision_id, 0) if row.get("family") == "casillas" else 0
        addition_leaf_count = addition_leaves.get(revision_id, 0) if row.get("family") == "casillas" else 0
        addition_member_count = len(addition_members.get(revision_id, ())) if row.get("family") == "casillas" else 0
        if not provenance_count and not addition_leaf_count:
            by_revision_family.append(row)
            continue
        updated = dict(row)
        old_redundant = updated.get("redundant_overrides", 0)
        old_genuine = updated.get("genuine_overrides", 0)
        old_additions = updated.get("additions", 0)
        updated["redundant_overrides"] = (
            (old_redundant if isinstance(old_redundant, int) else 0) - provenance_count - addition_leaf_count
        )
        updated["genuine_overrides"] = (old_genuine if isinstance(old_genuine, int) else 0) + provenance_count
        updated["additions"] = (old_additions if isinstance(old_additions, int) else 0) + addition_member_count
        by_revision_family.append(updated)
    addition_leaf_total = sum(addition_leaves.values())
    addition_member_total = sum(len(members) for members in addition_members.values())
    return replace(
        assessment,
        genuine_overrides=assessment.genuine_overrides + len(provenance_reclassified),
        redundant_overrides=(assessment.redundant_overrides - len(provenance_reclassified) - addition_leaf_total),
        additions=assessment.additions + addition_member_total,
        unresolved_duplication=tuple(
            finding for finding in assessment.unresolved_duplication if id(finding) not in identities
        ),
        by_revision_family=tuple(by_revision_family),
    )


def finding_identities(assessment: MigrationAssessment) -> frozenset[str]:
    """Identify findings by content, so equal counts cannot hide defect replacement."""
    return frozenset(
        json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        for item in (*assessment.unresolved_duplication, *assessment.blocked_work)
    )


def finding_transition(before: MigrationAssessment, after: MigrationAssessment) -> FindingTransition:
    """Report exact finding identities added and removed between assessments."""
    old, new = finding_identities(before), finding_identities(after)
    return {"removed": sorted(old - new), "added": sorted(new - old), "unchanged": len(old & new)}


def assessor_scope_gaps() -> tuple[Mapping[str, object], ...]:
    """Independently reconcile the assessor's family policy with the typed schema."""
    enrolled = {spec.section for spec in CANONICAL_FAMILY_SPECS}
    missing = sorted(_EXPECTED_ASSESSMENT_FAMILIES - enrolled)
    unknown = sorted(enrolled - _EXPECTED_ASSESSMENT_FAMILIES)
    return tuple(
        {"revision": "*", "family": family, "reason": "assessor_family_not_enrolled"} for family in missing
    ) + tuple({"revision": "*", "family": family, "reason": "assessor_family_not_in_schema"} for family in unknown)


def assessment_coverage_gaps(
    assessment: MigrationAssessment,
    modelo: ModeloDefinition,
    *,
    stage: str,
) -> tuple[Mapping[str, object], ...]:
    """Prove every revision has one row for every family and its scalar bucket."""
    expected_families = (*sorted(_EXPECTED_ASSESSMENT_FAMILIES), "$scalars")
    expected = {(str(revision_id), family) for revision_id in modelo.revisions for family in expected_families}
    actual = {(str(row.get("revision")), str(row.get("family"))) for row in assessment.by_revision_family}
    return tuple(
        {
            "stage": stage,
            "revision": revision,
            "family": family,
            "reason": "assessment_row_missing",
        }
        for revision, family in sorted(expected - actual)
    ) + tuple(
        {
            "stage": stage,
            "revision": revision,
            "family": family,
            "reason": "unexpected_assessment_row",
        }
        for revision, family in sorted(actual - expected)
    )


def root_eligibility(modelo_dir: Path) -> tuple[Mapping[str, object], ...]:
    """Classify every revision/family edge without treating an explicit root as invisible."""
    try:
        declarations = load_modelo_declarations(modelo_dir).get("revisions", {})
    except Exception as exc:  # each modelo must still receive an outcome
        return ({"revision": "*", "family": "*", "status": RootEligibility.UNRESOLVED, "detail": str(exc)},)
    if not isinstance(declarations, Mapping):
        return (
            {
                "revision": "*",
                "family": "*",
                "status": RootEligibility.UNRESOLVED,
                "detail": "revisions is not a mapping",
            },
        )
    metadata: list[RevisionSelectionMetadata] = []
    invalid: dict[str, str] = {}
    for raw_revision_id, raw_revision in declarations.items():
        if not isinstance(raw_revision, Mapping):
            invalid[str(raw_revision_id)] = "revision is not a mapping"
            continue
        try:
            metadata.append(
                RevisionSelectionMetadata.model_validate(
                    {
                        "id": str(raw_revision_id),
                        "valid_from": raw_revision.get("valid_from"),
                        "valid_to": raw_revision.get("valid_to"),
                        "period_selector": raw_revision.get("period_selector"),
                        "deadline_windows": raw_revision.get("deadline_windows", ()),
                    }
                )
            )
        except Exception as exc:
            invalid[str(raw_revision_id)] = f"{type(exc).__name__}: {exc}"
    ordered = sorted(metadata, key=lambda item: (item.valid_from, str(item.id)))
    rows: list[Mapping[str, object]] = []
    previous = None
    for revision in ordered:
        revision_id = str(revision.id)
        raw = declarations.get(revision_id)
        for spec in CANONICAL_FAMILY_SPECS:
            family_baseline = "casilla_storage_baseline" if spec.section == "casillas" else "family_storage_baseline"
            baseline = raw.get(family_baseline) if isinstance(raw, Mapping) else None
            predecessor = raw.get("predecessor") if isinstance(raw, Mapping) else None
            named = baseline if isinstance(baseline, str) else predecessor if isinstance(predecessor, str) else None
            explicit_root = isinstance(predecessor, Mapping)
            if previous is None:
                status, candidate = RootEligibility.FIRST_REVISION, None
            elif named is not None:
                status, candidate = RootEligibility.EXISTING_INHERITANCE, named
            elif (
                (explicit_root and not _technical_root_declaration(cast(Mapping[str, object], raw)))
                or revisions_coexist(cast("ModeloRevision", previous), cast("ModeloRevision", revision))
                or not spec.inherited
            ):
                status, candidate = RootEligibility.INCOMPATIBLE, str(previous.id)
            elif not isinstance(raw, Mapping):
                status, candidate = RootEligibility.UNRESOLVED, str(previous.id)
            else:
                status, candidate = RootEligibility.CANDIDATE, str(previous.id)
            rows.append(
                {
                    "revision": revision_id,
                    "family": spec.section,
                    "status": status,
                    "candidate": candidate,
                    "explicit_root": explicit_root,
                }
            )
        previous = revision
    for revision_id, detail in sorted(invalid.items()):
        rows.extend(
            {
                "revision": revision_id,
                "family": spec.section,
                "status": RootEligibility.UNRESOLVED,
                "candidate": None,
                "explicit_root": False,
                "detail": detail,
            }
            for spec in CANONICAL_FAMILY_SPECS
        )
    return tuple(rows)


def _technical_root_declaration(raw_revision: Mapping[str, object]) -> bool:
    """Return whether an explicit root records a converter limitation, not law/topology."""
    predecessor = raw_revision.get("predecessor")
    none = cast(Mapping[str, object], predecessor).get("none") if isinstance(predecessor, Mapping) else None
    if not isinstance(none, Mapping):
        return False
    declaration = cast(Mapping[str, object], none)
    cause = declaration.get("cause")
    if isinstance(cause, str):
        return cause in _TECHNICAL_ROOT_CAUSES
    reason = str(declaration.get("reason", "")).lower()
    return any(cause in reason for cause in _TECHNICAL_ROOT_CAUSES) or "migration" in reason or "lineage" in reason


def _raw_members(value: object, *, singleton: bool) -> tuple[Mapping[str, object], ...]:
    if singleton:
        return (cast(Mapping[str, object], value),) if isinstance(value, Mapping) else ()
    if not isinstance(value, list | tuple):
        return ()
    return tuple(cast(Mapping[str, object], item) for item in value if isinstance(item, Mapping))


def _raw_leaves(value: object, prefix: tuple[str, ...] = ()) -> dict[tuple[str, ...], object]:
    if not isinstance(value, Mapping) or not value:
        return {prefix: value}
    leaves: dict[tuple[str, ...], object] = {}
    for key, child in value.items():
        leaves.update(_raw_leaves(child, (*prefix, str(key))))
    return leaves


def _same_typed_value(left: object, right: object) -> bool:
    if type(left) is not type(right):
        return False
    if isinstance(left, Mapping) and isinstance(right, Mapping):
        return tuple(left) == tuple(right) and all(_same_typed_value(left[key], right[key]) for key in left)
    if isinstance(left, list | tuple) and isinstance(right, list | tuple):
        return len(left) == len(right) and all(
            _same_typed_value(old, new) for old, new in zip(left, right, strict=True)
        )
    return left == right


def root_overlap_diagnostics(
    modelo_dir: Path,
    eligibility: Sequence[Mapping[str, object]] | None = None,
) -> tuple[Mapping[str, object], ...]:
    """Expose same-storage-id root overlap as diagnostic evidence, never accepted identity."""
    declarations = load_modelo_declarations(modelo_dir).get("revisions", {})
    if not isinstance(declarations, Mapping):
        return ()
    rows = root_eligibility(modelo_dir) if eligibility is None else eligibility
    specs = {spec.section: spec for spec in CANONICAL_FAMILY_SPECS}
    findings: list[Mapping[str, object]] = []
    for row in rows:
        if row.get("status") is not RootEligibility.CANDIDATE:
            continue
        revision_id, baseline_id, family = row.get("revision"), row.get("candidate"), row.get("family")
        if not all(isinstance(value, str) for value in (revision_id, baseline_id, family)):
            continue
        spec = specs.get(family)
        current = declarations.get(revision_id)
        baseline = declarations.get(baseline_id)
        if spec is None or not isinstance(current, Mapping) or not isinstance(baseline, Mapping):
            continue
        old = {
            str(item.get(spec.storage_identity)): item
            for item in _raw_members(baseline.get(family), singleton=spec.singleton)
            if item.get(spec.storage_identity) is not None
        }
        for member in _raw_members(current.get(family), singleton=spec.singleton):
            identity = member.get(spec.storage_identity)
            inherited = old.get(str(identity))
            if identity is None or inherited is None:
                continue
            left, right = _raw_leaves(member), _raw_leaves(inherited)
            equal = sorted(
                ".".join(path)
                for path, value in left.items()
                if path
                and path[0] not in _REPRESENTATION_ONLY | {spec.storage_identity}
                and path in right
                and _same_typed_value(value, right[path])
            )
            if equal:
                findings.append(
                    {
                        "revision": revision_id,
                        "family": family,
                        "member": str(identity),
                        "fields": equal,
                        "reason": "raw same-storage-id overlap requires baseline conversion proof",
                    }
                )
    return tuple(findings)


def _root_gaps(rows: Sequence[Mapping[str, object]]) -> tuple[Mapping[str, object], ...]:
    return tuple(row for row in rows if row.get("status") in {RootEligibility.CANDIDATE, RootEligibility.UNRESOLVED})


def _selector_years(modelo: ModeloDefinition, revision_id: str, *, floor: int, ceiling: int) -> tuple[int, ...]:
    selector = modelo.revisions[revision_id].period_selector
    if selector.years:
        return tuple(year for year in selector.years if floor <= year <= ceiling)
    start = max(selector.year_from or floor, floor)
    end = min(selector.year_to if selector.year_to is not None else ceiling, ceiling)
    return tuple(range(start, end + 1)) if start <= end else ()


def request_matrix(modelo: ModeloDefinition, *, floor: int, ceiling: int) -> tuple[RequestCoordinate, ...]:
    """Derive exact, boundary, gap, and support-edge requests from canonical metadata."""
    coordinates: dict[tuple[object, ...], RequestCoordinate] = {}
    authored_years: set[int] = set()
    period_tokens: set[str] = set()
    for revision_id, revision in modelo.revisions.items():
        years = _selector_years(modelo, str(revision_id), floor=floor, ceiling=ceiling)
        authored_years.update(years)
        for year in years:
            for period in revision.period_selector.periods_for_year(year):
                token = str(period)
                period_tokens.add(token)
                for on, case in ((None, "exact"), (revision.valid_from, "valid_from"), (revision.valid_to, "valid_to")):
                    if on is None and case != "exact":
                        continue
                    coordinate = RequestCoordinate(
                        year,
                        token,
                        None if on is None else on.isoformat(),
                        str(revision_id),
                        case,
                    )
                    coordinates[(year, token, coordinate.on, str(revision_id))] = coordinate
    for period in sorted(period_tokens):
        for year, case in ((floor, "support_floor"), (ceiling, "support_ceiling")):
            coordinate = RequestCoordinate(year, period, None, None, case)
            coordinates[(year, period, None, None)] = coordinate
        if authored_years:
            for year in range(max(floor, min(authored_years)), min(ceiling, max(authored_years)) + 1):
                if year not in authored_years:
                    coordinate = RequestCoordinate(year, period, None, None, "internal_gap")
                    coordinates[(year, period, None, None)] = coordinate
    ordered = sorted(
        coordinates,
        key=lambda item: tuple("" if value is None else str(value) for value in item),
    )
    return tuple(coordinates[key] for key in ordered)


def _selection_result(
    modelo: ModeloDefinition,
    coordinate: RequestCoordinate,
    support: SupportedFilingYearsCatalogue,
) -> Mapping[str, object]:
    try:
        selected = select_revision(
            modelo,
            filing_year=coordinate.filing_year,
            period=coordinate.period,
            on=None if coordinate.on is None else date.fromisoformat(coordinate.on),
            revision_id=coordinate.revision_id,
            support=support,
        )
        resolution = revision_temporal_resolution(
            selected,
            filing_year=coordinate.filing_year,
            period=coordinate.period,
            support=support,
        )
        return {
            "outcome": "selected",
            "revision": str(selected.id),
            "requested_filing_year": resolution.requested_filing_year,
            "authored_filing_year": resolution.authored_filing_year,
            "projection_direction": str(resolution.projection_direction),
            "value": _typed_projection(selected),
        }
    except Exception as exc:
        return {"outcome": "refused", "error_type": type(exc).__name__, "detail": str(exc)}


def compare_temporal(
    before: ModeloDefinition,
    after: ModeloDefinition,
    *,
    support: SupportedFilingYearsCatalogue,
    floor: int,
    ceiling: int,
) -> ComparisonResult:
    """Compare canonical temporal selection and complete selected typed meaning."""
    differences: list[Mapping[str, object]] = []
    matrix = request_matrix(before, floor=floor, ceiling=ceiling)
    for coordinate in matrix:
        left = _selection_result(before, coordinate, support)
        right = _selection_result(after, coordinate, support)
        difference = _first_difference(left, right)
        if difference is not None:
            differences.append({"coordinate": asdict(coordinate), **difference})
    return ComparisonResult(
        status=CheckStatus.PASSED if not differences else CheckStatus.FAILED,
        checked=len(matrix),
        differences=tuple(differences),
    )


def _fact_projection(value: object) -> object:
    """Compare fact meaning while checking each generation digest separately."""
    projected = _typed_projection(value)
    if isinstance(projected, Mapping):
        return {key: child for key, child in projected.items() if key != "authority_digest"}
    return projected


def _fact_queries(authority: ValidatedRegistryAuthority) -> tuple[GovernedFactQuery, ...]:
    catalogue = authority.catalogues.facts
    envelope = authority.catalogues.require_supported_filing_years().date_envelope()
    queries: dict[str, GovernedFactQuery] = {}
    for fact in catalogue.facts.values():
        windows = fact.materialized_windows(envelope)
        query_type = _FACT_QUERY_TYPES[fact.family]
        for variant in fact.variants:
            window = windows[variant.variant_id]
            effective_date = max(window.valid_from, envelope.floor)
            if (window.valid_to is not None and window.valid_to < effective_date) or not envelope.admits_coordinate(
                effective_date
            ):
                continue
            filing_year = period = None
            selector = variant.period_selector
            if selector is not None:
                filing_year = selector.years[0] if selector.years else selector.year_from
                if filing_year is None:
                    continue
                period = str(selector.periods_for_year(filing_year)[0])
            query = query_type(
                fact_id=fact.fact_id,
                date_axis=variant.date_axis,
                effective_date=effective_date,
                selectors=variant.selectors,
                filing_year=filing_year,
                period=period,
            )
            key = json.dumps(query.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
            queries[key] = query
    return tuple(queries[key] for key in sorted(queries))


def _fact_result(resolve: Callable[[GovernedFactQuery], object], query: GovernedFactQuery) -> Mapping[str, object]:
    try:
        value = resolve(query)
        digest = getattr(value, "authority_digest", None)
        return {
            "outcome": "resolved",
            "authority_digest_valid": isinstance(digest, str) and len(digest) == 64,
            "value": _fact_projection(value),
        }
    except Exception as exc:
        return {"outcome": "refused", "error_type": type(exc).__name__, "detail": str(exc)}


def _snapshot_result(
    snapshot: Callable[..., object], modelo_id: str, coordinate: RequestCoordinate
) -> Mapping[str, object]:
    try:
        value = snapshot(
            modelo_id,
            filing_year=coordinate.filing_year,
            period=coordinate.period,
            on=None if coordinate.on is None else date.fromisoformat(coordinate.on),
            revision_id=coordinate.revision_id,
        )
        return {"outcome": "admitted", "value": _typed_projection(value)}
    except Exception as exc:
        return {"outcome": "refused", "error_type": type(exc).__name__, "detail": str(exc)}


def _indexed_selection_result(
    operation: PinnedAuthorityOperation,
    modelo_id: str,
    coordinate: RequestCoordinate,
) -> Mapping[str, object]:
    try:
        directory = operation.modelo_directory(modelo_id)
        selected = operation.revision_for_context(
            modelo_id,
            filing_year=coordinate.filing_year,
            period=coordinate.period,
            on=None if coordinate.on is None else date.fromisoformat(coordinate.on),
            revision_id=coordinate.revision_id,
        )
        resolution = revision_temporal_resolution(
            selected,
            filing_year=coordinate.filing_year,
            period=coordinate.period,
            support=directory.supported_filing_years,
        )
        return {
            "outcome": "selected",
            "revision": str(selected.id),
            "requested_filing_year": resolution.requested_filing_year,
            "authored_filing_year": resolution.authored_filing_year,
            "projection_direction": str(resolution.projection_direction),
            "value": _typed_projection(selected),
        }
    except Exception as exc:
        return {"outcome": "refused", "error_type": type(exc).__name__, "detail": str(exc)}


def _revision_inventory(modelo: ModeloDefinition) -> tuple[Mapping[str, object], ...]:
    return tuple(
        {
            "revision": str(revision.id),
            "valid_from": revision.valid_from.isoformat(),
            "valid_to": None if revision.valid_to is None else revision.valid_to.isoformat(),
            "years": list(revision.period_selector.years),
            "year_from": revision.period_selector.year_from,
            "year_to": revision.period_selector.year_to,
            "periods": [str(period) for period in revision.period_selector.declared_periods],
        }
        for revision in sorted(modelo.revisions.values(), key=lambda item: (item.valid_from, str(item.id)))
    )


def _file_change_count(before: tuple[FingerprintEntry, ...], after: tuple[FingerprintEntry, ...]) -> int:
    left = {item.path: item.sha256 for item in before}
    right = {item.path: item.sha256 for item in after}
    return sum(left.get(path) != right.get(path) for path in set(left) | set(right))


def _assessment_accounting(results: Sequence[Mapping[str, object]], key: str) -> Mapping[str, int]:
    totals = {
        "authored_payload_fields": 0,
        "inherited_payload_fields": 0,
        "genuine_overrides": 0,
        "redundant_overrides": 0,
        "additions": 0,
        "removals": 0,
        "structural_overhead": 0,
        "findings": 0,
        "repeated_values": 0,
        "coverage_gaps": 0,
    }
    for result in results:
        assessment = result.get(key)
        if not isinstance(assessment, Mapping):
            continue
        for name in tuple(totals)[:7]:
            value = assessment.get(name)
            if isinstance(value, int):
                totals[name] += value
        findings = assessment.get("unresolved_duplication")
        if isinstance(findings, list | tuple):
            totals["findings"] += len(findings)
            totals["repeated_values"] += sum(
                len(fields)
                for item in findings
                if isinstance(item, Mapping) and isinstance((fields := item.get("fields")), list | tuple)
            )
        gaps = assessment.get("blocked_work")
        if isinstance(gaps, list | tuple):
            totals["coverage_gaps"] += len(gaps)
        assessor_gaps = result.get("assessor_scope_gaps")
        if isinstance(assessor_gaps, list | tuple):
            totals["coverage_gaps"] += len(assessor_gaps)
    return totals


def _copy_modelo(source: Path, destination: Path) -> None:
    if destination.exists():
        raise RuntimeError(f"candidate path already exists: {destination}")
    shutil.copytree(source, destination)


def canonical_converter(source: Path, candidate: Path) -> Mapping[str, object]:
    """Invoke Lane 1's complete generalized migration orchestration without applying."""
    registry_root = source.parent.parent.resolve(strict=True)
    modelo_id = source.name
    candidate_registry = candidate.parent.parent.resolve(strict=True)
    for dependency in registry_root.iterdir():
        if dependency.name == _MODELOS:
            continue
        target = candidate_registry / dependency.name
        if target.exists():
            continue
        if dependency.is_dir():
            shutil.copytree(dependency, target)
        else:
            shutil.copy2(dependency, target)
    candidates_root = next((parent for parent in candidate.parents if parent.name == "candidates"), None)
    if candidates_root is None:
        raise RuntimeError(f"candidate path has no candidates scratch ancestor: {candidate}")
    runs_root = candidates_root.parent / "converter-runs"
    runs_root.mkdir(parents=True, exist_ok=True)
    closure_root = copy_registry_tree(
        registry_root,
        runs_root / f"{modelo_id}-{uuid4().hex}-dependencies" / "registry" / "aeat",
        modelo_id=modelo_id,
    )
    candidate_modelos = candidate_registry / _MODELOS
    for dependency in (closure_root / _MODELOS).iterdir():
        target = candidate_modelos / dependency.name
        if dependency.name != modelo_id and not target.exists():
            shutil.copytree(dependency, target)
    work_dir = runs_root / f"{modelo_id}-{uuid4().hex}"
    outcome = migrate_modelo(
        registry_root=registry_root,
        modelo_id=modelo_id,
        work_dir=work_dir,
        export_scenarios={},
        apply=False,
    )
    if outcome.staged_registry is not None:
        staged = outcome.staged_registry / _MODELOS / modelo_id
        resolved_candidate = candidate.resolve(strict=True)
        resolved_parent = candidate.parent.resolve(strict=True)
        if resolved_candidate.parent != resolved_parent:
            raise RuntimeError(f"candidate path escaped its scratch parent: {resolved_candidate}")
        shutil.rmtree(resolved_candidate)
        shutil.copytree(staged, resolved_candidate)
    return {
        "changed": outcome.changed,
        "complete": outcome.complete,
        "source_status": outcome.source_status,
        "publication_readiness_status": outcome.publication_readiness_status,
        "completed_revisions": outcome.completed,
        "unchanged_revisions": outcome.unchanged,
        "blocked_revisions": outcome.blocked,
        "source_findings": [asdict(finding) for finding in outcome.source_findings],
        "publication_readiness_findings": [asdict(finding) for finding in outcome.publication_readiness_findings],
        "work_dir": str(work_dir),
    }


def _source_dependency_paths(source_root: Path) -> tuple[Path, ...]:
    """Enumerate every non-registry compiler input that must be isolated."""
    evidence = tuple(
        Path(path) for path, _size, _modified_ns in collect_source_evidence_fingerprints(source_root, use_cache=False)
    )
    profile_root = source_root / "registry" / "cadrumo"
    profiles = tuple(path for path in profile_root.rglob("*") if path.is_file())
    return tuple(sorted(set((*evidence, *profiles))))


def _copy_source_dependencies(paths: Iterable[Path], *, source_root: Path, destination: Path) -> None:
    """Copy exact compiler inputs while retaining source-root-relative paths."""
    resolved_root = source_root.resolve(strict=True)
    for source in paths:
        relative = source.resolve(strict=True).relative_to(resolved_root)
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)


def _cache_invalidation_probe(registry_root: Path, probe_root: Path) -> Mapping[str, object]:
    """Exercise warm reuse and source/support invalidation on isolated copies."""
    try:
        source = discover_modelo_sources(registry_root / _MODELOS)[0].path
        modelo_probe = probe_root / "modelo"
        shutil.copytree(source, modelo_probe)
        cold = load_modelo_directory(modelo_probe)
        warm = load_modelo_directory(modelo_probe)
        manifest = modelo_probe / "manifest.toml"
        manifest.write_text(manifest.read_text(encoding="utf-8") + "\n", encoding="utf-8", newline="\n")
        changed = load_modelo_directory(modelo_probe)
        source_invalidated = (
            cold is warm and changed is not warm and _typed_projection(changed) == _typed_projection(warm)
        )

        legal_probe = probe_root / "registry" / "legal"
        shutil.copytree(registry_root / "legal", legal_probe)
        from dev.registry.compiler.loader import load_shared_catalogues

        support_before = load_shared_catalogues(legal_probe.parent).supported_filing_years
        support_file = next(
            path
            for path in sorted(legal_probe.glob("*.toml"))
            if "[supported_filing_years]" in path.read_text(encoding="utf-8")
        )
        document = tomlkit.parse(support_file.read_text(encoding="utf-8"))
        table = document["supported_filing_years"]
        floor, horizon = int(table["floor"]), int(table["horizon"])
        hard_ceiling = table.get("hard_ceiling")
        if hard_ceiling is None or horizon < int(hard_ceiling):
            table["horizon"] = horizon + 1
        elif floor < horizon:
            table["horizon"] = horizon - 1
        else:
            table["hard_ceiling"] = int(hard_ceiling) + 1
        support_file.write_text(tomlkit.dumps(document), encoding="utf-8", newline="\n")
        try:
            support_after = load_shared_catalogues(legal_probe.parent).supported_filing_years
            support_invalidated = _typed_projection(support_before) != _typed_projection(support_after)
            support_detail = None
        except Exception as exc:
            support_invalidated = True
            support_detail = f"changed support metadata refused: {type(exc).__name__}: {exc}"
        status = CheckStatus.PASSED if source_invalidated and support_invalidated else CheckStatus.FAILED
        return {
            "status": status,
            "cold_warm_same_object": cold is warm,
            "source_change_invalidated": source_invalidated,
            "support_change_invalidated": support_invalidated,
            "detail": support_detail,
        }
    except Exception as exc:
        return {"status": CheckStatus.FAILED, "detail": f"{type(exc).__name__}: {exc}"}


def _verify_one(
    modelo_id: str,
    source: Path,
    candidate: Path,
    *,
    support: SupportedFilingYearsCatalogue,
    floor: int,
    ceiling: int,
    converter: Callable[[Path, Path], Mapping[str, object]] = canonical_converter,
) -> dict[str, object]:
    before_files = fingerprint_tree(source)
    static_scope_gaps = assessor_scope_gaps()
    roots = root_eligibility(source)
    root_overlap = root_overlap_diagnostics(source, roots)
    try:
        before_assessment = normalized_assessment(source, assess_migration_state(source))
        before = load_modelo_directory(source)
        source_scope_gaps = assessment_coverage_gaps(before_assessment, before, stage="source")
    except Exception as exc:
        return {
            "modelo": modelo_id,
            "outcome": ModeloOutcome.UNASSESSED,
            "source_path": str(source),
            "candidate_path": str(candidate),
            "source_fingerprint": fingerprint_digest(before_files),
            "candidate_fingerprint": None,
            "root_eligibility": roots,
            "root_overlap_diagnostics": root_overlap,
            "assessor_scope_gaps": static_scope_gaps,
            "assessment_dependency": f"{type(exc).__name__}: {exc}",
            "source_apply_readiness": CheckStatus.FAILED,
            "authority_publication_readiness": CheckStatus.UNRESOLVED,
        }
    _copy_modelo(source, candidate)
    converter_report: Mapping[str, object] | None = None
    defect: str | None = None
    try:
        converter_report = converter(source, candidate)
    except Exception as exc:
        defect = f"{type(exc).__name__}: {exc}"
    after_files = fingerprint_tree(candidate)
    changed_files = _file_change_count(before_files, after_files)
    try:
        after_assessment = normalized_assessment(candidate, assess_migration_state(candidate))
        after = load_modelo_directory(candidate)
        candidate_scope_gaps = assessment_coverage_gaps(after_assessment, after, stage="candidate")
        roots_after = root_eligibility(candidate)
        equivalence = compare_modelos(before, after)
        temporal = compare_temporal(before, after, support=support, floor=floor, ceiling=ceiling)
    except Exception as exc:
        after_assessment = None
        candidate_scope_gaps = ()
        roots_after = root_eligibility(candidate)
        equivalence = ComparisonResult(CheckStatus.FAILED, 0, detail=f"{type(exc).__name__}: {exc}")
        temporal = ComparisonResult(CheckStatus.UNRESOLVED, 0, detail="candidate did not hydrate")
    idempotence = ComparisonResult(CheckStatus.UNRESOLVED, 0)
    if defect is None and after_assessment is not None:
        first_digest = fingerprint_digest(after_files)
        try:
            converter(candidate, candidate)
            repeated = fingerprint_tree(candidate)
            second_digest = fingerprint_digest(repeated)
            idempotence = ComparisonResult(
                CheckStatus.PASSED if first_digest == second_digest else CheckStatus.FAILED,
                1,
                ()
                if first_digest == second_digest
                else ({"location": "$files", "before": first_digest, "after": second_digest},),
            )
        except Exception as exc:
            idempotence = ComparisonResult(CheckStatus.FAILED, 1, detail=f"{type(exc).__name__}: {exc}")
    scope_gaps = (*static_scope_gaps, *source_scope_gaps, *candidate_scope_gaps)
    complete = bool(
        defect is None
        and after_assessment is not None
        and after_assessment.minimal
        and not scope_gaps
        and not _root_gaps(roots_after)
        and equivalence.status is CheckStatus.PASSED
        and temporal.status is CheckStatus.PASSED
        and idempotence.status is CheckStatus.PASSED
    )
    honest_noop = before_assessment.minimal and changed_files == 0
    if complete and honest_noop:
        outcome = ModeloOutcome.ALREADY_MINIMAL
    elif complete:
        outcome = ModeloOutcome.CONVERTED
    elif defect is not None:
        outcome = ModeloOutcome.REFUSED
    elif after_assessment is None:
        outcome = ModeloOutcome.UNASSESSED
    else:
        outcome = ModeloOutcome.PARTIAL
        if not before_assessment.minimal and changed_files == 0:
            defect = "converter_claimed_completion_without_changing_nonminimal_input"
    source_readiness = CheckStatus.PASSED if complete else CheckStatus.FAILED
    return {
        "modelo": modelo_id,
        "outcome": outcome,
        "source_path": str(source),
        "candidate_path": str(candidate),
        "source_fingerprint": fingerprint_digest(before_files),
        "candidate_fingerprint": fingerprint_digest(fingerprint_tree(candidate)),
        "authored_revisions": _revision_inventory(before),
        "root_eligibility": roots,
        "root_overlap_diagnostics": root_overlap,
        "candidate_root_eligibility": roots_after,
        "candidate_root_gaps": _root_gaps(roots_after),
        "assessor_scope_gaps": scope_gaps,
        "before_bytes": sum(item.bytes for item in before_files),
        "after_bytes": sum(item.bytes for item in fingerprint_tree(candidate)),
        "changed_files": changed_files,
        "before": asdict(before_assessment),
        "after": None if after_assessment is None else asdict(after_assessment),
        "finding_transition": (
            None if after_assessment is None else finding_transition(before_assessment, after_assessment)
        ),
        "converter": converter_report,
        "converter_defect": defect,
        "equivalence": asdict(equivalence),
        "projection": asdict(temporal),
        "idempotence": asdict(idempotence),
        "fact_parity": {"status": CheckStatus.UNRESOLVED, "detail": "registry-wide authority check pending"},
        "indexed_parity": {"status": CheckStatus.UNRESOLVED, "detail": "registry-wide authority check pending"},
        "cache": {"status": CheckStatus.UNRESOLVED, "detail": "registry-wide authority check pending"},
        "source_apply_readiness": source_readiness,
        "authority_publication_readiness": CheckStatus.UNRESOLVED,
    }


def _replace_candidate_modelo(registry_candidate: Path, modelo: Mapping[str, object]) -> None:
    if modelo.get("source_apply_readiness") != CheckStatus.PASSED:
        return
    source = Path(str(modelo["candidate_path"]))
    target = registry_candidate / _MODELOS / str(modelo["modelo"])
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(source, target)


def _authority_checks(
    source_registry: Path,
    candidate_registry: Path,
    *,
    source_root: Path,
    indexed_dir: Path,
) -> dict[str, object]:
    """Run source/candidate authority and real temporary indexed parity."""
    try:
        clear_registry_tree_cache()
        source_authority = compile_validated_authority(source_registry, source_root)
        source_cold = _typed_projection(source_authority.modelos)
        source_warm = _typed_projection(compile_validated_authority(source_registry, source_root).modelos)
        candidate_authority = compile_validated_authority(candidate_registry, source_root)
        candidate_cold = _typed_projection(candidate_authority.modelos)
        candidate_warm = _typed_projection(compile_validated_authority(candidate_registry, source_root).modelos)
    except Exception as exc:
        return {
            "equivalence": CheckStatus.UNRESOLVED,
            "facts": CheckStatus.UNRESOLVED,
            "indexed": CheckStatus.UNRESOLVED,
            "cache": CheckStatus.UNRESOLVED,
            "publication_readiness": CheckStatus.FAILED,
            "detail": f"validated authority prerequisite failed: {type(exc).__name__}: {exc}",
        }
    authority_difference = _first_difference(source_cold, candidate_cold)
    cache_difference = _first_difference(source_cold, source_warm) or _first_difference(candidate_cold, candidate_warm)
    facts_difference: Mapping[str, object] | None = _first_difference(
        _typed_projection(source_authority.catalogues.facts),
        _typed_projection(candidate_authority.catalogues.facts),
    )
    fact_queries = _fact_queries(source_authority)
    fact_checked = 0
    if facts_difference is None:
        for query in fact_queries:
            fact_checked += 1
            facts_difference = _first_difference(
                _fact_result(source_authority.resolve_governed_fact, query),
                _fact_result(candidate_authority.resolve_governed_fact, query),
                f"$.facts.{query.fact_id}",
            )
            if facts_difference is not None:
                break
    indexed_difference: Mapping[str, object] | None = None
    indexed_checked = 0
    indexed_temporal_checked = 0
    indexed_capability_checked = 0
    indexed_fact_checked = 0
    try:
        descriptor = publish_sqlite_authority_candidate(
            registry_root=candidate_registry,
            source_root=source_root,
            profile_schema_path=source_root / "registry" / "cadrumo" / "user_profile" / "schema.toml",
            destination=indexed_dir,
        )
        indexed = IndexedRegistryAuthority(indexed_dir / "authority.current.json")
        try:
            with indexed.operation() as operation:
                expected_ids = tuple(
                    sorted(
                        (str(modelo.id), str(revision_id))
                        for modelo in candidate_authority.modelos
                        for revision_id in modelo.revisions
                    )
                )
                actual_ids = tuple(sorted(operation.revision_ids()))
                indexed_difference = _first_difference(expected_ids, actual_ids, "$.revision_ids")
                if indexed_difference is None:
                    for modelo_id, revision_id in expected_ids:
                        expected = candidate_authority.modelo(modelo_id).revisions[revision_id]
                        actual = operation.revision_with_export_layouts(modelo_id, revision_id)
                        indexed_checked += 1
                        indexed_difference = _first_difference(
                            _typed_projection(expected), _typed_projection(actual), f"$.{modelo_id}.{revision_id}"
                        )
                        if indexed_difference is not None:
                            break
                support = candidate_authority.catalogues.supported_filing_years
                if indexed_difference is None and support is None:
                    indexed_difference = {"location": "$.support", "reason": "supported range missing"}
                if indexed_difference is None and support is not None:
                    sample_ceiling = support.hard_ceiling if support.hard_ceiling is not None else support.horizon + 1
                    source_by_id = {str(modelo.id): modelo for modelo in source_authority.modelos}
                    for modelo in candidate_authority.modelos:
                        modelo_id = str(modelo.id)
                        for coordinate in request_matrix(modelo, floor=support.floor, ceiling=sample_ceiling):
                            indexed_temporal_checked += 1
                            indexed_difference = _first_difference(
                                _selection_result(source_by_id[modelo_id], coordinate, support),
                                _indexed_selection_result(operation, modelo_id, coordinate),
                                f"$.temporal.{modelo_id}",
                            )
                            if indexed_difference is not None:
                                break
                            indexed_capability_checked += 1
                            source_snapshot = _snapshot_result(source_authority.snapshot, modelo_id, coordinate)
                            candidate_snapshot = _snapshot_result(candidate_authority.snapshot, modelo_id, coordinate)
                            indexed_snapshot = _snapshot_result(operation.snapshot, modelo_id, coordinate)
                            indexed_difference = _first_difference(
                                source_snapshot,
                                candidate_snapshot,
                                f"$.capability.source_candidate.{modelo_id}",
                            ) or _first_difference(
                                candidate_snapshot,
                                indexed_snapshot,
                                f"$.capability.candidate_indexed.{modelo_id}",
                            )
                            if indexed_difference is not None:
                                break
                        if indexed_difference is not None:
                            break
                if indexed_difference is None:
                    for query in fact_queries:
                        indexed_fact_checked += 1
                        indexed_difference = _first_difference(
                            _fact_result(candidate_authority.resolve_governed_fact, query),
                            _fact_result(operation.resolve_governed_fact, query),
                            f"$.indexed_facts.{query.fact_id}",
                        )
                        if indexed_difference is not None:
                            break
        finally:
            indexed.close()
        descriptor_payload: object = asdict(descriptor)
    except Exception as exc:
        return {
            "equivalence": CheckStatus.PASSED if authority_difference is None else CheckStatus.FAILED,
            "facts": CheckStatus.PASSED if facts_difference is None else CheckStatus.FAILED,
            "fact_queries_checked": fact_checked,
            "indexed": CheckStatus.UNRESOLVED,
            "cache": CheckStatus.PASSED if cache_difference is None else CheckStatus.FAILED,
            "publication_readiness": CheckStatus.FAILED,
            "detail": f"temporary indexed build failed: {type(exc).__name__}: {exc}",
        }
    passed = authority_difference is None and facts_difference is None and indexed_difference is None
    return {
        "equivalence": CheckStatus.PASSED if authority_difference is None else CheckStatus.FAILED,
        "facts": CheckStatus.PASSED if facts_difference is None else CheckStatus.FAILED,
        "fact_queries_checked": fact_checked,
        "indexed": CheckStatus.PASSED if indexed_difference is None else CheckStatus.FAILED,
        "indexed_revisions_checked": indexed_checked,
        "indexed_temporal_coordinates_checked": indexed_temporal_checked,
        "indexed_capability_coordinates_checked": indexed_capability_checked,
        "indexed_fact_queries_checked": indexed_fact_checked,
        "cache": CheckStatus.PASSED if cache_difference is None else CheckStatus.FAILED,
        "publication_readiness": CheckStatus.PASSED if passed else CheckStatus.FAILED,
        "authority_difference": authority_difference,
        "facts_difference": facts_difference,
        "indexed_difference": indexed_difference,
        "descriptor": descriptor_payload,
    }


def run_registry_verification(
    *,
    registry_root: Path,
    source_root: Path,
    work_dir: Path,
    converter: Callable[[Path, Path], Mapping[str, object]] = canonical_converter,
) -> Mapping[str, object]:
    """Exercise every discovered modelo once and persist detailed JSON artifacts."""
    registry_root = registry_root.resolve(strict=True)
    source_root = source_root.resolve(strict=True)
    work_dir = work_dir.resolve()
    if (
        registry_root == work_dir
        or registry_root in work_dir.parents
        or source_root == work_dir
        or source_root in work_dir.parents
    ):
        raise ValueError("work directory must be outside the live registry and source roots")
    if work_dir.exists():
        raise ValueError(f"work directory already exists: {work_dir}")
    work_dir.mkdir(parents=True)
    snapshot_registry = work_dir / "source-snapshot" / "registry" / "aeat"
    snapshot_source_root = work_dir / "source-snapshot" / "data"
    registry_candidate = work_dir / "registry-candidate" / "aeat"
    shutil.copytree(registry_root, snapshot_registry)
    shutil.copytree(snapshot_registry, registry_candidate)
    sources = discover_modelo_sources(snapshot_registry / _MODELOS)
    if len({source.modelo_id for source in sources}) != len(sources):
        raise RuntimeError("modelo discovery returned duplicate identities")
    tool_paths = tuple(REPO_ROOT / relative for relative in _TOOL_INPUTS)
    live_registry_before = fingerprint_tree(registry_root)
    tools_before = fingerprint_paths(tool_paths, relative_to=REPO_ROOT)
    source_dependencies = _source_dependency_paths(source_root)
    source_dependencies_before = fingerprint_paths(source_dependencies, relative_to=source_root)
    _copy_source_dependencies(source_dependencies, source_root=source_root, destination=snapshot_source_root)
    published_root = source_root / "registry" / "authority"
    published_before = fingerprint_tree(published_root)
    from dev.registry.compiler.loader import load_shared_catalogues

    support = load_shared_catalogues(snapshot_registry).supported_filing_years
    if support is None:
        raise RuntimeError("registry has no global supported filing range")
    ceiling = support.hard_ceiling if support.hard_ceiling is not None else support.horizon
    details_dir = work_dir / "modelos"
    details_dir.mkdir()
    results: list[dict[str, object]] = []
    for source in sources:
        candidate = work_dir / "candidates" / source.modelo_id / "registry" / "aeat" / _MODELOS / source.modelo_id
        result: dict[str, object]
        try:
            result = _verify_one(
                source.modelo_id,
                source.path,
                candidate,
                support=support,
                floor=support.floor,
                ceiling=ceiling,
                converter=converter,
            )
        except Exception as exc:
            result = {
                "modelo": source.modelo_id,
                "outcome": ModeloOutcome.UNASSESSED,
                "source_path": str(source.path),
                "candidate_path": str(candidate),
                "dependency": f"{type(exc).__name__}: {exc}",
                "source_apply_readiness": CheckStatus.FAILED,
                "authority_publication_readiness": CheckStatus.UNRESOLVED,
            }
        results.append(result)
        (details_dir / f"{source.modelo_id}.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8", newline="\n"
        )
        _replace_candidate_modelo(registry_candidate, result)
    authority = _authority_checks(
        snapshot_registry,
        registry_candidate,
        source_root=snapshot_source_root,
        indexed_dir=work_dir / "indexed-authority",
    )
    cache_invalidation = _cache_invalidation_probe(
        registry_candidate,
        work_dir / "cache-invalidation-probe",
    )
    authority["cache_invalidation"] = cache_invalidation
    if cache_invalidation["status"] is not CheckStatus.PASSED:
        authority["cache"] = CheckStatus.FAILED
        authority["publication_readiness"] = CheckStatus.FAILED
    for result in results:
        result["fact_parity"] = {"status": authority["facts"], "scope": "registry-wide governed catalogue"}
        result["indexed_parity"] = {"status": authority["indexed"], "detail": authority.get("detail")}
        result["cache"] = {"status": authority["cache"], "scope": "cold/warm compiled authority"}
        result["authority_publication_readiness"] = (
            authority["publication_readiness"]
            if result.get("source_apply_readiness") == CheckStatus.PASSED
            else CheckStatus.FAILED
        )
        (details_dir / f"{result['modelo']}.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8", newline="\n"
        )
    live_registry_after = fingerprint_tree(registry_root)
    tools_after = fingerprint_paths(tool_paths, relative_to=REPO_ROOT)
    source_dependencies_after = fingerprint_paths(source_dependencies, relative_to=source_root)
    published_after = fingerprint_tree(published_root)
    inputs_stable = (
        live_registry_before == live_registry_after
        and tools_before == tools_after
        and source_dependencies_before == source_dependencies_after
    )
    no_live_mutation = live_registry_before == live_registry_after and published_before == published_after
    if not inputs_stable:
        for result in results:
            result["input_stability"] = {
                "status": CheckStatus.FAILED,
                "detail": "live registry, shared source dependency, or verification tool changed during measurement",
            }
            result["source_apply_readiness"] = CheckStatus.FAILED
            result["authority_publication_readiness"] = CheckStatus.FAILED
            (details_dir / f"{result['modelo']}.json").write_text(
                json.dumps(result, ensure_ascii=False, indent=2, default=str) + "\n",
                encoding="utf-8",
                newline="\n",
            )
    outcome_counts = {status.value: sum(item["outcome"] == status for item in results) for status in ModeloOutcome}
    complete = (
        inputs_stable
        and len(results) == len(sources)
        and all(item.get("source_apply_readiness") == CheckStatus.PASSED for item in results)
        and authority["publication_readiness"] == CheckStatus.PASSED
    )
    summary = {
        "schema": "cadrumo-registry-collapse-readiness/v1",
        "complete": complete,
        "registry_rollout": "complete" if complete else "incomplete",
        "no_live_mutation": no_live_mutation,
        "inputs_stable": inputs_stable,
        "inventory": {"discovered": len(sources), "reported": len(results), "duplicates": 0},
        "global_supported_range": {
            "floor": support.floor,
            "horizon": support.horizon,
            "hard_ceiling": support.hard_ceiling,
        },
        "input_fingerprints": {
            "registry": fingerprint_digest(live_registry_before),
            "tools": fingerprint_digest(tools_before),
            "source_dependencies": fingerprint_digest(source_dependencies_before),
            "published_authority": fingerprint_digest(published_before),
            "snapshot": fingerprint_digest(fingerprint_tree(snapshot_registry)),
        },
        "outcomes": outcome_counts,
        "accounting": {
            "before": _assessment_accounting(results, "before"),
            "after": _assessment_accounting(results, "after"),
        },
        "source_apply_ready": sum(item.get("source_apply_readiness") == CheckStatus.PASSED for item in results),
        "authority_publication_ready": sum(
            item.get("authority_publication_readiness") == CheckStatus.PASSED for item in results
        ),
        "authority": authority,
        "modelos": [{"modelo": item["modelo"], "outcome": item["outcome"]} for item in results],
    }
    (work_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8", newline="\n"
    )
    (work_dir / "input-manifest.json").write_text(
        json.dumps(
            {
                "registry": [asdict(item) for item in live_registry_before],
                "tools": [asdict(item) for item in tools_before],
                "source_dependencies": [asdict(item) for item in source_dependencies_before],
                "published_authority": [asdict(item) for item in published_before],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return summary


def main(argv: Sequence[str] | None = None) -> int:
    """Run the non-applying verifier and fail while any rollout result is incomplete."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry-root", required=True, type=Path)
    parser.add_argument("--source-root", required=True, type=Path)
    parser.add_argument("--work-dir", required=True, type=Path)
    arguments = parser.parse_args(argv)
    try:
        summary = run_registry_verification(
            registry_root=arguments.registry_root,
            source_root=arguments.source_root,
            work_dir=arguments.work_dir,
        )
    except Exception as exc:
        sys.stderr.write(f"registry collapse verification refused: {type(exc).__name__}: {exc}\n")
        return 1
    sys.stdout.write(json.dumps(summary, ensure_ascii=False, indent=2, default=str) + "\n")
    return 0 if summary["complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
