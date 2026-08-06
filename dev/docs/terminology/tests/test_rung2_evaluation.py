"""Real composition checks for the bounded Rung-2 browser ladder."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from dev.docs.terminology._rung2_evaluation import (
    Rung2CandidateStatus,
    Rung2Evaluation,
    Rung2EvaluationPolicy,
    Rung2EvaluationReason,
    Rung2EvaluationRow,
    Rung2LexicalObservation,
    Rung2SemanticCandidate,
    Rung2SemanticCandidateResult,
    compose_rung2_candidates,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core, pytest.mark.docs]


def _semantic_result(
    record_id: str = "concept:prorrata",
    *,
    score: float = 0.91,
    ranking_weight: float = 1.0,
) -> Rung2SemanticCandidateResult:
    return Rung2SemanticCandidateResult(
        query_tokens=("prorrata",),
        covered_token_count=1,
        candidates=(
            Rung2SemanticCandidate(
                record_id=record_id,
                semantic_score=score,
                semantic_ranking_weight=ranking_weight,
            ),
        ),
        status=Rung2CandidateStatus.CANDIDATES,
    )


def test_non_direct_card_pass_rows_do_not_displace_same_band_semantic_candidate() -> None:
    """Description-only legal/card hits yield to semantic cosine in one band."""
    lexical_candidates = (
        Rung2LexicalObservation(
            record_id="legal:prorrata",
            tier_rank=2.0,
            direct_match_strength=0,
            is_lexical_card=True,
            relevance_rank=0,
        ),
        Rung2LexicalObservation(
            record_id="casilla-record:303:001",
            tier_rank=1.8,
            direct_match_strength=0,
            is_lexical_card=True,
            relevance_rank=1,
        ),
    )

    result = compose_rung2_candidates(lexical_candidates, _semantic_result())

    assert tuple(entry.record_id for entry in result.entries) == (
        "concept:prorrata",
        "legal:prorrata",
        "casilla-record:303:001",
    )


def test_direct_lexical_identity_still_precedes_semantic_candidate() -> None:
    """An independently observed direct title/alias match remains first."""
    lexical_candidates = (
        Rung2LexicalObservation(
            record_id="casilla-record:303:001",
            tier_rank=1.8,
            direct_match_strength=3,
            is_lexical_card=True,
            relevance_rank=0,
        ),
    )

    result = compose_rung2_candidates(
        lexical_candidates,
        _semantic_result(score=0.99),
    )

    assert tuple(entry.record_id for entry in result.entries) == (
        "casilla-record:303:001",
        "concept:prorrata",
    )


def test_semantic_abstention_does_not_compose_supplied_candidates() -> None:
    """A validated abstention result contributes no semantic ladder rows."""
    semantic_result = Rung2SemanticCandidateResult(
        query_tokens=(),
        covered_token_count=0,
        candidates=(),
        status=Rung2CandidateStatus.EMPTY_QUERY,
    )

    result = compose_rung2_candidates(
        (
            Rung2LexicalObservation(
                record_id="legal:prorrata",
                tier_rank=1.0,
                direct_match_strength=0,
                is_lexical_card=True,
                relevance_rank=0,
            ),
        ),
        semantic_result,
    )

    assert result.semantic_status is Rung2CandidateStatus.EMPTY_QUERY
    assert tuple(entry.record_id for entry in result.entries) == ("legal:prorrata",)


def test_semantic_abstention_rejects_exposed_candidates() -> None:
    """An abstention status cannot expose rows for a later composition call."""
    with pytest.raises(ValidationError, match="abstention status"):
        Rung2SemanticCandidateResult(
            query_tokens=(),
            covered_token_count=0,
            candidates=(
                Rung2SemanticCandidate(
                    record_id="concept:prorrata",
                    semantic_score=0.99,
                    semantic_ranking_weight=1.0,
                ),
            ),
            status=Rung2CandidateStatus.EMPTY_QUERY,
        )


def test_lexical_ties_use_utf8_record_id_fallback() -> None:
    """Equal lexical rows have stable order independent of caller tuple order."""
    lexical_candidates = (
        Rung2LexicalObservation(
            record_id="legal:β",
            tier_rank=1.5,
            direct_match_strength=0,
            is_lexical_card=True,
            relevance_rank=0,
        ),
        Rung2LexicalObservation(
            record_id="legal:á",
            tier_rank=1.5,
            direct_match_strength=0,
            is_lexical_card=True,
            relevance_rank=0,
        ),
    )

    result = compose_rung2_candidates(
        lexical_candidates,
        Rung2SemanticCandidateResult(
            query_tokens=(),
            covered_token_count=0,
            candidates=(),
            status=Rung2CandidateStatus.EMPTY_QUERY,
        ),
    )

    assert tuple(entry.record_id for entry in result.entries) == (
        "legal:á",
        "legal:β",
    )


def test_lexical_relevance_precedes_utf8_tie_break() -> None:
    """Existing relevance order remains ahead of the canonical id fallback."""
    result = compose_rung2_candidates(
        (
            Rung2LexicalObservation(
                record_id="legal:á",
                tier_rank=1.5,
                direct_match_strength=0,
                is_lexical_card=True,
                relevance_rank=1,
            ),
            Rung2LexicalObservation(
                record_id="legal:β",
                tier_rank=1.5,
                direct_match_strength=0,
                is_lexical_card=True,
                relevance_rank=0,
            ),
        ),
        Rung2SemanticCandidateResult(
            query_tokens=(),
            covered_token_count=0,
            candidates=(),
            status=Rung2CandidateStatus.EMPTY_QUERY,
        ),
    )

    assert tuple(entry.record_id for entry in result.entries) == ("legal:β", "legal:á")


def test_evaluation_row_requires_hit_membership_and_reason() -> None:
    """A hit must be a matching expected/candidate id with the hit reason."""
    with pytest.raises(ValidationError, match="matched record id"):
        Rung2EvaluationRow(
            query="prorrata",
            concept_id="prorrata",
            expected_record_ids=("concept:prorrata",),
            candidate_record_ids=("concept:otra",),
            query_token_count=1,
            covered_token_count=1,
            hit=True,
            reason=Rung2EvaluationReason.HIT,
            matched_record_id="concept:prorrata",
        )


def test_evaluation_row_rejects_miss_with_expected_candidate_membership() -> None:
    """A row with expected/candidate membership cannot be reported as a miss."""
    with pytest.raises(ValidationError, match="must be a hit"):
        Rung2EvaluationRow(
            query="prorrata",
            concept_id="prorrata",
            expected_record_ids=("concept:prorrata",),
            candidate_record_ids=("concept:prorrata",),
            query_token_count=1,
            covered_token_count=1,
            hit=False,
            reason=Rung2EvaluationReason.TARGET_MISMATCH,
            matched_record_id=None,
        )


def test_evaluation_row_abstention_requires_empty_candidates() -> None:
    """An abstention reason cannot carry candidate membership into a row."""
    with pytest.raises(ValidationError, match="abstention row"):
        Rung2EvaluationRow(
            query="prorrata",
            concept_id="prorrata",
            expected_record_ids=("concept:prorrata",),
            candidate_record_ids=("concept:otra",),
            query_token_count=1,
            covered_token_count=0,
            hit=False,
            reason=Rung2EvaluationReason.INSUFFICIENT_COVERAGE,
            matched_record_id=None,
        )


def test_evaluation_aggregate_counts_derive_from_rows() -> None:
    """The aggregate cannot contradict the validated row arithmetic."""
    row = Rung2EvaluationRow(
        query="prorrata",
        concept_id="prorrata",
        expected_record_ids=("concept:prorrata",),
        candidate_record_ids=("concept:prorrata",),
        query_token_count=1,
        covered_token_count=1,
        hit=True,
        reason=Rung2EvaluationReason.HIT,
        matched_record_id="concept:prorrata",
    )

    with pytest.raises(ValidationError, match="hit count"):
        Rung2Evaluation(
            query_set_version=1,
            policy=Rung2EvaluationPolicy(
                minimum_coverage_ratio=0.8,
                cosine_floor=0.75,
                runner_up_margin=0.05,
                result_limit=5,
            ),
            case_count=1,
            hit_count=0,
            miss_count=1,
            held_out_miss_rate=1.0,
            rows=(row,),
        )
