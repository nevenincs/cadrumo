"""Held-out miss-rate evaluation for the compiled terminology relevance map.

The evaluator is the deferral gate for a possible rung-2 static
term-embedding matrix. It measures the committed, laundered mapping exactly as
the offline docs build will consume it. A high miss-rate only justifies rung-2
work when the input sweep is not already marked degraded; a saturated RAG run
must be refreshed first, not disguised as a semantic retrieval failure.
"""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import Final

from pydantic import BaseModel, ConfigDict, Field

from cadrumo.core.resources import bundled_path

from ._sweep import SweepResult

__all__ = [
    "DEFAULT_RUNG2_MISS_RATE_THRESHOLD",
    "TOP_RESULTS_BOUND",
    "HeldOutCaseKind",
    "HeldOutQueryCase",
    "HeldOutQuerySet",
    "MissRateEvaluation",
    "MissRateRow",
    "MissReason",
    "Rung2Adjudication",
    "Rung2Decision",
    "adjudicate_rung2",
    "evaluate_held_out_miss_rate",
    "held_out_query_set_path",
    "load_committed_relevance",
    "load_held_out_query_set",
    "relevance_mapping_path",
]

# The ratified materiality line (2026-07-13 ADR, D3): implement rung 2 only
# when MORE THAN ten percent of held-out queries miss the top-five shipped
# results. The gate default IS the ratified number; never loosen it ad hoc.
DEFAULT_RUNG2_MISS_RATE_THRESHOLD = 0.10
#: ADR D3 counts a hit only within the top five shipped results.
TOP_RESULTS_BOUND = 5
_UTF_8: Final[str] = "utf-8"


class MissReason(StrEnum):
    """Outcome reason for one held-out query case."""

    HIT = "hit"
    QUERY_NOT_COMPILED = "query-not-compiled"
    NO_TARGETS = "no-targets"
    TARGET_MISMATCH = "target-mismatch"


class Rung2Decision(StrEnum):
    """Measured decision for the static term-embedding matrix."""

    KEEP_DEFERRED = "keep-deferred"
    REFRESH_RELEVANCE_FIRST = "refresh-relevance-first"
    IMPLEMENT_RUNG2 = "implement-rung-2"


class HeldOutCaseKind(StrEnum):
    """How a held-out case is evaluated against the compiled mapping."""

    #: The query is a shipped vocabulary row; hit iff an expected id is in the
    #: TOP FIVE targets of exactly that compiled query (ADR D3 bound).
    VOCABULARY = "vocabulary"
    #: The query is a real free-text phrasing that is NOT in the vocabulary;
    #: candidate compiled queries are those whose normalised text appears
    #: word-bounded inside the case query (mirroring the shipped palette's
    #: lexical containment over term cards). No candidate at all is a
    #: query-not-compiled miss -- exactly the class rung 2 would serve.
    OUT_OF_SAMPLE = "out_of_sample"


class HeldOutQueryCase(BaseModel):
    """One real operator query and the record ids that would satisfy it."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    query: str = Field(min_length=1, max_length=160)
    concept_id: str = Field(min_length=2, max_length=64)
    expected_record_ids: tuple[str, ...] = Field(min_length=1)
    source: str = Field(min_length=12, max_length=500)
    kind: HeldOutCaseKind = HeldOutCaseKind.VOCABULARY


class HeldOutQuerySet(BaseModel):
    """Versioned held-out query corpus used only for evaluation."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    version: int = Field(ge=1)
    description: str = Field(min_length=20, max_length=500)
    cases: tuple[HeldOutQueryCase, ...] = Field(min_length=1)


class MissRateRow(BaseModel):
    """Measured outcome for one held-out query case."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    query: str
    concept_id: str
    hit: bool
    reason: MissReason
    matched_record_id: str | None = None
    target_count: int = Field(ge=0)


class MissRateEvaluation(BaseModel):
    """Aggregate miss-rate measurement over the committed relevance mapping."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    case_count: int = Field(ge=1)
    hit_count: int = Field(ge=0)
    miss_count: int = Field(ge=0)
    miss_rate: float = Field(ge=0.0, le=1.0)
    compiled_query_count: int = Field(ge=0)
    compiled_failed_query_count: int = Field(ge=0)
    compiled_targeted_query_count: int = Field(ge=0)
    rows: tuple[MissRateRow, ...] = Field(min_length=1)


class Rung2Adjudication(BaseModel):
    """Rung-2 decision derived from a miss-rate evaluation."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    decision: Rung2Decision
    miss_rate_threshold: float = Field(ge=0.0, le=1.0)
    measured_miss_rate: float = Field(ge=0.0, le=1.0)
    rationale: str = Field(min_length=20, max_length=800)


def relevance_mapping_path() -> Path:
    """Return the bundled path for the committed relevance mapping."""

    return bundled_path("terminology", "relevance", "relevance.json")


def held_out_query_set_path() -> Path:
    """Return the bundled path for the held-out query corpus."""

    return bundled_path("terminology", "evaluation", "held-out-queries.json")


def load_committed_relevance(path: Path | None = None) -> SweepResult:
    """Load and strictly validate the committed relevance mapping."""

    resolved = path if path is not None else relevance_mapping_path()
    return SweepResult.model_validate_json(resolved.read_text(encoding=_UTF_8))


def load_held_out_query_set(path: Path | None = None) -> HeldOutQuerySet:
    """Load and strictly validate the held-out query corpus."""

    resolved = path if path is not None else held_out_query_set_path()
    return HeldOutQuerySet.model_validate_json(resolved.read_text(encoding=_UTF_8))


def evaluate_held_out_miss_rate(
    *,
    query_set: HeldOutQuerySet | None = None,
    relevance: SweepResult | None = None,
) -> MissRateEvaluation:
    """Measure held-out misses against the committed relevance mapping."""

    resolved_cases = query_set if query_set is not None else load_held_out_query_set()
    resolved_relevance = relevance if relevance is not None else load_committed_relevance()
    by_case_key = {
        (mapping.concept_id, _normalise_query(mapping.query)): mapping for mapping in resolved_relevance.mappings
    }

    rows: list[MissRateRow] = []
    for case in resolved_cases.cases:
        if case.kind is HeldOutCaseKind.OUT_OF_SAMPLE:
            rows.append(_evaluate_out_of_sample(case, resolved_relevance))
            continue
        mapping = by_case_key.get((case.concept_id, _normalise_query(case.query)))
        if mapping is None:
            rows.append(_row_for(case, hit=False, reason=MissReason.QUERY_NOT_COMPILED, target_count=0))
            continue
        if not mapping.targets:
            rows.append(_row_for(case, hit=False, reason=MissReason.NO_TARGETS, target_count=0))
            continue
        top_targets = mapping.targets[:TOP_RESULTS_BOUND]
        target_ids = {target.record_id for target in top_targets}
        matched = next((record_id for record_id in case.expected_record_ids if record_id in target_ids), None)
        rows.append(
            _row_for(
                case,
                hit=matched is not None,
                reason=MissReason.HIT if matched is not None else MissReason.TARGET_MISMATCH,
                matched_record_id=matched,
                target_count=len(top_targets),
            ),
        )

    hits = sum(1 for row in rows if row.hit)
    misses = len(rows) - hits
    targeted = sum(1 for mapping in resolved_relevance.mappings if mapping.targets)
    return MissRateEvaluation(
        case_count=len(rows),
        hit_count=hits,
        miss_count=misses,
        miss_rate=misses / len(rows),
        compiled_query_count=resolved_relevance.query_count,
        compiled_failed_query_count=resolved_relevance.failed_query_count,
        compiled_targeted_query_count=targeted,
        rows=tuple(rows),
    )


def _evaluate_out_of_sample(case: HeldOutQueryCase, relevance: SweepResult) -> MissRateRow:
    """Evaluate a free-text case against the compiled mapping's lexical reach.

    Mirrors the shipped palette's containment matching over the precompiled
    tiers only: a compiled query is a candidate when its normalised text
    occurs word-bounded inside the case query. The full-text Pagefind tier is
    NOT modelled, so an out-of-sample miss is an UPPER BOUND on the shipped
    miss -- the honest direction for a gate that triggers paying for rung 2.
    """
    case_text = f" {_normalise_query(case.query)} "
    candidate_targets: list[str] = []
    for mapping in relevance.mappings:
        compiled = _normalise_query(mapping.query)
        if compiled and f" {compiled} " in case_text:
            candidate_targets.extend(target.record_id for target in mapping.targets[:TOP_RESULTS_BOUND])
    if not candidate_targets:
        return _row_for(case, hit=False, reason=MissReason.QUERY_NOT_COMPILED, target_count=0)
    target_ids = set(candidate_targets)
    matched = next((record_id for record_id in case.expected_record_ids if record_id in target_ids), None)
    return _row_for(
        case,
        hit=matched is not None,
        reason=MissReason.HIT if matched is not None else MissReason.TARGET_MISMATCH,
        matched_record_id=matched,
        target_count=len(target_ids),
    )


def adjudicate_rung2(
    evaluation: MissRateEvaluation,
    *,
    miss_rate_threshold: float = DEFAULT_RUNG2_MISS_RATE_THRESHOLD,
) -> Rung2Adjudication:
    """Adjudicate whether the static rung-2 matrix is justified by measurements."""

    if evaluation.compiled_failed_query_count > 0:
        return Rung2Adjudication(
            decision=Rung2Decision.REFRESH_RELEVANCE_FIRST,
            miss_rate_threshold=miss_rate_threshold,
            measured_miss_rate=evaluation.miss_rate,
            rationale=(
                "The compiled relevance artifact records failed sweep queries, so misses first require a full "
                "relevance refresh from the resident RAG service before they can justify a static embedding matrix."
            ),
        )
    if evaluation.miss_rate > miss_rate_threshold:
        return Rung2Adjudication(
            decision=Rung2Decision.IMPLEMENT_RUNG2,
            miss_rate_threshold=miss_rate_threshold,
            measured_miss_rate=evaluation.miss_rate,
            rationale=(
                "The relevance artifact is not marked degraded and the held-out miss-rate exceeds the accepted "
                "threshold, so rung-2 static term embeddings are justified."
            ),
        )
    return Rung2Adjudication(
        decision=Rung2Decision.KEEP_DEFERRED,
        miss_rate_threshold=miss_rate_threshold,
        measured_miss_rate=evaluation.miss_rate,
        rationale=(
            "The relevance artifact is not marked degraded and the held-out miss-rate is within the accepted "
            "threshold, so rung-2 static term embeddings remain deferred."
        ),
    )


def _row_for(
    case: HeldOutQueryCase,
    *,
    hit: bool,
    reason: MissReason,
    target_count: int,
    matched_record_id: str | None = None,
) -> MissRateRow:
    return MissRateRow(
        query=case.query,
        concept_id=case.concept_id,
        hit=hit,
        reason=reason,
        matched_record_id=matched_record_id,
        target_count=target_count,
    )


def _normalise_query(value: str) -> str:
    return " ".join(value.strip().casefold().split())
