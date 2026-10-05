"""Canonical registry candidate conversion and dependency closure."""

from __future__ import annotations

import shutil
from collections.abc import Mapping
from dataclasses import asdict
from pathlib import Path
from uuid import uuid4

from dev.registry.edition_delta_migration import MigrationOutcome, migrate_modelo
from dev.registry.edition_round_trip import copy_registry_tree

from .registry_collapse_models import _MODELOS


def canonical_converter(source: Path, candidate: Path) -> Mapping[str, object]:
    """Invoke Lane 1's complete generalized migration orchestration without applying."""
    registry_root = source.parent.parent.resolve(strict=True)
    modelo_id = source.name
    candidate_registry = candidate.parent.parent.resolve(strict=True)
    _copy_registry_dependencies(registry_root, candidate_registry)
    runs_root = _converter_runs_root(candidate)
    candidate_modelos = candidate_registry / _MODELOS
    _copy_candidate_dependency_closure(registry_root, candidate_modelos, runs_root, modelo_id)
    work_dir = runs_root / f"{modelo_id}-{uuid4().hex}"
    outcome = migrate_modelo(
        registry_root=registry_root,
        modelo_id=modelo_id,
        work_dir=work_dir,
        export_scenarios={},
        apply=False,
    )
    _install_staged_candidate(outcome, candidate, modelo_id)
    return _conversion_report(outcome, work_dir)


def _copy_registry_dependencies(registry_root: Path, candidate_registry: Path) -> None:
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


def _converter_runs_root(candidate: Path) -> Path:
    candidates_root = next((parent for parent in candidate.parents if parent.name == "candidates"), None)
    if candidates_root is None:
        raise RuntimeError(f"candidate path has no candidates scratch ancestor: {candidate}")
    runs_root = candidates_root.parent / "converter-runs"
    runs_root.mkdir(parents=True, exist_ok=True)
    return runs_root


def _copy_candidate_dependency_closure(
    registry_root: Path,
    candidate_modelos: Path,
    runs_root: Path,
    modelo_id: str,
) -> None:
    closure_root = copy_registry_tree(
        registry_root,
        runs_root / f"{modelo_id}-{uuid4().hex}-dependencies" / "registry" / "aeat",
        modelo_id=modelo_id,
    )
    for dependency in (closure_root / _MODELOS).iterdir():
        target = candidate_modelos / dependency.name
        if dependency.name != modelo_id and not target.exists():
            shutil.copytree(dependency, target)


def _install_staged_candidate(
    outcome: MigrationOutcome,
    candidate: Path,
    modelo_id: str,
) -> None:
    if outcome.staged_registry is not None:
        staged = outcome.staged_registry / _MODELOS / modelo_id
        resolved_candidate = candidate.resolve(strict=True)
        resolved_parent = candidate.parent.resolve(strict=True)
        if resolved_candidate.parent != resolved_parent:
            raise RuntimeError(f"candidate path escaped its scratch parent: {resolved_candidate}")
        shutil.rmtree(resolved_candidate)
        shutil.copytree(staged, resolved_candidate)


def _conversion_report(outcome: MigrationOutcome, work_dir: Path) -> Mapping[str, object]:
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
