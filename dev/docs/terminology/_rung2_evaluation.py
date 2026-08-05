"""Source-only held-out measurement for the Rung-2 browser candidate seam.

This module mirrors ``rung2SemanticCandidates`` in the browser controller over
an already validated :class:`Rung2SearchBundle`.  It deliberately has no file
I/O, provider, artifact, browser-config, acceptance, or result-destination
responsibility.  Candidate output contains only manifest record ids and the
scores needed to measure held-out recall; Pagefind and the baseline lexical
evaluator remain separate authorities for their respective surfaces.

``evaluate_rung2_held_out`` is therefore a measurement primitive for the
semantic tier, not the final P02.S07 standing report.  The composition seam
below can order a caller's independently captured Pagefind observations, but
does not capture Pagefind or establish release acceptance.
"""

from __future__ import annotations

from functools import cmp_to_key
import math
import struct
from enum import StrEnum
from typing import Annotated, Final, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator

from ._miss_rate import HeldOutQuerySet
from ._rung2_bridge import Rung2SearchBundle
from ._static_matrix import (
    MatrixCompilationError,
    QuantizedEmbeddingRow,
    QuantizedQueryTokenRow,
    normalise_query_tokens,
)

__all__ = [
    "Rung2CandidateStatus",
    "Rung2CoverageEvidence",
    "Rung2Evaluation",
    "Rung2EvaluationError",
    "Rung2EvaluationPolicy",
    "Rung2EvaluationReason",
    "Rung2EvaluationRow",
    "Rung2CompositionEntry",
    "Rung2CompositionResult",
    "Rung2LexicalObservation",
    "Rung2SemanticCandidate",
    "Rung2SemanticCandidateResult",
    "aggregate_rung2_coverage",
    "compose_rung2_candidates",
    "evaluate_rung2_held_out",
    "rung2_semantic_candidates",
]

_UTF_8: Final[str] = "utf-8"
_JS_MAX_SAFE_INTEGER: Final[int] = 2**53 - 1
_COMPOSE_RESULT_LIMIT: Final[int] = 18
_RecordId = Annotated[str, StringConstraints(min_length=1, max_length=320)]
_Sha256 = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]


class Rung2EvaluationError(ValueError):
    """Raised when a validated bundle cannot be executed by the browser algorithm."""


class Rung2EvaluationPolicy(BaseModel):
    """Explicit measured values used by the browser candidate algorithm.

    The policy has no defaults and does not contain ``approved`` or any other
    release evidence.  ``result_limit`` is explicit so a measurement cannot
    silently use a different cap; the accepted browser contract fixes it at
    five results.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    minimum_coverage_ratio: float = Field(gt=0.0, le=1.0)
    cosine_floor: float = Field(ge=-1.0, le=1.0)
    runner_up_margin: float = Field(ge=0.0, le=2.0)
    result_limit: Literal[5]

    @field_validator("minimum_coverage_ratio", "cosine_floor", "runner_up_margin")
    @classmethod
    def _require_finite_measurement(cls, value: float) -> float:
        """Reject a policy value that cannot be used deterministically."""
        if not math.isfinite(value):
            raise ValueError("Rung-2 evaluation policy values must be finite")
        return value


class Rung2CandidateStatus(StrEnum):
    """Outcome of the browser-equivalent candidate algorithm for one query."""

    CANDIDATES = "candidates"
    EMPTY_QUERY = "empty-query"
    INSUFFICIENT_COVERAGE = "insufficient-coverage"
    NON_FINITE_QUERY_VECTOR = "non-finite-query-vector"
    ZERO_QUERY_VECTOR = "zero-query-vector"
    RUNNER_UP_AMBIGUITY = "runner-up-ambiguity"
    NO_COSINE_MATCH = "no-cosine-match"


class Rung2EvaluationReason(StrEnum):
    """Measured held-out outcome without implying a release decision."""

    HIT = "hit"
    TARGET_MISMATCH = "target-mismatch"
    EMPTY_QUERY = Rung2CandidateStatus.EMPTY_QUERY.value
    INSUFFICIENT_COVERAGE = Rung2CandidateStatus.INSUFFICIENT_COVERAGE.value
    NON_FINITE_QUERY_VECTOR = Rung2CandidateStatus.NON_FINITE_QUERY_VECTOR.value
    ZERO_QUERY_VECTOR = Rung2CandidateStatus.ZERO_QUERY_VECTOR.value
    RUNNER_UP_AMBIGUITY = Rung2CandidateStatus.RUNNER_UP_AMBIGUITY.value
    NO_COSINE_MATCH = Rung2CandidateStatus.NO_COSINE_MATCH.value


class Rung2SemanticCandidate(BaseModel):
    """One browser-equivalent candidate identified only by its record id."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    record_id: _RecordId
    semantic_score: float
    semantic_ranking_weight: float = Field(ge=0.0, le=1.0)

    @field_validator("semantic_score", "semantic_ranking_weight")
    @classmethod
    def _require_finite_score(cls, value: float) -> float:
        """Keep measured ordering values finite."""
        if not math.isfinite(value):
            raise ValueError("Rung-2 candidate scores must be finite")
        return value


class Rung2SemanticCandidateResult(BaseModel):
    """Browser-equivalent candidates and the reason for an abstention, if any."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    query_tokens: tuple[str, ...]
    covered_token_count: int = Field(ge=0)
    candidates: tuple[Rung2SemanticCandidate, ...]
    status: Rung2CandidateStatus


class Rung2LexicalObservation(BaseModel):
    """One explicitly captured Pagefind row needed by the browser ladder.

    The caller supplies these observations later from an independent Pagefind
    capture; this model never loads or queries Pagefind and has no defaults.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    record_id: _RecordId
    tier_rank: float = Field(ge=0.0)
    direct_match_strength: Literal[0, 1, 2, 3]
    is_lexical_card: bool
    relevance_rank: int = Field(ge=0, le=_JS_MAX_SAFE_INTEGER)

    @field_validator("tier_rank")
    @classmethod
    def _require_finite_tier_rank(cls, value: float) -> float:
        """Keep lexical ordering deterministic."""
        if not math.isfinite(value):
            raise ValueError("lexical tier ranks must be finite")
        return value


class Rung2CompositionEntry(BaseModel):
    """One ordered, deduplicated row in the source-only combined ladder."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    record_id: _RecordId
    source: Literal["lexical", "semantic"]
    tier_rank: float = Field(ge=0.0)
    direct_match_strength: Literal[0, 1, 2, 3]
    is_lexical_card: bool
    relevance_rank: int = Field(ge=0, le=_JS_MAX_SAFE_INTEGER)
    semantic_score: float | None
    semantic_ranking_weight: float | None = Field(ge=0.0, le=1.0)

    @field_validator("tier_rank", "semantic_score", "semantic_ranking_weight")
    @classmethod
    def _require_finite_ordering_value(cls, value: float | None) -> float | None:
        """Keep every emitted ordering value finite when present."""
        if value is not None and not math.isfinite(value):
            raise ValueError("composition ordering values must be finite")
        return value

    @model_validator(mode="after")
    def _enforce_source_fields(self) -> Rung2CompositionEntry:
        """Keep lexical and semantic rows explicit rather than silently mixed."""
        if self.source == "lexical":
            if self.semantic_score is not None or self.semantic_ranking_weight is not None:
                raise ValueError("lexical composition entries cannot carry semantic scores")
        elif (
            self.semantic_score is None
            or self.semantic_ranking_weight is None
            or self.is_lexical_card
            or self.direct_match_strength != 0
        ):
            raise ValueError("semantic composition entries require semantic scores")
        return self


class Rung2CompositionResult(BaseModel):
    """Measured browser ordering from supplied lexical rows plus semantic rows."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    semantic_status: Rung2CandidateStatus
    entries: tuple[Rung2CompositionEntry, ...]


class Rung2EvaluationRow(BaseModel):
    """One held-out measurement row for the bounded semantic tier."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    query: str = Field(min_length=1, max_length=160)
    concept_id: str = Field(min_length=2, max_length=64)
    expected_record_ids: tuple[_RecordId, ...] = Field(min_length=1)
    candidate_record_ids: tuple[_RecordId, ...]
    query_token_count: int = Field(ge=0)
    covered_token_count: int = Field(ge=0)
    hit: bool
    reason: Rung2EvaluationReason
    matched_record_id: _RecordId | None


class Rung2Evaluation(BaseModel):
    """Held-out semantic measurement, without adjudication or acceptance."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    query_set_version: int = Field(ge=1)
    policy: Rung2EvaluationPolicy
    case_count: int = Field(ge=1)
    hit_count: int = Field(ge=0)
    miss_count: int = Field(ge=0)
    held_out_miss_rate: float = Field(ge=0.0, le=1.0)
    rows: tuple[Rung2EvaluationRow, ...] = Field(min_length=1)

    @field_validator("held_out_miss_rate")
    @classmethod
    def _require_finite_miss_rate(cls, value: float) -> float:
        """Keep the reported measurement finite."""
        if not math.isfinite(value):
            raise ValueError("held-out miss rate must be finite")
        return value


class Rung2CoverageEvidence(BaseModel):
    """Aggregate token-coverage evidence bound to one validated bundle.

    This is measurement evidence only.  It does not approve a browser tier,
    adjudicate miss rate, or replace the accepted artifact and licence gates.
    The two artifact digests and the matrix query-token fingerprint make the
    aggregate auditable against the exact bundle that produced its rows.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    query_set_version: int = Field(ge=1)
    matrix_query_token_sha256: _Sha256
    matrix_artifact_sha256: _Sha256
    bundle_artifact_sha256: _Sha256
    minimum_coverage_ratio: float = Field(gt=0.0, le=1.0)
    query_count: int = Field(gt=0)
    total_query_token_count: int = Field(gt=0)
    total_covered_token_count: int = Field(ge=0)
    fully_covered_query_count: int = Field(ge=0)
    zero_covered_query_count: int = Field(ge=0)
    below_minimum_coverage_query_count: int = Field(ge=0)
    aggregate_coverage_ratio: float = Field(ge=0.0, le=1.0)

    @field_validator("minimum_coverage_ratio", "aggregate_coverage_ratio")
    @classmethod
    def _require_finite_ratio(cls, value: float) -> float:
        """Reject non-finite coverage evidence before it can be serialized."""
        if not math.isfinite(value):
            raise ValueError("Rung-2 coverage ratios must be finite")
        return value

    @model_validator(mode="after")
    def _enforce_coverage_invariants(self) -> Rung2CoverageEvidence:
        """Keep aggregate counts and the reported ratio self-consistent."""
        if self.total_covered_token_count > self.total_query_token_count:
            raise ValueError("covered token count cannot exceed total query token count")
        if self.total_query_token_count < self.query_count:
            raise ValueError("total query token count cannot be below query count")
        if self.fully_covered_query_count > self.query_count:
            raise ValueError("fully covered query count cannot exceed query count")
        if self.zero_covered_query_count > self.query_count:
            raise ValueError("zero-covered query count cannot exceed query count")
        if self.fully_covered_query_count + self.zero_covered_query_count > self.query_count:
            raise ValueError("fully covered and zero-covered queries cannot overlap")
        if self.below_minimum_coverage_query_count > self.query_count:
            raise ValueError("below-minimum query count cannot exceed query count")
        if self.zero_covered_query_count > self.below_minimum_coverage_query_count:
            raise ValueError("zero-covered queries must be below the minimum coverage threshold")
        expected_ratio = self.total_covered_token_count / self.total_query_token_count
        if self.aggregate_coverage_ratio != expected_ratio:
            raise ValueError("aggregate coverage ratio does not match the token counts")
        return self


def aggregate_rung2_coverage(
    evaluation: object,
    bundle: object,
) -> Rung2CoverageEvidence:
    """Aggregate validated held-out rows without I/O or release adjudication.

    The evaluator remains responsible for producing browser-equivalent rows.
    This function only verifies the row arithmetic and binds the resulting
    coverage evidence to the exact validated matrix and bundle identities.
    """
    if not isinstance(evaluation, Rung2Evaluation):
        raise Rung2EvaluationError("evaluation must be a validated Rung2Evaluation")
    if not isinstance(bundle, Rung2SearchBundle):
        raise Rung2EvaluationError("bundle must be a validated Rung2SearchBundle")
    if evaluation.case_count != len(evaluation.rows):
        raise Rung2EvaluationError("evaluation case_count does not match its rows")
    if evaluation.hit_count + evaluation.miss_count != evaluation.case_count:
        raise Rung2EvaluationError("evaluation hit and miss counts do not partition its cases")
    expected_miss_rate = evaluation.miss_count / evaluation.case_count
    if evaluation.held_out_miss_rate != expected_miss_rate:
        raise Rung2EvaluationError("evaluation miss rate does not match its hit and miss counts")

    total_tokens = 0
    total_covered = 0
    fully_covered = 0
    zero_covered = 0
    below_minimum = 0
    for row in evaluation.rows:
        if row.query_token_count <= 0:
            raise Rung2EvaluationError("coverage evidence requires every query to have normalized tokens")
        if row.covered_token_count > row.query_token_count:
            raise Rung2EvaluationError("a row reports more covered tokens than query tokens")
        total_tokens += row.query_token_count
        total_covered += row.covered_token_count
        ratio = row.covered_token_count / row.query_token_count
        if row.covered_token_count == row.query_token_count:
            fully_covered += 1
        if row.covered_token_count == 0:
            zero_covered += 1
        if ratio < evaluation.policy.minimum_coverage_ratio:
            below_minimum += 1

    return Rung2CoverageEvidence(
        query_set_version=evaluation.query_set_version,
        matrix_query_token_sha256=bundle.matrix.query_token_sha256,
        matrix_artifact_sha256=bundle.matrix.artifact_sha256,
        bundle_artifact_sha256=bundle.artifact_sha256,
        minimum_coverage_ratio=evaluation.policy.minimum_coverage_ratio,
        query_count=evaluation.case_count,
        total_query_token_count=total_tokens,
        total_covered_token_count=total_covered,
        fully_covered_query_count=fully_covered,
        zero_covered_query_count=zero_covered,
        below_minimum_coverage_query_count=below_minimum,
        aggregate_coverage_ratio=total_covered / total_tokens,
    )


def rung2_semantic_candidates(
    bundle: Rung2SearchBundle,
    query: str,
    policy: Rung2EvaluationPolicy,
) -> Rung2SemanticCandidateResult:
    """Mirror the browser's quantized Rung-2 candidate algorithm.

    The caller supplies both the validated bundle and every measured policy
    value.  The function never loads a bundle, constructs a URL, or applies a
    release threshold; an empty candidate tuple is the browser-equivalent
    abstention outcome for an ineligible query.
    """

    _require_inputs(bundle, policy)
    try:
        tokens = normalise_query_tokens(query)
    except MatrixCompilationError as exc:
        raise Rung2EvaluationError(f"query cannot be normalized for Rung-2 measurement: {exc}") from exc
    if not tokens:
        return _candidate_result(tokens, 0, (), Rung2CandidateStatus.EMPTY_QUERY)

    dimension = bundle.matrix.dimension
    query_rows = {row.token: row for row in bundle.matrix.query_token_rows}
    query_vector = [0.0] * dimension
    covered = 0
    for token in tokens:
        row = query_rows.get(token)
        if row is None:
            continue
        covered += 1
        for index in range(dimension):
            product = _float32(row.values[index] * row.scale)
            query_vector[index] = _float32(query_vector[index] + product)

    if covered == 0 or covered / len(tokens) < policy.minimum_coverage_ratio:
        return _candidate_result(tokens, covered, (), Rung2CandidateStatus.INSUFFICIENT_COVERAGE)
    if any(not math.isfinite(value) for value in query_vector):
        return _candidate_result(tokens, covered, (), Rung2CandidateStatus.NON_FINITE_QUERY_VECTOR)

    query_vector = [_float32(value / covered) for value in query_vector]
    query_norm_squared = _sum_of_squares(query_vector)
    query_norm = math.sqrt(query_norm_squared) if query_norm_squared >= 0.0 else float("nan")
    if not math.isfinite(query_norm) or query_norm <= 0.0:
        return _candidate_result(tokens, covered, (), Rung2CandidateStatus.ZERO_QUERY_VECTOR)

    bridge_by_term = {entry.term: entry for entry in bundle.bridge.entries}
    scored: list[tuple[str, float]] = []
    for row in bundle.matrix.rows:
        term_vector, term_norm = _dequantize(row, dimension=dimension)
        dot = 0.0
        for index in range(dimension):
            dot = _float32(dot + _float32(query_vector[index] * term_vector[index]))
        score = dot / (query_norm * term_norm)
        if math.isfinite(score) and score >= policy.cosine_floor:
            scored.append((row.term, score))
    scored.sort(key=lambda item: (-item[1], item[0].encode(_UTF_8)))
    if not scored:
        return _candidate_result(tokens, covered, (), Rung2CandidateStatus.NO_COSINE_MATCH)
    if len(scored) > 1 and scored[0][1] - scored[1][1] < policy.runner_up_margin:
        return _candidate_result(tokens, covered, (), Rung2CandidateStatus.RUNNER_UP_AMBIGUITY)

    by_record: dict[str, Rung2SemanticCandidate] = {}
    for term, score in scored:
        for target in bridge_by_term[term].targets:
            prior = by_record.get(target.record_id)
            if (
                prior is None
                or score > prior.semantic_score
                or score == prior.semantic_score and target.ranking_weight > prior.semantic_ranking_weight
            ):
                by_record[target.record_id] = Rung2SemanticCandidate(
                    record_id=target.record_id,
                    semantic_score=score,
                    semantic_ranking_weight=target.ranking_weight,
                )

    candidates = tuple(
        sorted(
            by_record.values(),
            key=lambda candidate: (
                -candidate.semantic_score,
                -candidate.semantic_ranking_weight,
                candidate.record_id.encode(_UTF_8),
            ),
        )[: policy.result_limit]
    )
    return _candidate_result(tokens, covered, candidates, Rung2CandidateStatus.CANDIDATES)


def compose_rung2_candidates(
    lexical_candidates: tuple[Rung2LexicalObservation, ...],
    semantic_result: Rung2SemanticCandidateResult,
) -> Rung2CompositionResult:
    """Compose a caller-supplied Pagefind tuple with an existing semantic result.

    This is a pure ordering measurement seam.  It consumes independently
    captured Pagefind observations later, never calls Pagefind or reads an
    artifact, and reports no release or acceptance evidence.
    """

    if not isinstance(lexical_candidates, tuple) or any(
        not isinstance(candidate, Rung2LexicalObservation) for candidate in lexical_candidates
    ):
        raise Rung2EvaluationError("lexical_candidates must be a tuple of validated Rung2LexicalObservation values")
    if not isinstance(semantic_result, Rung2SemanticCandidateResult):
        raise Rung2EvaluationError("semantic_result must be a validated Rung2SemanticCandidateResult")

    entries = tuple(_composition_entry(candidate) for candidate in lexical_candidates) + tuple(
        _composition_entry(candidate) for candidate in semantic_result.candidates
    )
    ordered = sorted(entries, key=cmp_to_key(_compare_composition_entries))
    seen_record_ids: set[str] = set()
    deduplicated: list[Rung2CompositionEntry] = []
    for entry in ordered:
        if entry.record_id in seen_record_ids:
            continue
        seen_record_ids.add(entry.record_id)
        deduplicated.append(entry)
        if len(deduplicated) == _COMPOSE_RESULT_LIMIT:
            break
    return Rung2CompositionResult(
        semantic_status=semantic_result.status,
        entries=tuple(deduplicated),
    )


def evaluate_rung2_held_out(
    bundle: Rung2SearchBundle,
    query_set: HeldOutQuerySet,
    policy: Rung2EvaluationPolicy,
) -> Rung2Evaluation:
    """Measure held-out expected ids against browser-equivalent top-five ids."""

    _require_inputs(bundle, policy)
    if not isinstance(query_set, HeldOutQuerySet):
        raise Rung2EvaluationError("query_set must be a validated HeldOutQuerySet")

    rows: list[Rung2EvaluationRow] = []
    for case in query_set.cases:
        result = rung2_semantic_candidates(bundle, case.query, policy)
        candidate_ids = tuple(candidate.record_id for candidate in result.candidates)
        matched = next((record_id for record_id in case.expected_record_ids if record_id in candidate_ids), None)
        if matched is not None:
            reason = Rung2EvaluationReason.HIT
        elif candidate_ids:
            reason = Rung2EvaluationReason.TARGET_MISMATCH
        else:
            reason = Rung2EvaluationReason(result.status.value)
        rows.append(
            Rung2EvaluationRow(
                query=case.query,
                concept_id=case.concept_id,
                expected_record_ids=case.expected_record_ids,
                candidate_record_ids=candidate_ids,
                query_token_count=len(result.query_tokens),
                covered_token_count=result.covered_token_count,
                hit=matched is not None,
                reason=reason,
                matched_record_id=matched,
            ),
        )

    hits = sum(1 for row in rows if row.hit)
    misses = len(rows) - hits
    return Rung2Evaluation(
        query_set_version=query_set.version,
        policy=policy,
        case_count=len(rows),
        hit_count=hits,
        miss_count=misses,
        held_out_miss_rate=misses / len(rows),
        rows=tuple(rows),
    )


def _composition_entry(
    candidate: Rung2LexicalObservation | Rung2SemanticCandidate,
) -> Rung2CompositionEntry:
    if isinstance(candidate, Rung2LexicalObservation):
        return Rung2CompositionEntry(
            record_id=candidate.record_id,
            source="lexical",
            tier_rank=candidate.tier_rank,
            direct_match_strength=candidate.direct_match_strength,
            is_lexical_card=candidate.is_lexical_card,
            relevance_rank=candidate.relevance_rank,
            semantic_score=None,
            semantic_ranking_weight=None,
        )
    # Browser semantic rows use the manifest's card band (1 + weight); the
    # validated semantic result carries that same explicit ranking weight.
    return Rung2CompositionEntry(
        record_id=candidate.record_id,
        source="semantic",
        tier_rank=1.0 + candidate.semantic_ranking_weight,
        direct_match_strength=0,
        is_lexical_card=False,
        relevance_rank=0,
        semantic_score=candidate.semantic_score,
        semantic_ranking_weight=candidate.semantic_ranking_weight,
    )


def _compare_composition_entries(
    left: Rung2CompositionEntry,
    right: Rung2CompositionEntry,
) -> int:
    """Mirror the browser comparator without relying on JavaScript defaults."""
    left_is_semantic = left.source == "semantic"
    right_is_semantic = right.source == "semantic"
    if left_is_semantic != right_is_semantic:
        left_is_direct = left.is_lexical_card or left.direct_match_strength > 0
        right_is_direct = right.is_lexical_card or right.direct_match_strength > 0
        if left_is_direct != right_is_direct:
            return -1 if left_is_direct else 1
        if left_is_direct and right_is_direct and left.direct_match_strength != right.direct_match_strength:
            return -1 if left.direct_match_strength > right.direct_match_strength else 1

    if left.tier_rank != right.tier_rank:
        return -1 if left.tier_rank > right.tier_rank else 1
    if left.direct_match_strength != right.direct_match_strength:
        return -1 if left.direct_match_strength > right.direct_match_strength else 1
    if left_is_semantic and right_is_semantic:
        assert left.semantic_score is not None
        assert right.semantic_score is not None
        if left.semantic_score != right.semantic_score:
            return -1 if left.semantic_score > right.semantic_score else 1
        assert left.semantic_ranking_weight is not None
        assert right.semantic_ranking_weight is not None
        if left.semantic_ranking_weight != right.semantic_ranking_weight:
            return -1 if left.semantic_ranking_weight > right.semantic_ranking_weight else 1
        if left.record_id.encode(_UTF_8) != right.record_id.encode(_UTF_8):
            return -1 if left.record_id.encode(_UTF_8) < right.record_id.encode(_UTF_8) else 1
    if left.relevance_rank != right.relevance_rank:
        return -1 if left.relevance_rank < right.relevance_rank else 1
    return 0


def _candidate_result(
    query_tokens: tuple[str, ...],
    covered_token_count: int,
    candidates: tuple[Rung2SemanticCandidate, ...],
    status: Rung2CandidateStatus,
) -> Rung2SemanticCandidateResult:
    return Rung2SemanticCandidateResult(
        query_tokens=query_tokens,
        covered_token_count=covered_token_count,
        candidates=candidates,
        status=status,
    )


def _dequantize(
    row: QuantizedEmbeddingRow | QuantizedQueryTokenRow,
    *,
    dimension: int,
) -> tuple[tuple[float, ...], float]:
    """Reproduce the browser's float32 dequantization and norm calculation."""

    vector = tuple(_float32(value * row.scale) for value in row.values)
    if len(vector) != dimension or any(not math.isfinite(value) for value in vector):
        raise Rung2EvaluationError("Rung-2 dequantized term vector is non-finite or has the wrong dimension")
    norm_squared = _sum_of_squares(vector)
    norm = math.sqrt(norm_squared) if norm_squared >= 0.0 else float("nan")
    if not math.isfinite(norm) or norm <= 0.0:
        raise Rung2EvaluationError("Rung-2 dequantized term vector is zero or non-finite")
    return vector, norm


def _sum_of_squares(values: list[float] | tuple[float, ...]) -> float:
    """Sum squares with the browser's float32 multiplication and accumulation."""

    total = 0.0
    for value in values:
        total = _float32(total + _float32(value * value))
    return total


def _float32(value: float) -> float:
    """Match JavaScript ``Math.fround`` for finite values and overflow."""

    if not math.isfinite(value):
        return value
    try:
        return struct.unpack("<f", struct.pack("<f", value))[0]
    except (OverflowError, struct.error):
        return math.copysign(float("inf"), value)


def _require_inputs(bundle: object, policy: object) -> None:
    """Require the two explicit validated inputs without loading or defaulting."""

    if not isinstance(bundle, Rung2SearchBundle):
        raise Rung2EvaluationError("bundle must be an already validated Rung2SearchBundle")
    if not isinstance(policy, Rung2EvaluationPolicy):
        raise Rung2EvaluationError("policy must be an explicit validated Rung2EvaluationPolicy")
