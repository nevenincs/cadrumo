"""Held-out miss-rate gates for the compiled terminology relevance mapping."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from .._miss_rate import (
    HeldOutCaseKind,
    HeldOutQueryCase,
    HeldOutQuerySet,
    MissRateEvaluation,
    MissRateRow,
    MissReason,
    evaluate_held_out_miss_rate,
    held_out_query_set_path,
    load_committed_relevance,
    load_held_out_query_set,
)
from .._sweep import enumerate_query_vocabulary

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


def test_the_relevance_artifact_records_no_failed_sweep_queries() -> None:
    """The committed mapping was produced by a clean sweep, not a degraded one.

    Kept from the retired rung-2 adjudication, which measured this on its way to
    a decision that no longer exists. The property still matters on its own: the
    mapping boosts LEXICAL results, and a mapping built from a sweep that failed
    queries is boosting on partial evidence.
    """
    evaluation = evaluate_held_out_miss_rate()

    assert evaluation.compiled_failed_query_count == 0


# ---------------------------------------------------------------------------
# The expected ids must name records production can actually emit
# ---------------------------------------------------------------------------
#
# ``expected_record_ids`` is the only place this corpus states WHAT a query
# should retrieve, and nothing joined it to the record space the search surface
# actually emits. The evaluator cannot: an id no projection can produce is
# indistinguishable, at the point of measurement, from a genuine retrieval
# failure -- it scores as ``target-mismatch`` and is counted into the miss
# rate, which is the figure the materiality line reads. So a fabricated or
# unshippable expectation does not fail; it silently argues for work.
#
# The two gates below close that. Existence catches a fabricated id outright.
# Satisfiability catches the subtler shape: a case whose every expectation
# names something the surface can never emit is unsatisfiable by construction,
# and its miss measures the corpus, not retrieval.


def _live_record_ids() -> tuple[frozenset[str], frozenset[str]]:
    """Return (every id production defines, the subset it can emit).

    Concept ids come from the same projection the search surface indexes; only
    APPROVED cards reach that surface, so the emittable subset is narrower than
    the defined one. Legal ids are composed from the production loader and the
    production id function -- the two halves ``project_legal_search_records``
    itself composes -- rather than from that projection directly, because it
    also builds a full search record and so carries failure modes unrelated to
    record identity.
    """
    from ...._paths import REPO_ROOT
    from ...legal_reference import load_legal_provisions
    from ...terminology_handbook.loader import load_terminology_handbook
    from ..concept_card_projection import project_concept_cards
    from ..legal_projection import legal_target_record_id
    from ..unified_record import to_search_record

    cards, _stats = project_concept_cards(load_terminology_handbook())
    defined = {to_search_record(card).id for card in cards}
    emittable = {to_search_record(card).id for card in cards if card.is_approved}
    legal = {legal_target_record_id(record.legal_id) for record in load_legal_provisions(REPO_ROOT)}
    return frozenset(defined | legal), frozenset(emittable | legal)


@pytest.fixture(scope="module")
def live_record_ids() -> tuple[frozenset[str], frozenset[str]]:
    """The live record-id space, derived once for every gate below."""
    return _live_record_ids()


def _undefined_expected_ids(query_set: HeldOutQuerySet, defined: frozenset[str]) -> list[str]:
    """Return every expected id naming no record production defines at all."""
    return sorted(
        {
            f"{case.query} -> {record_id}"
            for case in query_set.cases
            for record_id in case.expected_record_ids
            if record_id not in defined
        },
    )


def _unsatisfiable_cases(query_set: HeldOutQuerySet, emittable: frozenset[str]) -> list[str]:
    """Return every case no expectation of which the search surface can emit."""
    return sorted(
        f"{case.query} -> {sorted(case.expected_record_ids)}"
        for case in query_set.cases
        if not any(record_id in emittable for record_id in case.expected_record_ids)
    )


def test_every_expected_record_id_names_a_record_production_defines(
    live_record_ids: tuple[frozenset[str], frozenset[str]],
) -> None:
    """No expectation may name a record id no projection produces.

    A typo'd or invented id costs nothing at evaluation time and inflates the
    miss rate, so it argues for retrieval work the measurement never justified.
    """
    defined, _emittable = live_record_ids

    undefined = _undefined_expected_ids(load_held_out_query_set(), defined)

    assert not undefined, "held-out expectation(s) name no record production defines:\n" + "\n".join(
        f"  - {row}" for row in undefined
    )


def test_every_held_out_case_is_satisfiable_by_the_shipped_surface(
    live_record_ids: tuple[frozenset[str], frozenset[str]],
) -> None:
    """Every case must carry at least one expectation the surface can emit.

    A case whose expectations are all unshippable -- an unapproved concept
    card, say -- can never hit however good retrieval becomes. Its miss is a
    corpus fact wearing a retrieval fact's clothes.
    """
    _defined, emittable = live_record_ids

    unsatisfiable = _unsatisfiable_cases(load_held_out_query_set(), emittable)

    assert not unsatisfiable, "held-out case(s) no shipped surface can satisfy:\n" + "\n".join(
        f"  - {row}" for row in unsatisfiable
    )


def _synthetic_case(query: str, *expected: str) -> HeldOutQueryCase:
    """Build one synthetic held-out case for the detector-teeth gates."""
    return HeldOutQueryCase(
        query=query,
        concept_id="prorrata",
        expected_record_ids=tuple(expected),
        source="synthetic case built in this test to prove the join detects a defect",
        kind=HeldOutCaseKind.VOCABULARY,
    )


def _synthetic_query_set(*cases: HeldOutQueryCase) -> HeldOutQuerySet:
    """Wrap synthetic cases in a valid corpus, so only the join is under test."""
    return HeldOutQuerySet(
        version=1,
        description="synthetic held-out corpus built in this test; never committed",
        cases=cases,
    )


def test_the_existence_join_detects_a_fabricated_id_and_clears_a_real_one(
    live_record_ids: tuple[frozenset[str], frozenset[str]],
) -> None:
    """Teeth, both directions, over an isolated synthetic corpus.

    A join that never fires proves nothing, and one that always fires proves
    less. The clearing id is drawn from the live space, so the negative
    direction cannot pass by accident.
    """
    defined, _emittable = live_record_ids
    real = sorted(record_id for record_id in defined if record_id.startswith("concept:"))[0]

    fabricated = _undefined_expected_ids(
        _synthetic_query_set(_synthetic_case("q", "concept:no-such-concept-ever")),
        defined,
    )
    assert len(fabricated) == 1, fabricated
    assert "concept:no-such-concept-ever" in fabricated[0]

    assert not _undefined_expected_ids(_synthetic_query_set(_synthetic_case("q", real)), defined)


def test_the_satisfiability_join_detects_an_unshippable_case_and_clears_a_shippable_one(
    live_record_ids: tuple[frozenset[str], frozenset[str]],
) -> None:
    """Teeth, both directions, over the emittable subset.

    The positive control is a DEFINED-but-unemittable id -- the shape the
    existence gate above cannot see -- so the two gates are shown to catch
    different defects rather than the same one twice.
    """
    defined, emittable = live_record_ids
    unemittable = sorted(defined - emittable)
    assert unemittable, "no unapproved concept card exists, so this control cannot be built"

    caught = _unsatisfiable_cases(
        _synthetic_query_set(_synthetic_case("q", unemittable[0])),
        emittable,
    )
    assert len(caught) == 1, caught

    shippable = sorted(emittable)[0]
    assert not _unsatisfiable_cases(
        _synthetic_query_set(_synthetic_case("q", unemittable[0], shippable)),
        emittable,
    )


def _row(*, hit: bool) -> MissRateRow:
    return MissRateRow(
        query="prorrata",
        concept_id="prorrata",
        hit=hit,
        reason=MissReason.HIT if hit else MissReason.TARGET_MISMATCH,
        target_count=1 if hit else 0,
    )


def _evaluation(**overrides: object) -> MissRateEvaluation:
    fields: dict[str, object] = {
        "case_count": 2,
        "hit_count": 1,
        "miss_count": 1,
        "miss_rate": 0.5,
        "compiled_query_count": 2,
        "compiled_failed_query_count": 0,
        "compiled_targeted_query_count": 2,
        "rows": (_row(hit=True), _row(hit=False)),
    }
    fields.update(overrides)
    return MissRateEvaluation(**fields)  # type: ignore[arg-type]


def test_miss_rate_evaluation_refuses_a_contradictory_tally() -> None:
    """The record refuses count/row tallies that each pass their own validator.

    ``case_count`` is ``ge=1``, the tallies are ``ge=0`` and ``miss_rate`` is bounded
    to ``0..1``, so every field below is individually lawful; only the joint
    constraint distinguishes a measurement from a contradiction. Unenforced, the
    published miss rate can disagree with the very rows it summarises.
    """
    with pytest.raises(ValidationError, match="must equal the number of measured rows"):
        _evaluation(case_count=5)

    with pytest.raises(ValidationError, match="must partition case_count"):
        _evaluation(hit_count=0, miss_count=0, case_count=2, miss_rate=0.0)

    with pytest.raises(ValidationError, match="rows recorded as a hit"):
        _evaluation(hit_count=2, miss_count=0, miss_rate=0.0)

    with pytest.raises(ValidationError, match="miss_count divided by case_count"):
        _evaluation(miss_rate=0.0)


def test_miss_rate_evaluation_admits_every_consistent_tally() -> None:
    """Anti-noise: lawful tallies are admitted unchanged, at both rate extremes.

    The empty-parameter control is the smallest admissible evaluation -- the single
    row a ``min_length=1`` corpus permits -- at each extreme of ``miss_rate``. A gate
    that refused either would refuse a legitimate all-hit or all-miss run.
    """
    assert _evaluation().miss_rate == 0.5

    all_hit = _evaluation(case_count=1, hit_count=1, miss_count=0, miss_rate=0.0, rows=(_row(hit=True),))
    assert all_hit.miss_rate == 0.0

    all_miss = _evaluation(case_count=1, hit_count=0, miss_count=1, miss_rate=1.0, rows=(_row(hit=False),))
    assert all_miss.miss_rate == 1.0

    thirds = _evaluation(
        case_count=3,
        hit_count=2,
        miss_count=1,
        miss_rate=1 / 3,
        rows=(_row(hit=True), _row(hit=True), _row(hit=False)),
    )
    assert thirds.miss_count == 1
