"""Registry-wide collapse verification run coordination and artifact persistence."""

from __future__ import annotations

import json
import shutil
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path

from cadrumo.domain.calculations.registry.schema import SupportedFilingYearsCatalogue
from dev._paths import REPO_ROOT
from dev.registry.compiler.loader import load_shared_catalogues
from dev.registry.compiler.loader_cache import ModeloSource, discover_modelo_sources

from .registry_collapse_assessment import _assessment_accounting
from .registry_collapse_authority_checks import _authority_checks
from .registry_collapse_cache import _cache_invalidation_probe
from .registry_collapse_candidate import _replace_candidate_modelo, _verify_one
from .registry_collapse_converter import canonical_converter
from .registry_collapse_fingerprints import (
    fingerprint_digest,
    fingerprint_optional_tree,
    fingerprint_paths,
    fingerprint_tree,
    published_authority_root,
)
from .registry_collapse_inputs import _copy_source_dependencies, _source_dependency_paths, _tool_input_paths
from .registry_collapse_models import _MODELOS, CheckStatus, FingerprintEntry, ModeloOutcome


@dataclass(frozen=True, slots=True)
class _RunContext:
    registry_root: Path
    source_root: Path
    work_dir: Path
    snapshot_registry: Path
    snapshot_source_root: Path
    registry_candidate: Path
    sources: tuple[ModeloSource, ...]
    discovered: int
    requested_modelos: tuple[str, ...]
    live_registry_before: tuple[FingerprintEntry, ...]
    tools_before: tuple[FingerprintEntry, ...]
    source_dependencies: tuple[Path, ...]
    source_dependencies_before: tuple[FingerprintEntry, ...]
    published_root: Path
    published_before: tuple[FingerprintEntry, ...]
    support: SupportedFilingYearsCatalogue
    ceiling: int
    details_dir: Path


def run_registry_verification(
    *,
    registry_root: Path,
    source_root: Path,
    work_dir: Path,
    converter: Callable[[Path, Path], Mapping[str, object]] = canonical_converter,
    authority_root: Path | None = None,
    modelos: Sequence[str] = (),
) -> Mapping[str, object]:
    """Exercise every discovered modelo once and persist detailed JSON artifacts.

    ``authority_root`` is the published authority whose immutability the run
    proves; it defaults to the working tree's own publication. ``modelos``
    narrows the per-modelo pass to the named identities, so a memory-limited
    host can verify one modelo per process against the same registry-wide
    authority checks.
    """
    context = _prepare_run_context(registry_root, source_root, work_dir, authority_root, modelos)
    results = _verify_modelos(context, converter)
    authority = _run_authority_checks(context)
    _apply_authority_results(results, authority, context.details_dir)
    live_registry_after, tools_after, source_dependencies_after, published_after = _fingerprint_run_inputs(context)
    inputs_stable = _inputs_stable(context, live_registry_after, tools_after, source_dependencies_after)
    no_live_mutation = _no_live_mutation(context, live_registry_after, published_after)
    _record_input_instability(results, context.details_dir, inputs_stable)
    summary = _run_summary(context, results, authority, inputs_stable, no_live_mutation)
    _write_run_artifacts(context, summary)
    return summary


def _validated_run_paths(registry_root: Path, source_root: Path, work_dir: Path) -> tuple[Path, Path, Path]:
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
    return registry_root, source_root, work_dir


def _snapshot_paths(work_dir: Path) -> tuple[Path, Path, Path]:
    snapshot_registry = work_dir / "source-snapshot" / "registry" / "aeat"
    snapshot_source_root = work_dir / "source-snapshot" / "data"
    registry_candidate = work_dir / "registry-candidate" / "aeat"
    return snapshot_registry, snapshot_source_root, registry_candidate


def _copy_registry_snapshots(
    registry_root: Path,
    snapshot_registry: Path,
    registry_candidate: Path,
) -> None:
    shutil.copytree(registry_root, snapshot_registry)
    shutil.copytree(snapshot_registry, registry_candidate)


def _selected_sources(
    snapshot_registry: Path,
    modelos: Sequence[str],
) -> tuple[tuple[ModeloSource, ...], int]:
    sources = discover_modelo_sources(snapshot_registry / _MODELOS)
    if len({source.modelo_id for source in sources}) != len(sources):
        raise RuntimeError("modelo discovery returned duplicate identities")
    discovered = len(sources)
    if modelos:
        unknown = sorted(set(modelos) - {source.modelo_id for source in sources})
        if unknown:
            raise ValueError(f"unknown modelo identities requested: {', '.join(unknown)}")
        sources = tuple(source for source in sources if source.modelo_id in set(modelos))
    return sources, discovered


def _prepare_run_context(
    registry_root: Path,
    source_root: Path,
    work_dir: Path,
    authority_root: Path | None,
    modelos: Sequence[str],
) -> _RunContext:
    registry_root, source_root, work_dir = _validated_run_paths(registry_root, source_root, work_dir)
    snapshot_registry, snapshot_source_root, registry_candidate = _snapshot_paths(work_dir)
    live_registry_before = fingerprint_tree(registry_root)
    tools_before = _tool_fingerprints(REPO_ROOT)
    source_dependencies = _source_dependency_paths(source_root)
    source_dependencies_before = fingerprint_paths(source_dependencies, relative_to=source_root)
    published_root = published_authority_root(authority_root)
    published_before = fingerprint_optional_tree(published_root)
    _copy_registry_snapshots(registry_root, snapshot_registry, registry_candidate)
    _copy_source_dependencies(source_dependencies, source_root=source_root, destination=snapshot_source_root)
    _require_snapshots_match_inputs(
        snapshot_registry,
        registry_candidate,
        snapshot_source_root,
        live_registry_before,
        source_dependencies_before,
    )
    sources, discovered = _selected_sources(snapshot_registry, modelos)
    support, ceiling = _run_support(snapshot_registry)
    details_dir = work_dir / "modelos"
    details_dir.mkdir()
    return _RunContext(
        registry_root=registry_root,
        source_root=source_root,
        work_dir=work_dir,
        snapshot_registry=snapshot_registry,
        snapshot_source_root=snapshot_source_root,
        registry_candidate=registry_candidate,
        sources=sources,
        discovered=discovered,
        requested_modelos=tuple(modelos),
        live_registry_before=live_registry_before,
        tools_before=tools_before,
        source_dependencies=source_dependencies,
        source_dependencies_before=source_dependencies_before,
        published_root=published_root,
        published_before=published_before,
        support=support,
        ceiling=ceiling,
        details_dir=details_dir,
    )


def _require_snapshots_match_inputs(
    snapshot_registry: Path,
    registry_candidate: Path,
    snapshot_source_root: Path,
    registry_before: tuple[FingerprintEntry, ...],
    dependencies_before: tuple[FingerprintEntry, ...],
) -> None:
    """Refuse a frozen input that differs from the pre-copy live image."""
    if fingerprint_tree(snapshot_registry) != registry_before:
        raise RuntimeError("registry source snapshot differs from the captured live input")
    if fingerprint_tree(registry_candidate) != registry_before:
        raise RuntimeError("registry candidate snapshot differs from the captured live input")
    if fingerprint_optional_tree(snapshot_source_root) != dependencies_before:
        raise RuntimeError("source dependency snapshot differs from the captured live input")


def _run_support(snapshot_registry: Path) -> tuple[SupportedFilingYearsCatalogue, int]:
    support = load_shared_catalogues(snapshot_registry).supported_filing_years
    if support is None:
        raise RuntimeError("registry has no global supported filing range")
    ceiling = support.hard_ceiling if support.hard_ceiling is not None else support.horizon
    return support, ceiling


def _verify_modelos(
    context: _RunContext,
    converter: Callable[[Path, Path], Mapping[str, object]],
) -> list[dict[str, object]]:
    results = []
    for source in context.sources:
        candidate = _candidate_path(context.work_dir, source.modelo_id)
        result = _verify_one_safely(source, candidate, context.support, context.ceiling, converter)
        results.append(result)
        _write_modelo_result(context.details_dir, source.modelo_id, result)
        _replace_candidate_modelo(context.registry_candidate, result)
    return results


def _candidate_path(work_dir: Path, modelo_id: str) -> Path:
    return work_dir / "candidates" / modelo_id / "registry" / "aeat" / _MODELOS / modelo_id


def _verify_one_safely(
    source: ModeloSource,
    candidate: Path,
    support: SupportedFilingYearsCatalogue,
    ceiling: int,
    converter: Callable[[Path, Path], Mapping[str, object]],
) -> dict[str, object]:
    try:
        return _verify_one(
            source.modelo_id,
            source.path,
            candidate,
            support=support,
            floor=support.floor,
            ceiling=ceiling,
            converter=converter,
        )
    except Exception as exc:
        return {
            "modelo": source.modelo_id,
            "outcome": ModeloOutcome.UNASSESSED,
            "source_path": str(source.path),
            "candidate_path": str(candidate),
            "dependency": f"{type(exc).__name__}: {exc}",
            "source_apply_readiness": CheckStatus.FAILED,
            "authority_publication_readiness": CheckStatus.UNRESOLVED,
        }


def _write_modelo_result(details_dir: Path, modelo_id: str, result: Mapping[str, object]) -> None:
    (details_dir / f"{modelo_id}.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2, default=str) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _run_authority_checks(context: _RunContext) -> dict[str, object]:
    authority = _authority_checks(
        context.snapshot_registry,
        context.registry_candidate,
        source_root=context.snapshot_source_root,
        indexed_dir=context.work_dir / "indexed-authority",
    )
    cache_invalidation = _cache_invalidation_probe(
        context.registry_candidate,
        context.work_dir / "cache-invalidation-probe",
    )
    authority["cache_invalidation"] = cache_invalidation
    if cache_invalidation["status"] is not CheckStatus.PASSED:
        authority["cache"] = CheckStatus.FAILED
        authority["publication_readiness"] = CheckStatus.FAILED
    return authority


def _apply_authority_results(
    results: Sequence[dict[str, object]],
    authority: Mapping[str, object],
    details_dir: Path,
) -> None:
    for result in results:
        result["fact_parity"] = {"status": authority["facts"], "scope": "registry-wide governed catalogue"}
        result["indexed_parity"] = {"status": authority["indexed"], "detail": authority.get("detail")}
        result["cache"] = {"status": authority["cache"], "scope": "cold/warm compiled authority"}
        result["authority_publication_readiness"] = (
            authority["publication_readiness"]
            if result.get("source_apply_readiness") == CheckStatus.PASSED
            else CheckStatus.FAILED
        )
        _write_modelo_result(details_dir, str(result["modelo"]), result)


def _fingerprint_run_inputs(
    context: _RunContext,
) -> tuple[
    tuple[FingerprintEntry, ...],
    tuple[FingerprintEntry, ...],
    tuple[FingerprintEntry, ...],
    tuple[FingerprintEntry, ...],
]:
    return (
        fingerprint_tree(context.registry_root),
        _tool_fingerprints(REPO_ROOT),
        fingerprint_paths(_source_dependency_paths(context.source_root), relative_to=context.source_root),
        fingerprint_optional_tree(context.published_root),
    )


def _tool_fingerprints(repo_root: Path) -> tuple[FingerprintEntry, ...]:
    """Re-discover tool paths for each boundary before hashing their bytes."""
    return fingerprint_paths(_tool_input_paths(repo_root), relative_to=repo_root)


def _inputs_stable(
    context: _RunContext,
    registry_after: tuple[FingerprintEntry, ...],
    tools_after: tuple[FingerprintEntry, ...],
    dependencies_after: tuple[FingerprintEntry, ...],
) -> bool:
    return (
        context.live_registry_before == registry_after
        and context.tools_before == tools_after
        and context.source_dependencies_before == dependencies_after
    )


def _no_live_mutation(
    context: _RunContext,
    registry_after: tuple[FingerprintEntry, ...],
    published_after: tuple[FingerprintEntry, ...],
) -> bool:
    return context.live_registry_before == registry_after and context.published_before == published_after


def _record_input_instability(
    results: Sequence[dict[str, object]],
    details_dir: Path,
    inputs_stable: bool,
) -> None:
    if inputs_stable:
        return
    for result in results:
        result["input_stability"] = {
            "status": CheckStatus.FAILED,
            "detail": "live registry, shared source dependency, or verification tool changed during measurement",
        }
        result["source_apply_readiness"] = CheckStatus.FAILED
        result["authority_publication_readiness"] = CheckStatus.FAILED
        _write_modelo_result(details_dir, str(result["modelo"]), result)


def _run_summary(
    context: _RunContext,
    results: Sequence[Mapping[str, object]],
    authority: Mapping[str, object],
    inputs_stable: bool,
    no_live_mutation: bool,
) -> dict[str, object]:
    outcome_counts = {status.value: sum(item["outcome"] == status for item in results) for status in ModeloOutcome}
    complete = _run_is_complete(context.sources, results, authority, inputs_stable, no_live_mutation)
    return {
        "schema": "cadrumo-registry-collapse-readiness/v1",
        "complete": complete,
        "registry_rollout": "complete" if complete and not context.requested_modelos else "incomplete",
        "no_live_mutation": no_live_mutation,
        "inputs_stable": inputs_stable,
        "inventory": {
            "discovered": context.discovered,
            "requested": sorted(source.modelo_id for source in context.sources) if context.requested_modelos else "all",
            "reported": len(results),
            "duplicates": 0,
        },
        "global_supported_range": {
            "floor": context.support.floor,
            "horizon": context.support.horizon,
            "hard_ceiling": context.support.hard_ceiling,
        },
        "input_fingerprints": {
            "registry": fingerprint_digest(context.live_registry_before),
            "tools": fingerprint_digest(context.tools_before),
            "source_dependencies": fingerprint_digest(context.source_dependencies_before),
            "published_authority": fingerprint_digest(context.published_before),
            "snapshot": fingerprint_digest(fingerprint_tree(context.snapshot_registry)),
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


def _run_is_complete(
    sources: Sequence[ModeloSource],
    results: Sequence[Mapping[str, object]],
    authority: Mapping[str, object],
    inputs_stable: bool,
    no_live_mutation: bool,
) -> bool:
    return (
        inputs_stable
        and no_live_mutation
        and len(results) == len(sources)
        and all(item.get("source_apply_readiness") == CheckStatus.PASSED for item in results)
        and authority["publication_readiness"] == CheckStatus.PASSED
    )


def _write_run_artifacts(context: _RunContext, summary: Mapping[str, object]) -> None:
    (context.work_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, default=str) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    (context.work_dir / "input-manifest.json").write_text(
        json.dumps(
            {
                "registry": [asdict(item) for item in context.live_registry_before],
                "tools": [asdict(item) for item in context.tools_before],
                "source_dependencies": [asdict(item) for item in context.source_dependencies_before],
                "published_authority": [asdict(item) for item in context.published_before],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
