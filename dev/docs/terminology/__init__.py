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
from ._unified_record import (
    RankingTier,
    SearchRecord,
    SearchRecordMetadata,
    kind_base_weight,
    normalise_ranking_weight,
    to_search_record,
)

__all__ = [
    "CasillaProjectionStats",
    "CasillaSearchRecord",
    "ChunkHit",
    "CliOptionRecord",
    "CliProjectionStats",
    "CliSurfaceRecord",
    "ConceptCardProjectionStats",
    "ConceptCardRecord",
    "DropReason",
    "DroppedHit",
    "GroundingSurface",
    "LegalGroundingLink",
    "LocalisedDefinition",
    "RankingTier",
    "ResolutionResult",
    "ResolvedTarget",
    "SearchRecord",
    "SearchRecordBase",
    "SearchRecordKind",
    "SearchRecordMetadata",
    "TargetResolver",
    "TermAlias",
    "kind_base_weight",
    "normalise_ranking_weight",
    "project_casilla_search_records",
    "project_cli_search_records",
    "project_concept_cards",
    "project_modelo_casillas",
    "resolve_chunk_hits",
    "to_search_record",
]
