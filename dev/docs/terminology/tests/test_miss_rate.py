"""Held-out miss-rate gates for the compiled terminology relevance mapping."""

from __future__ import annotations

import pytest

from dev.docs.terminology._miss_rate import (
    MissReason,
    Rung2Decision,
    adjudicate_rung2,
    evaluate_held_out_miss_rate,
    held_out_query_set_path,
    load_committed_relevance,
    load_held_out_query_set,
)
from dev.docs.terminology._sweep import enumerate_query_vocabulary

pytestmark = [pytest.mark.unit, pytest.mark.hex_core, pytest.mark.docs]


def test_held_out_query_set_is_a_curated_bundled_corpus() -> None:
    """The evaluator reads a committed held-out corpus, not inline test data."""
    query_set = load_held_out_query_set()

    assert held_out_query_set_path().is_file()
    assert query_set.version == 1
    assert len(query_set.cases) >= 5
    assert len({(case.concept_id, case.query.casefold()) for case in query_set.cases}) == len(query_set.cases)
    assert all(case.expected_record_ids for case in query_set.cases)
    assert all(case.source.strip() for case in query_set.cases)


def test_held_out_queries_are_compiled_vocabulary_cases() -> None:
    """Every held-out query is a real shipped query-vocabulary row."""
    vocabulary = {(query.concept_id, query.query.casefold()) for query in enumerate_query_vocabulary()}
    query_set = load_held_out_query_set()

    missing = [
        (case.concept_id, case.query)
        for case in query_set.cases
        if (case.concept_id, case.query.casefold()) not in vocabulary
    ]

    assert not missing, f"held-out case(s) not present in the shipped query vocabulary: {missing}"


def test_held_out_miss_rate_measures_the_committed_relevance_mapping() -> None:
    """Current committed data has one measured hit and honest targetless misses."""
    evaluation = evaluate_held_out_miss_rate()
    by_query = {row.query: row for row in evaluation.rows}

    assert evaluation.case_count == len(load_held_out_query_set().cases)
    assert evaluation.compiled_query_count == load_committed_relevance().query_count
    assert by_query["regla de prorrata"].hit
    assert by_query["regla de prorrata"].matched_record_id in {
        "legal:ley-37-1992:art-104",
        "legal:ley-37-1992:art-102",
        "concept:prorrata-especial",
    }
    assert evaluation.hit_count == 1
    assert evaluation.miss_count == 4
    assert evaluation.miss_rate == pytest.approx(0.8)
    assert {row.reason for row in evaluation.rows if not row.hit} == {MissReason.NO_TARGETS}


def test_rung2_adjudication_requires_relevance_refresh_before_embeddings() -> None:
    """A degraded sweep cannot be used as proof that static embeddings are needed."""
    evaluation = evaluate_held_out_miss_rate()
    adjudication = adjudicate_rung2(evaluation)

    assert evaluation.compiled_failed_query_count > 0
    assert adjudication.decision is Rung2Decision.REFRESH_RELEVANCE_FIRST
    assert adjudication.measured_miss_rate == evaluation.miss_rate
