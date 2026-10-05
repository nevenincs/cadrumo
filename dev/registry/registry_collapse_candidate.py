"""Isolated per-modelo migration verification."""

from __future__ import annotations

import shutil
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict
from pathlib import Path

from cadrumo.domain.calculations.registry.schema import (
    ModeloDefinition,
    SupportedFilingYearsCatalogue,
)
from dev.registry.compiler.loader import load_modelo_directory
from dev.registry.edition_delta_assessment import MigrationAssessment, assess_migration_state

from .registry_collapse_assessment import assessment_coverage_gaps, assessor_scope_gaps, finding_transition
from .registry_collapse_assessment_normalization import normalized_assessment
from .registry_collapse_authority_queries import _revision_inventory
from .registry_collapse_comparison import compare_modelos
from .registry_collapse_converter import canonical_converter
from .registry_collapse_fingerprints import _file_change_count, fingerprint_digest, fingerprint_tree
from .registry_collapse_models import _MODELOS, CheckStatus, ComparisonResult, FingerprintEntry, ModeloOutcome
from .registry_collapse_requests import compare_temporal
from .registry_collapse_roots import _root_gaps, root_eligibility, root_overlap_diagnostics


def _copy_modelo(source: Path, destination: Path) -> None:
    if destination.exists():
        raise RuntimeError(f"candidate path already exists: {destination}")
    shutil.copytree(source, destination)


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
        before_assessment, before, source_scope_gaps = _assessed_modelo(source, stage="source")
    except Exception as exc:
        return _unassessed_source_result(
            modelo_id, source, candidate, before_files, roots, root_overlap, static_scope_gaps, exc
        )
    _copy_modelo(source, candidate)
    converter_report, defect = _run_converter(converter, source, candidate)
    after_files = fingerprint_tree(candidate)
    changed_files = _file_change_count(before_files, after_files)
    after_assessment, candidate_scope_gaps, roots_after, equivalence, temporal = _candidate_assessment_state(
        candidate,
        before,
        support=support,
        floor=floor,
        ceiling=ceiling,
    )
    idempotence = _idempotence_result(converter, defect, after_assessment, candidate, after_files)
    scope_gaps = (*static_scope_gaps, *source_scope_gaps, *candidate_scope_gaps)
    complete = _candidate_is_complete(
        after_assessment,
        scope_gaps,
        roots_after,
        equivalence,
        temporal,
        idempotence,
        defect,
    )
    outcome, defect = _candidate_outcome(before_assessment, after_assessment, changed_files, complete, defect)
    source_readiness = CheckStatus.PASSED if complete else CheckStatus.FAILED
    return _verified_modelo_result(
        modelo_id,
        source,
        candidate,
        before_files,
        after_assessment,
        before_assessment,
        before,
        roots,
        root_overlap,
        roots_after,
        scope_gaps,
        changed_files,
        converter_report,
        defect,
        equivalence,
        temporal,
        idempotence,
        source_readiness,
        outcome,
    )


def _assessed_modelo(
    modelo_dir: Path,
    *,
    stage: str,
) -> tuple[MigrationAssessment, ModeloDefinition, tuple[Mapping[str, object], ...]]:
    assessment = normalized_assessment(modelo_dir, assess_migration_state(modelo_dir))
    modelo = load_modelo_directory(modelo_dir)
    gaps = assessment_coverage_gaps(assessment, modelo, stage=stage)
    return assessment, modelo, gaps


def _unassessed_source_result(
    modelo_id: str,
    source: Path,
    candidate: Path,
    before_files: tuple[FingerprintEntry, ...],
    roots: tuple[Mapping[str, object], ...],
    root_overlap: tuple[Mapping[str, object], ...],
    static_scope_gaps: tuple[Mapping[str, object], ...],
    error: Exception,
) -> dict[str, object]:
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
        "assessment_dependency": f"{type(error).__name__}: {error}",
        "source_apply_readiness": CheckStatus.FAILED,
        "authority_publication_readiness": CheckStatus.UNRESOLVED,
    }


def _run_converter(
    converter: Callable[[Path, Path], Mapping[str, object]],
    source: Path,
    candidate: Path,
) -> tuple[Mapping[str, object] | None, str | None]:
    try:
        return converter(source, candidate), None
    except Exception as exc:
        return None, f"{type(exc).__name__}: {exc}"


def _candidate_assessment_state(
    candidate: Path,
    before: ModeloDefinition,
    *,
    support: SupportedFilingYearsCatalogue,
    floor: int,
    ceiling: int,
) -> tuple[
    MigrationAssessment | None,
    tuple[Mapping[str, object], ...],
    tuple[Mapping[str, object], ...],
    ComparisonResult,
    ComparisonResult,
]:
    try:
        after_assessment, after, candidate_scope_gaps = _assessed_modelo(candidate, stage="candidate")
        roots_after = root_eligibility(candidate)
        equivalence = compare_modelos(before, after)
        temporal = compare_temporal(before, after, support=support, floor=floor, ceiling=ceiling)
    except Exception as exc:
        candidate_scope_gaps = ()
        roots_after = root_eligibility(candidate)
        equivalence = ComparisonResult(CheckStatus.FAILED, 0, detail=f"{type(exc).__name__}: {exc}")
        temporal = ComparisonResult(CheckStatus.UNRESOLVED, 0, detail="candidate did not hydrate")
        return None, candidate_scope_gaps, roots_after, equivalence, temporal
    return after_assessment, candidate_scope_gaps, roots_after, equivalence, temporal


def _idempotence_result(
    converter: Callable[[Path, Path], Mapping[str, object]],
    defect: str | None,
    after_assessment: MigrationAssessment | None,
    candidate: Path,
    after_files: tuple[FingerprintEntry, ...],
) -> ComparisonResult:
    idempotence = ComparisonResult(CheckStatus.UNRESOLVED, 0)
    if defect is not None or after_assessment is None:
        return idempotence
    first_digest = fingerprint_digest(after_files)
    try:
        converter(candidate, candidate)
        second_digest = fingerprint_digest(fingerprint_tree(candidate))
    except Exception as exc:
        return ComparisonResult(CheckStatus.FAILED, 1, detail=f"{type(exc).__name__}: {exc}")
    if first_digest == second_digest:
        return ComparisonResult(CheckStatus.PASSED, 1)
    return ComparisonResult(
        CheckStatus.FAILED,
        1,
        ({"location": "$files", "before": first_digest, "after": second_digest},),
    )


def _candidate_is_complete(
    after_assessment: MigrationAssessment | None,
    scope_gaps: Sequence[Mapping[str, object]],
    roots_after: Sequence[Mapping[str, object]],
    equivalence: ComparisonResult,
    temporal: ComparisonResult,
    idempotence: ComparisonResult,
    defect: str | None,
) -> bool:
    return bool(
        defect is None
        and after_assessment is not None
        and after_assessment.minimal
        and not scope_gaps
        and not _root_gaps(roots_after)
        and equivalence.status is CheckStatus.PASSED
        and temporal.status is CheckStatus.PASSED
        and idempotence.status is CheckStatus.PASSED
    )


def _candidate_outcome(
    before_assessment: MigrationAssessment,
    after_assessment: MigrationAssessment | None,
    changed_files: int,
    complete: bool,
    defect: str | None,
) -> tuple[ModeloOutcome, str | None]:
    if complete and before_assessment.minimal and changed_files == 0:
        return ModeloOutcome.ALREADY_MINIMAL, defect
    if complete:
        return ModeloOutcome.CONVERTED, defect
    if defect is not None:
        return ModeloOutcome.REFUSED, defect
    if after_assessment is None:
        return ModeloOutcome.UNASSESSED, defect
    if not before_assessment.minimal and changed_files == 0:
        defect = "converter_claimed_completion_without_changing_nonminimal_input"
    return ModeloOutcome.PARTIAL, defect


def _verified_modelo_result(
    modelo_id: str,
    source: Path,
    candidate: Path,
    before_files: tuple[FingerprintEntry, ...],
    after_assessment: MigrationAssessment | None,
    before_assessment: MigrationAssessment,
    before: ModeloDefinition,
    roots: tuple[Mapping[str, object], ...],
    root_overlap: tuple[Mapping[str, object], ...],
    roots_after: tuple[Mapping[str, object], ...],
    scope_gaps: Sequence[Mapping[str, object]],
    changed_files: int,
    converter_report: Mapping[str, object] | None,
    defect: str | None,
    equivalence: ComparisonResult,
    temporal: ComparisonResult,
    idempotence: ComparisonResult,
    source_readiness: CheckStatus,
    outcome: ModeloOutcome,
) -> dict[str, object]:
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
