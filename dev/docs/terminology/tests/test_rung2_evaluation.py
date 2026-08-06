"""Real composition checks for the bounded Rung-2 browser ladder."""

from __future__ import annotations

import pytest

from dev.docs.terminology._rung2_evaluation import (
    Rung2CandidateStatus,
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
