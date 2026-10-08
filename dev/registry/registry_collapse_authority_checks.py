"""Registry-wide authority, governed-fact, and indexed parity checks."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path

from cadrumo.domain.calculations.registry.authority import (
    IndexedRegistryAuthority,
    PinnedAuthorityOperation,
    ValidatedRegistryAuthority,
)
from cadrumo.domain.calculations.registry.authority_store import AUTHORITY_DESCRIPTOR_FILENAME
from cadrumo.domain.calculations.registry.facts.resolution import GovernedFactQuery
from cadrumo.domain.calculations.registry.schema import ModeloDefinition, SupportedFilingYearsCatalogue
from dev.registry.compiler.authority import compile_validated_authority
from dev.registry.compiler.loader import clear_registry_tree_cache
from dev.registry.pipeline.authority_publication import publish_sqlite_authority_candidate

from .registry_collapse_authority_queries import (
    _fact_queries,
    _fact_result,
    _indexed_complete_revision,
    _indexed_selection_result,
    _snapshot_result,
)
from .registry_collapse_comparison import _first_difference, _typed_projection
from .registry_collapse_models import CheckStatus, RequestCoordinate
from .registry_collapse_requests import _selection_result, request_matrix


@dataclass(frozen=True, slots=True)
class _AuthorityPair:
    source: ValidatedRegistryAuthority
    candidate: ValidatedRegistryAuthority
    source_cold: object
    source_warm: object
    candidate_cold: object
    candidate_warm: object


@dataclass(frozen=True, slots=True)
class _FactParity:
    difference: Mapping[str, object] | None
    checked: int
    queries: tuple[GovernedFactQuery, ...]


@dataclass(frozen=True, slots=True)
class _IndexedParity:
    difference: Mapping[str, object] | None
    revision_count: int = 0
    temporal_count: int = 0
    capability_count: int = 0
    fact_count: int = 0
    descriptor: object | None = None
    detail: str | None = None


def _authority_checks(
    source_registry: Path,
    candidate_registry: Path,
    *,
    source_root: Path,
    indexed_dir: Path,
) -> dict[str, object]:
    """Run source/candidate authority and real temporary indexed parity."""
    try:
        authorities = _compile_authority_pair(source_registry, candidate_registry, source_root)
    except Exception as exc:
        return _authority_prerequisite_failure(exc)
    authority_difference = _first_difference(authorities.source_cold, authorities.candidate_cold)
    cache_difference = _authority_cache_difference(authorities)
    facts = _compare_fact_authorities(authorities.source, authorities.candidate)
    indexed = _indexed_authority_parity(
        candidate_registry,
        source_root,
        indexed_dir,
        authorities.source,
        authorities.candidate,
        facts.queries,
    )
    if indexed.detail is not None:
        return _indexed_prerequisite_result(authority_difference, facts, cache_difference, indexed)
    return _authority_parity_result(authority_difference, facts, cache_difference, indexed)


def _indexed_prerequisite_result(
    authority_difference: Mapping[str, object] | None,
    facts: _FactParity,
    cache_difference: Mapping[str, object] | None,
    indexed: _IndexedParity,
) -> dict[str, object]:
    return {
        "equivalence": CheckStatus.PASSED if authority_difference is None else CheckStatus.FAILED,
        "facts": CheckStatus.PASSED if facts.difference is None else CheckStatus.FAILED,
        "fact_queries_checked": facts.checked,
        "indexed": CheckStatus.UNRESOLVED,
        "cache": CheckStatus.PASSED if cache_difference is None else CheckStatus.FAILED,
        "publication_readiness": CheckStatus.FAILED,
        "detail": indexed.detail,
    }


def _authority_parity_result(
    authority_difference: Mapping[str, object] | None,
    facts: _FactParity,
    cache_difference: Mapping[str, object] | None,
    indexed: _IndexedParity,
) -> dict[str, object]:
    passed = authority_difference is None and facts.difference is None and indexed.difference is None
    return {
        "equivalence": CheckStatus.PASSED if authority_difference is None else CheckStatus.FAILED,
        "facts": CheckStatus.PASSED if facts.difference is None else CheckStatus.FAILED,
        "fact_queries_checked": facts.checked,
        "indexed": CheckStatus.PASSED if indexed.difference is None else CheckStatus.FAILED,
        "indexed_revisions_checked": indexed.revision_count,
        "indexed_temporal_coordinates_checked": indexed.temporal_count,
        "indexed_capability_coordinates_checked": indexed.capability_count,
        "indexed_fact_queries_checked": indexed.fact_count,
        "cache": CheckStatus.PASSED if cache_difference is None else CheckStatus.FAILED,
        "publication_readiness": CheckStatus.PASSED if passed else CheckStatus.FAILED,
        "authority_difference": authority_difference,
        "facts_difference": facts.difference,
        "indexed_difference": indexed.difference,
        "descriptor": indexed.descriptor,
    }


def _compile_authority_pair(
    source_registry: Path,
    candidate_registry: Path,
    source_root: Path,
) -> _AuthorityPair:
    clear_registry_tree_cache()
    source = compile_validated_authority(source_registry, source_root)
    source_cold = _typed_projection(source.modelos)
    source_warm = _typed_projection(compile_validated_authority(source_registry, source_root).modelos)
    candidate = compile_validated_authority(candidate_registry, source_root)
    candidate_cold = _typed_projection(candidate.modelos)
    candidate_warm = _typed_projection(compile_validated_authority(candidate_registry, source_root).modelos)
    return _AuthorityPair(source, candidate, source_cold, source_warm, candidate_cold, candidate_warm)


def _authority_prerequisite_failure(error: Exception) -> dict[str, object]:
    return {
        "equivalence": CheckStatus.UNRESOLVED,
        "facts": CheckStatus.UNRESOLVED,
        "indexed": CheckStatus.UNRESOLVED,
        "cache": CheckStatus.UNRESOLVED,
        "publication_readiness": CheckStatus.FAILED,
        "detail": f"validated authority prerequisite failed: {type(error).__name__}: {error}",
    }


def _authority_cache_difference(authorities: _AuthorityPair) -> Mapping[str, object] | None:
    return _first_difference(authorities.source_cold, authorities.source_warm) or _first_difference(
        authorities.candidate_cold,
        authorities.candidate_warm,
    )


def _compare_fact_authorities(
    source: ValidatedRegistryAuthority,
    candidate: ValidatedRegistryAuthority,
) -> _FactParity:
    difference = _first_difference(
        _typed_projection(source.catalogues.facts),
        _typed_projection(candidate.catalogues.facts),
    )
    queries = _fact_queries(source)
    checked = 0
    if difference is None:
        difference, checked = _first_fact_difference(
            queries,
            source.resolve_governed_fact,
            candidate.resolve_governed_fact,
            "$.facts",
        )
    return _FactParity(difference, checked, queries)


def _first_fact_difference(
    queries: Sequence[GovernedFactQuery],
    left_resolver: Callable[[GovernedFactQuery], object],
    right_resolver: Callable[[GovernedFactQuery], object],
    path_prefix: str,
) -> tuple[Mapping[str, object] | None, int]:
    for checked, query in enumerate(queries, start=1):
        difference = _first_difference(
            _fact_result(left_resolver, query),
            _fact_result(right_resolver, query),
            f"{path_prefix}.{query.fact_id}",
        )
        if difference is not None:
            return difference, checked
    return None, len(queries)


def _indexed_authority_parity(
    candidate_registry: Path,
    source_root: Path,
    indexed_dir: Path,
    source: ValidatedRegistryAuthority,
    candidate: ValidatedRegistryAuthority,
    fact_queries: Sequence[GovernedFactQuery],
) -> _IndexedParity:
    try:
        descriptor = publish_sqlite_authority_candidate(
            registry_root=candidate_registry,
            source_root=source_root,
            profile_schema_path=source_root / "registry" / "cadrumo" / "user_profile" / "schema.toml",
            destination=indexed_dir,
        )
        indexed = IndexedRegistryAuthority(indexed_dir / AUTHORITY_DESCRIPTOR_FILENAME)
        try:
            with indexed.operation() as operation:
                compared = _compare_indexed_operation(operation, source, candidate, fact_queries)
        finally:
            indexed.close()
        return _IndexedParity(
            compared.difference,
            compared.revision_count,
            compared.temporal_count,
            compared.capability_count,
            compared.fact_count,
            asdict(descriptor),
        )
    except Exception as exc:
        return _IndexedParity(None, detail=f"temporary indexed build failed: {type(exc).__name__}: {exc}")


def _compare_indexed_operation(
    operation: PinnedAuthorityOperation,
    source: ValidatedRegistryAuthority,
    candidate: ValidatedRegistryAuthority,
    fact_queries: Sequence[GovernedFactQuery],
) -> _IndexedParity:
    expected_ids = tuple(
        sorted((str(modelo.id), str(revision_id)) for modelo in candidate.modelos for revision_id in modelo.revisions)
    )
    difference = _indexed_revision_ids_difference(operation, expected_ids)
    revision_count = 0
    if difference is None:
        difference, revision_count = _indexed_revision_difference(operation, candidate, expected_ids)
    support = candidate.catalogues.supported_filing_years
    temporal_count = capability_count = 0
    if difference is None and support is None:
        difference = {"location": "$.support", "reason": "supported range missing"}
    if difference is None and support is not None:
        difference, temporal_count, capability_count = _indexed_temporal_and_capability_difference(
            operation,
            source,
            candidate,
            support,
        )
    fact_count = 0
    if difference is None:
        difference, fact_count = _indexed_fact_difference(operation, candidate, fact_queries)
    return _IndexedParity(difference, revision_count, temporal_count, capability_count, fact_count)


def _indexed_revision_ids_difference(
    operation: PinnedAuthorityOperation,
    expected_ids: tuple[tuple[str, str], ...],
) -> Mapping[str, object] | None:
    return _first_difference(expected_ids, tuple(sorted(operation.revision_ids())), "$.revision_ids")


def _indexed_revision_difference(
    operation: PinnedAuthorityOperation,
    candidate: ValidatedRegistryAuthority,
    expected_ids: Sequence[tuple[str, str]],
) -> tuple[Mapping[str, object] | None, int]:
    checked = 0
    for modelo_id, revision_id in expected_ids:
        expected = candidate.modelo(modelo_id).revisions[revision_id]
        actual = _indexed_complete_revision(operation, modelo_id, revision_id)
        checked += 1
        difference = _first_difference(
            _typed_projection(expected),
            _typed_projection(actual),
            f"$.{modelo_id}.{revision_id}",
        )
        if difference is not None:
            return difference, checked
    return None, checked


def _indexed_temporal_and_capability_difference(
    operation: PinnedAuthorityOperation,
    source: ValidatedRegistryAuthority,
    candidate: ValidatedRegistryAuthority,
    support: SupportedFilingYearsCatalogue,
) -> tuple[Mapping[str, object] | None, int, int]:
    sample_ceiling = support.hard_ceiling if support.hard_ceiling is not None else support.horizon + 1
    source_by_id = {str(modelo.id): modelo for modelo in source.modelos}
    temporal_checked = capability_checked = 0
    for modelo in candidate.modelos:
        modelo_id = str(modelo.id)
        difference, temporal_count, capability_count = _indexed_modelo_temporal_difference(
            operation,
            source,
            candidate,
            source_by_id[modelo_id],
            modelo,
            support,
            sample_ceiling,
        )
        temporal_checked += temporal_count
        capability_checked += capability_count
        if difference is not None:
            return difference, temporal_checked, capability_checked
    return None, temporal_checked, capability_checked


def _indexed_modelo_temporal_difference(
    operation: PinnedAuthorityOperation,
    source_authority: ValidatedRegistryAuthority,
    candidate_authority: ValidatedRegistryAuthority,
    source_modelo: ModeloDefinition,
    candidate_modelo: ModeloDefinition,
    support: SupportedFilingYearsCatalogue,
    ceiling: int,
) -> tuple[Mapping[str, object] | None, int, int]:
    modelo_id = str(candidate_modelo.id)
    temporal_checked = capability_checked = 0
    for coordinate in request_matrix(candidate_modelo, floor=support.floor, ceiling=ceiling):
        temporal_checked += 1
        difference = _indexed_temporal_difference(operation, source_modelo, modelo_id, coordinate, support)
        if difference is not None:
            return difference, temporal_checked, capability_checked
        capability_checked += 1
        difference = _indexed_capability_difference(
            operation,
            source_authority,
            candidate_authority,
            modelo_id,
            coordinate,
        )
        if difference is not None:
            return difference, temporal_checked, capability_checked
    return None, temporal_checked, capability_checked


def _indexed_temporal_difference(
    operation: PinnedAuthorityOperation,
    source_modelo: ModeloDefinition,
    modelo_id: str,
    coordinate: RequestCoordinate,
    support: SupportedFilingYearsCatalogue,
) -> Mapping[str, object] | None:
    return _first_difference(
        _selection_result(source_modelo, coordinate, support),
        _indexed_selection_result(operation, modelo_id, coordinate),
        f"$.temporal.{modelo_id}",
    )


def _indexed_capability_difference(
    operation: PinnedAuthorityOperation,
    source_authority: ValidatedRegistryAuthority,
    candidate_authority: ValidatedRegistryAuthority,
    modelo_id: str,
    coordinate: RequestCoordinate,
) -> Mapping[str, object] | None:
    source_snapshot = _snapshot_result(source_authority.snapshot, modelo_id, coordinate)
    candidate_snapshot = _snapshot_result(candidate_authority.snapshot, modelo_id, coordinate)
    indexed_snapshot = _snapshot_result(
        operation.snapshot,
        modelo_id,
        coordinate,
        indexed_form_layout=operation.form_layout,
    )
    return _first_difference(
        source_snapshot,
        candidate_snapshot,
        f"$.capability.source_candidate.{modelo_id}",
    ) or _first_difference(
        candidate_snapshot,
        indexed_snapshot,
        f"$.capability.candidate_indexed.{modelo_id}",
    )


def _indexed_fact_difference(
    operation: PinnedAuthorityOperation,
    candidate: ValidatedRegistryAuthority,
    queries: Sequence[GovernedFactQuery],
) -> tuple[Mapping[str, object] | None, int]:
    return _first_fact_difference(
        queries,
        candidate.resolve_governed_fact,
        operation.resolve_governed_fact,
        "$.indexed_facts",
    )
