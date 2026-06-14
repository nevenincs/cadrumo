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
    """The refreshed, non-degraded corpus resolves every held-out query.

    The committed mapping is now a complete, non-degraded sweep: zero failed
    queries, and every shipped query carries at least its originating concept
    card plus the RAG-discovered grounding surfaces. So every held-out case
    resolves -- the worked example ``regla de prorrata`` to its BOE legal
    article, the catalogued-term cases to their first-class concept card.
    """
    evaluation = evaluate_held_out_miss_rate()
    by_query = {row.query: row for row in evaluation.rows}

    assert evaluation.case_count == len(load_held_out_query_set().cases)
    assert evaluation.compiled_query_count == load_committed_relevance().query_count
    # The sweep is non-degraded: no transient retrieval failures were recorded.
    assert evaluation.compiled_failed_query_count == 0
    # Every shipped query resolved to at least one target (the concept-card seed
    # guarantees coverage; RAG adds the grounding surfaces).
    assert evaluation.compiled_targeted_query_count == evaluation.compiled_query_count
    # The prorrata worked example resolves to its real BOE legal grounding.
    assert by_query["regla de prorrata"].hit
    assert by_query["regla de prorrata"].matched_record_id in {
        "legal:ley-37-1992:art-104",
        "legal:ley-37-1992:art-102",
        "concept:prorrata-especial",
    }
    # No targetless misses remain on the complete corpus.
    assert evaluation.hit_count == evaluation.case_count
    assert evaluation.miss_count == 0
    assert evaluation.miss_rate == pytest.approx(0.0)
    assert not [row for row in evaluation.rows if row.reason is MissReason.NO_TARGETS]


def test_rung2_adjudication_keeps_static_embeddings_deferred() -> None:
    """A complete, non-degraded sweep keeps the static rung-2 matrix deferred.

    With zero failed queries the adjudicator stops demanding a refresh and
    measures honestly: the held-out miss-rate is within the accepted threshold,
    so the ~1-3 MB static term-embedding matrix (rung 2) stays deferred. The
    residual closed-vocabulary queries are served first-class by the concept
    card and four-language declared aliases (rung 1); rung 2's unique value --
    live embedding of UNCATALOGUED free text -- is not exercised by any
    held-out miss.
    """
    evaluation = evaluate_held_out_miss_rate()
    adjudication = adjudicate_rung2(evaluation)

    assert evaluation.compiled_failed_query_count == 0
    assert evaluation.miss_rate <= adjudication.miss_rate_threshold
    assert adjudication.decision is Rung2Decision.KEEP_DEFERRED
    assert adjudication.measured_miss_rate == evaluation.miss_rate
