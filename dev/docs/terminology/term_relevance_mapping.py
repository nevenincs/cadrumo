"""The shipped laundered term-to-target relevance mapping.

The build-time RAG sweep compiles a closed query vocabulary into ranked
targets, and this module is the contract for what that compilation SHIPS:
identifiers, deep-link targets, and normalised ranking weights, and nothing
else. No stored vector, no sparse term-weight map, no raw retrieval score, no
source path -- the laundering boundary is these three models, so a reader of
the committed data file and the runner that writes it cannot disagree about
what a shipped relevance unit may contain.

The runner (``sweep_runner``) produces one of these; the search-index injector
(``dev.docs.pagefind_inject``) validates the committed file back into one and
ranks palette results from it. The two sit in different packages and address
this same shape, so it has a defining module of its own rather than living
inside the runner.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from cadrumo.core.external_constants import OutputLanguage

from .search_record import SearchRecordKind

__all__ = [
    "SweepResult",
    "TermRelevanceMapping",
    "TermTargetRef",
]


class TermTargetRef(BaseModel):
    """A laundered term-to-target reference (ids + target + weight ONLY).

    The shipped relevance unit: no vectors, no sparse / SPLADE term weights, no
    raw retrieval score, no source path. Just the resolved record's id, its deep
    link target, its kind, and the normalised ranking weight a consumer sorts
    on. This is the laundering boundary for what ships.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    record_id: str = Field(min_length=1, max_length=320)
    target: str = Field(min_length=1, max_length=512)
    kind: SearchRecordKind
    surface: str = Field(min_length=1, max_length=32)
    ranking_weight: float = Field(ge=0.0, le=1.0)


class TermRelevanceMapping(BaseModel):
    """The ranked targets one query term resolved to, plus an audit summary.

    ``targets`` is the laundered ranked list (highest weight first). The audit
    is COUNTS only (``dropped`` / ``collapsed``) -- the per-hit drop/collapse
    detail stays in the build log, not the shipped mapping, so no path or score
    leaks. ``cluster_locator`` is the dominant directory cluster (a thin-signal
    tie-break hint), itself an identifier, not a vector.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    query: str = Field(min_length=1, max_length=160)
    concept_id: str = Field(min_length=2, max_length=64)
    language: OutputLanguage
    targets: tuple[TermTargetRef, ...] = Field(default=())
    dropped_count: int = Field(default=0, ge=0)
    collapsed_count: int = Field(default=0, ge=0)
    dominant_cluster: str | None = Field(default=None, min_length=1, max_length=272)


class SweepResult(BaseModel):
    """The full sweep output: one mapping per query term, plus run provenance.

    Strict, frozen, and JSON-serialisable so the sibling landing step
    serialises it to the committed relevance data file with one
    ``model_dump_json`` call -- the clean seam.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    mappings: tuple[TermRelevanceMapping, ...] = Field(default=())
    query_count: int = Field(ge=0)
    concept_count: int = Field(ge=0)
    #: How many queries failed retrieval (transient service errors) and were
    #: recorded as honest empty mappings. A non-zero count marks a degraded run.
    failed_query_count: int = Field(default=0, ge=0)
    #: The reindex-before-sweep outcome (the job-queued acknowledgement or a
    #: note that the index was used as-is because the service was busy).
    reindex_note: str = Field(min_length=1, max_length=1000)
    score_floor: float = Field(ge=0.0, le=1.0)
