"""Build-time compilers projecting registry data into docs search records.

This package is dev build tooling (alongside ``dev/docs/cli_reference.py``
and ``dev/docs/apidocs``), not shippable ``src/aeat`` code: the projected
records are a build-time artifact consumed by the downstream Pagefind
injection, never committed (like the generated CLI reference). Per ADR D4
the casilla records are MACHINE-GENERATED from registry snapshots and
never hand-curated, distinct from the curated ``aeat.terminology`` concept
Handbook.
"""

from __future__ import annotations

from ._casilla_projection import (
    CasillaProjectionStats,
    project_casilla_search_records,
    project_modelo_casillas,
)
from ._cli_projection import (
    CliOptionRecord,
    CliProjectionStats,
    CliSurfaceRecord,
    project_cli_search_records,
)
from ._concept_cards import (
    ConceptCardProjectionStats,
    ConceptCardRecord,
    LegalGroundingLink,
    LocalisedDefinition,
    TermAlias,
    project_concept_cards,
)
from ._miss_rate import (
    DEFAULT_RUNG2_MISS_RATE_THRESHOLD,
    HeldOutQueryCase,
    HeldOutQuerySet,
    MissRateEvaluation,
    MissRateRow,
    MissReason,
    Rung2Adjudication,
    Rung2Decision,
    adjudicate_rung2,
    evaluate_held_out_miss_rate,
    held_out_query_set_path,
    load_committed_relevance,
    load_held_out_query_set,
    relevance_mapping_path,
)
from ._resolution import (
    ChunkHit,
    DroppedHit,
    DropReason,
    GroundingSurface,
    ResolutionResult,
    ResolvedTarget,
    TargetResolver,
    resolve_chunk_hits,
)
from ._search_record import (
    CasillaSearchRecord,
    SearchRecordBase,
    SearchRecordKind,
)
from ._sweep import (
    DEFAULT_MAX_RESULTS,
    RagSearchClient,
    ServiceRagSearchClient,
    SweepError,
    SweepQuery,
    SweepResult,
    TermRelevanceMapping,
    TermTargetRef,
    enumerate_query_vocabulary,
    run_sweep,
)
from ._synonym_mining import (
    DEFAULT_RELATIVE_COSINE_THRESHOLDS,
    RatificationAction,
    RatificationStatus,
    RatificationValidationResult,
    RatificationViolation,
    RelativeCosineThresholds,
    SynonymCandidateEntry,
    SynonymCandidateObservation,
    SynonymRatificationQueue,
    load_synonym_ratification_queue,
    mine_synonym_candidates,
    synonym_ratification_queue_path,
    validate_ratification_queue,
)
from ._unified_record import (
    RankingTier,
    SearchRecord,
    SearchRecordMetadata,
    kind_base_weight,
    normalise_ranking_weight,
    to_search_record,
)
from ._wrangle import (
    STRONG_SIGNAL_SCORE_FLOOR,
    CollapsedHit,
    CollapseReason,
    DirectoryCluster,
    WrangledResult,
    read_clusters,
    wrangle,
)

__all__ = [
    "DEFAULT_MAX_RESULTS",
    "DEFAULT_RELATIVE_COSINE_THRESHOLDS",
    "DEFAULT_RUNG2_MISS_RATE_THRESHOLD",
    "STRONG_SIGNAL_SCORE_FLOOR",
    "CasillaProjectionStats",
    "CasillaSearchRecord",
    "ChunkHit",
    "CliOptionRecord",
    "CliProjectionStats",
    "CliSurfaceRecord",
    "CollapseReason",
    "CollapsedHit",
    "ConceptCardProjectionStats",
    "ConceptCardRecord",
    "DirectoryCluster",
    "DropReason",
    "DroppedHit",
    "GroundingSurface",
    "HeldOutQueryCase",
    "HeldOutQuerySet",
    "LegalGroundingLink",
    "LocalisedDefinition",
    "MissRateEvaluation",
    "MissRateRow",
    "MissReason",
    "RagSearchClient",
    "RankingTier",
    "RatificationAction",
    "RatificationStatus",
    "RatificationValidationResult",
    "RatificationViolation",
    "RelativeCosineThresholds",
    "ResolutionResult",
    "ResolvedTarget",
    "Rung2Adjudication",
    "Rung2Decision",
    "SearchRecord",
    "SearchRecordBase",
    "SearchRecordKind",
    "SearchRecordMetadata",
    "ServiceRagSearchClient",
    "SweepError",
    "SweepQuery",
    "SweepResult",
    "SynonymCandidateEntry",
    "SynonymCandidateObservation",
    "SynonymRatificationQueue",
    "TargetResolver",
    "TermAlias",
    "TermRelevanceMapping",
    "TermTargetRef",
    "WrangledResult",
    "adjudicate_rung2",
    "enumerate_query_vocabulary",
    "evaluate_held_out_miss_rate",
    "held_out_query_set_path",
    "kind_base_weight",
    "load_committed_relevance",
    "load_held_out_query_set",
    "load_synonym_ratification_queue",
    "mine_synonym_candidates",
    "normalise_ranking_weight",
    "project_casilla_search_records",
    "project_cli_search_records",
    "project_concept_cards",
    "project_modelo_casillas",
    "read_clusters",
    "relevance_mapping_path",
    "resolve_chunk_hits",
    "run_sweep",
    "synonym_ratification_queue_path",
    "to_search_record",
    "validate_ratification_queue",
    "wrangle",
]
