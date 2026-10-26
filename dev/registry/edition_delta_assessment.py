"""Assessment of authored duplication and migration readiness."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Final

from cadrumo.domain.calculations.registry.errors import RegistryLoadError
from cadrumo.domain.calculations.registry.revision_order import ordered_revisions

from . import edition_delta_errors as _edition_delta_errors
from .compiler.loader import load_modelo_declarations, load_modelo_directory
from .edition_delta_assessment_revision import assess_revision
from .edition_delta_assessment_shape import authored_shape_findings
from .edition_delta_assessment_state import AssessmentRun
from .edition_round_trip import RoundTripFinding, RoundTripFindingKind

__all__ = (
    "AcceptanceCheckClass",
    "MigrationAssessment",
    "MigrationStatus",
    "PublicationExecutionStatus",
    "PublicationReadinessStatus",
    "SourceMigrationStatus",
    "assess_migration_state",
)


class AcceptanceCheckClass(StrEnum):
    """Owning acceptance boundary for a migration diagnostic."""

    SOURCE_RECONSTRUCTION = "source_reconstruction"
    PUBLICATION_READINESS = "publication_readiness"


class SourceMigrationStatus(StrEnum):
    """Machine states for source replacement alone."""

    ACCEPTED = "accepted"
    APPLIED = "applied"
    PARTIALLY_APPLIED = "partially_applied"
    PARTIAL = "partial"
    REFUSED = "refused"


class PublicationReadinessStatus(StrEnum):
    """Machine states for the complete publication contract."""

    FAILED = "failed"
    NOT_CHECKED = "not_checked"


class PublicationExecutionStatus(StrEnum):
    """Machine states for authority publication execution."""

    NOT_PERFORMED = "not_performed"


class MigrationStatus(StrEnum):
    """Independent verdicts carried by a source-migration report."""

    PASSED = "passed"
    FAILED = "failed"
    COMPLETE = "complete"
    INCOMPLETE = "incomplete"
    UNCHANGED = "unchanged"
    APPLIED = "applied"
    PARTIALLY_APPLIED = "partially_applied"
    STAGED = "staged"
    NOT_APPLIED = "not_applied"


@dataclass(frozen=True, slots=True)
class MigrationAssessment:
    """Read-only physical and semantic measurements for one authored modelo tree.

    A payload field is one value-bearing mapping entry, recursively. Empty
    mappings/arrays are one explicit value. Array elements are part of their
    owning field and are compared with order and type intact. ``id``, storage
    selectors, baseline/predecessor references, removals, and position/order
    declarations are structural overhead. Provenance and continuity fields are
    payload and are deliberately absent from that structural classification.
    """

    fingerprint: str
    input_fingerprints: tuple[Mapping[str, str], ...]
    inputs_stable: bool
    physical_bytes: int
    authored_payload_fields: int
    inherited_payload_fields: int
    genuine_overrides: int
    redundant_overrides: int
    additions: int
    removals: int
    structural_overhead: int
    unresolved_duplication: tuple[Mapping[str, object], ...]
    blocked_work: tuple[Mapping[str, object], ...]
    by_revision_family: tuple[Mapping[str, object], ...]

    @property
    def minimal(self) -> bool:
        """Whether no eligible repeated payload or unassessed work remains."""
        return self.inputs_stable and not self.unresolved_duplication and not self.blocked_work


def _file_fingerprints(modelo_dir: Path) -> tuple[Mapping[str, str], ...]:
    return tuple(
        {
            "path": path.relative_to(modelo_dir).as_posix(),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }
        for path in sorted(item for item in modelo_dir.rglob("*") if item.is_file())
    )


def _source_fingerprint(modelo_dir: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(item for item in modelo_dir.rglob("*") if item.is_file()):
        digest.update(path.relative_to(modelo_dir).as_posix().encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return f"sha256:{digest.hexdigest()}"


def assess_migration_state(modelo_dir: Path) -> MigrationAssessment:
    """Measure authored duplication independently of any converter deletion plan."""
    initial_fingerprints = _file_fingerprints(modelo_dir)
    initial_fingerprint = _source_fingerprint(modelo_dir)
    try:
        declarations = load_modelo_declarations(modelo_dir)
    except RegistryLoadError as exc:
        return _load_failure_assessment(modelo_dir, initial_fingerprints, initial_fingerprint, exc)
    raw_revisions = declarations.get("revisions", {})
    if not isinstance(raw_revisions, Mapping):
        raise _edition_delta_errors.MigrationRefusedError(f"{modelo_dir}: revisions are not a mapping")
    shape_findings = authored_shape_findings(raw_revisions)
    if shape_findings:
        return _shape_failure_assessment(modelo_dir, initial_fingerprints, initial_fingerprint, shape_findings)
    definition = load_modelo_directory(modelo_dir)
    run = AssessmentRun(modelo_dir, initial_fingerprint, initial_fingerprints, definition)
    previous: str | None = None
    for revision in ordered_revisions(definition):
        revision_id = str(revision.id)
        raw = raw_revisions.get(revision_id, {})
        if isinstance(raw, Mapping):
            assess_revision(run, revision, raw, previous)
        previous = revision_id
    return _final_assessment(run)


def _load_failure_assessment(
    modelo_dir: Path,
    initial_fingerprints: tuple[Mapping[str, str], ...],
    initial_fingerprint: str,
    error: RegistryLoadError,
) -> MigrationAssessment:
    field_match = re.search(r"fragment field '([^']+)'", str(error))
    revision_match = re.search(r"[\\/]revisions[\\/]([^\\/]+)[\\/]", str(error))
    final_fingerprints = _file_fingerprints(modelo_dir)
    inputs_stable = initial_fingerprints == final_fingerprints
    blocked: list[Mapping[str, object]] = [
        {
            "revision": revision_match.group(1) if revision_match else "*",
            "family": field_match.group(1) if field_match else "*",
            "reason": "authored_shape_unsupported",
            "detail": str(error),
        }
    ]
    if not inputs_stable:
        blocked.append({"revision": "*", "family": "*", "reason": "inputs_changed_during_assessment"})
    return MigrationAssessment(
        fingerprint=initial_fingerprint,
        input_fingerprints=initial_fingerprints,
        inputs_stable=inputs_stable,
        physical_bytes=_physical_bytes(modelo_dir),
        authored_payload_fields=0,
        inherited_payload_fields=0,
        genuine_overrides=0,
        redundant_overrides=0,
        additions=0,
        removals=0,
        structural_overhead=0,
        unresolved_duplication=(),
        blocked_work=tuple(blocked),
        by_revision_family=(),
    )


def _shape_failure_assessment(
    modelo_dir: Path,
    initial_fingerprints: tuple[Mapping[str, str], ...],
    initial_fingerprint: str,
    findings: list[Mapping[str, object]],
) -> MigrationAssessment:
    final_fingerprints = _file_fingerprints(modelo_dir)
    inputs_stable = initial_fingerprints == final_fingerprints
    if not inputs_stable:
        findings.append({"revision": "*", "family": "*", "reason": "inputs_changed_during_assessment"})
    return MigrationAssessment(
        fingerprint=initial_fingerprint,
        input_fingerprints=initial_fingerprints,
        inputs_stable=inputs_stable,
        physical_bytes=_physical_bytes(modelo_dir),
        authored_payload_fields=0,
        inherited_payload_fields=0,
        genuine_overrides=0,
        redundant_overrides=0,
        additions=0,
        removals=0,
        structural_overhead=0,
        unresolved_duplication=(),
        blocked_work=tuple(findings),
        by_revision_family=(),
    )


def _final_assessment(run: AssessmentRun) -> MigrationAssessment:
    final_fingerprints = _file_fingerprints(run.modelo_dir)
    inputs_stable = run.input_fingerprints == final_fingerprints
    if not inputs_stable:
        run.blocked.append({"revision": "*", "family": "*", "reason": "inputs_changed_during_assessment"})
    blocked = {tuple(sorted(item.items())): item for item in run.blocked}
    return MigrationAssessment(
        fingerprint=run.fingerprint,
        input_fingerprints=run.input_fingerprints,
        inputs_stable=inputs_stable,
        physical_bytes=_physical_bytes(run.modelo_dir),
        authored_payload_fields=run.totals["authored_payload_fields"],
        inherited_payload_fields=run.totals["inherited_payload_fields"],
        genuine_overrides=run.totals["genuine_overrides"],
        redundant_overrides=run.totals["redundant_overrides"],
        additions=run.totals["additions"],
        removals=run.totals["removals"],
        structural_overhead=run.totals["structural_overhead"],
        unresolved_duplication=tuple(run.unresolved),
        blocked_work=tuple(dict(item) for item in blocked.values()),
        by_revision_family=tuple(run.rows),
    )


def _physical_bytes(modelo_dir: Path) -> int:
    return sum(path.stat().st_size for path in modelo_dir.rglob("*") if path.is_file())


_PUBLICATION_READINESS_FINDINGS: Final = frozenset(
    {
        RoundTripFindingKind.EXPORT_BYTES,
        RoundTripFindingKind.EXPORT_REFUSED,
        RoundTripFindingKind.EXPORT_UNCHECKED,
    }
)


def _finding_class(finding: RoundTripFinding) -> AcceptanceCheckClass:
    """Classify by the diagnostic's typed identity, never its prose."""
    if finding.kind in _PUBLICATION_READINESS_FINDINGS:
        return AcceptanceCheckClass.PUBLICATION_READINESS
    return AcceptanceCheckClass.SOURCE_RECONSTRUCTION


def _is_source_finding(finding: RoundTripFinding) -> bool:
    return _finding_class(finding) is AcceptanceCheckClass.SOURCE_RECONSTRUCTION
