"""Held-out miss-rate gates for the compiled terminology relevance mapping."""

from __future__ import annotations

import pytest

from dev.docs.terminology._miss_rate import (
    DEFAULT_RUNG2_MISS_RATE_THRESHOLD,
    HeldOutCaseKind,
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


def test_case_kinds_partition_the_vocabulary_honestly() -> None:
    """Vocabulary cases are real vocabulary rows; out-of-sample cases are NOT.

    The close-review (2026-07-13 audit, SHARP-1) found the original all-
    vocabulary set made a miss impossible by construction. The kinds now
    partition honestly: a ``vocabulary`` case must be a shipped query row,
    and an ``out_of_sample`` case must NOT be one -- otherwise it is not
    held out and the gate is decorative again.
    """
    vocabulary = {(query.concept_id, query.query.casefold()) for query in enumerate_query_vocabulary()}
    query_set = load_held_out_query_set()

    bad_vocab = [
        (case.concept_id, case.query)
        for case in query_set.cases
        if case.kind is HeldOutCaseKind.VOCABULARY and (case.concept_id, case.query.casefold()) not in vocabulary
    ]
    assert not bad_vocab, f"vocabulary case(s) not in the shipped vocabulary: {bad_vocab}"

    leaked = [
        (case.concept_id, case.query)
        for case in query_set.cases
        if case.kind is HeldOutCaseKind.OUT_OF_SAMPLE and (case.concept_id, case.query.casefold()) in vocabulary
    ]
    assert not leaked, f"out-of-sample case(s) leaked into the vocabulary: {leaked}"

    kinds = {case.kind for case in query_set.cases}
    assert kinds == {HeldOutCaseKind.VOCABULARY, HeldOutCaseKind.OUT_OF_SAMPLE}, (
        "the held-out corpus must carry BOTH kinds; an all-vocabulary set "
        "cannot register a miss and an all-out-of-sample set loses the "
        "wrangling-regression signal"
    )


def test_held_out_miss_rate_measures_the_committed_relevance_mapping() -> None:
    """The evaluation is structurally sound; misses come only where possible.

    The close-review removed the zero-miss pinning: the corpus now contains
    genuine out-of-sample phrasings, so misses are a REAL measurement, never
    asserted away. What stays pinned is structure: the sweep is non-degraded,
    every vocabulary case hits (the concept-card seed plus top-five bound
    make a vocabulary miss a wrangling regression), the prorrata worked
    example still grounds legally, and any miss belongs to an out-of-sample
    case.
    """
    evaluation = evaluate_held_out_miss_rate()
    query_set = load_held_out_query_set()
    by_query = {row.query: row for row in evaluation.rows}
    kind_by_query = {case.query: case.kind for case in query_set.cases}

    assert evaluation.case_count == len(query_set.cases)
    assert evaluation.compiled_query_count == load_committed_relevance().query_count
    # The sweep is non-degraded: no transient retrieval failures were recorded.
    assert evaluation.compiled_failed_query_count == 0
    assert evaluation.compiled_targeted_query_count == evaluation.compiled_query_count
    # The prorrata worked example resolves to its real BOE legal grounding.
    assert by_query["regla de prorrata"].hit
    assert by_query["regla de prorrata"].matched_record_id in {
        "legal:ley-37-1992:art-104",
        "legal:ley-37-1992:art-102",
        "concept:prorrata-especial",
    }
    # A vocabulary-case miss means the wrangler dropped a curated surface.
    vocabulary_misses = [
        row for row in evaluation.rows if not row.hit and kind_by_query[row.query] is HeldOutCaseKind.VOCABULARY
    ]
    assert not vocabulary_misses, f"vocabulary regression: {[r.query for r in vocabulary_misses]}"
    assert not [row for row in evaluation.rows if row.reason is MissReason.NO_TARGETS]


def test_rung2_adjudication_is_consistent_with_the_ratified_gate() -> None:
    """The adjudication applies the RATIFIED threshold and follows the number.

    The gate does not pin the verdict (the close-review found the previous
    version asserted keep-deferred, which made the measurement decorative).
    It pins consistency: the default threshold IS the ratified ten percent,
    and the decision is exactly what the measured rate demands on either
    side of it.
    """
    evaluation = evaluate_held_out_miss_rate()
    adjudication = adjudicate_rung2(evaluation)

    assert adjudication.miss_rate_threshold == DEFAULT_RUNG2_MISS_RATE_THRESHOLD == 0.10
    assert evaluation.compiled_failed_query_count == 0
    assert adjudication.measured_miss_rate == evaluation.miss_rate
    expected = (
        Rung2Decision.IMPLEMENT_RUNG2
        if evaluation.miss_rate > adjudication.miss_rate_threshold
        else Rung2Decision.KEEP_DEFERRED
    )
    assert adjudication.decision is expected
