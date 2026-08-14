"""The scoring arm's own gate, and the proof that its zeros mean something.

A scorer that returns zeros for everything passes every green run silently and
reports a perfect abstention record for a model that invented on every slot. So
each counter carries an explicit proof that it CAN be non-zero, driven from a
recorded emission rather than a live model -- which also gives the S2 fabrication
measurement a gate that does not wait on a transport.

Every case scores against the real pinned corpus, because a scorer proven only
against a fixture the test author wrote is proven against that author's idea of
the corpus rather than the corpus.
"""

from __future__ import annotations

from typing import Any

import pytest

from .._key import CorpusDocument, CorpusKey
from .._result import HarnessRefusalError
from .._scoring import FieldVerdict, score_emission

pytestmark = [pytest.mark.integration, pytest.mark.hex_core]

#: One of the two entries the S2 baseline requires to surface findings. It is a
#: real corpus document with both a substantial scorable set and a substantial
#: trap set, which is exactly what a scorer needs to be exercised on.
_ANCHOR_DOC_ID = "OP-PUR-COM-2026-0005_layout-minimal"


@pytest.fixture
def anchor(key: CorpusKey) -> CorpusDocument:
    """The S2 anchor document."""
    return key.document(_ANCHOR_DOC_ID)


def _perfect_emission(document: CorpusDocument) -> dict[str, Any]:
    """The emission a flawless model would produce: every truth, no trap answered.

    Derived from the document's own truth rather than typed out, so it stays
    correct if the corpus changes and cannot encode the author's memory of it.
    """
    return {name: document.ground_truth[name] for name in document.scorable_fields}


# ----------------------------------------------------------------------------
# The anchor carries enough of both kinds of slot to exercise the arm at all
# ----------------------------------------------------------------------------


def test_the_anchor_document_still_carries_both_slot_kinds(anchor: CorpusDocument) -> None:
    """A rename or a truth edit must fail here rather than make the proofs vacuous.

    Every proof below asserts a non-zero count. If the anchor lost its traps, the
    fabrication proof would still pass while measuring nothing, so the population
    is pinned before it is used.
    """
    assert len(anchor.scorable_fields) == 19
    assert len(anchor.fabrication_trap_fields) == 10


def test_both_com_2026_0005_entries_can_surface_a_finding(key: CorpusKey) -> None:
    """The S2 baseline names two entries; neither may be trap-less."""
    entries = tuple(document for document in key.documents if "COM-2026-0005" in document.doc_id)
    assert len(entries) == 2
    for document in entries:
        assert document.fabrication_trap_fields, f"{document.doc_id} has no trap to fabricate into"
        assert document.scorable_fields, f"{document.doc_id} has no truth to score"


# ----------------------------------------------------------------------------
# Each counter proves it can be non-zero -- the three required proofs
# ----------------------------------------------------------------------------


def test_a_correct_value_produces_matched(anchor: CorpusDocument) -> None:
    """PROOF 1: matched is reachable, and reaches the document's full denominator."""
    scoring = score_emission(document=anchor, emitted=_perfect_emission(anchor))

    assert scoring.matched == 19
    assert scoring.wrong == 0
    assert scoring.missed == 0
    assert scoring.fabricated == 0
    assert scoring.correctly_abstained == 10


def test_a_wrong_value_produces_wrong(anchor: CorpusDocument) -> None:
    """PROOF 2: wrong is reachable, and does not leak into matched."""
    emission = _perfect_emission(anchor)
    emission["invoice_number"] = "NOT-THE-PRINTED-NUMBER"

    scoring = score_emission(document=anchor, emitted=emission)

    assert scoring.wrong == 1
    assert scoring.matched == 18
    assert scoring.fabricated == 0
    verdicts = {outcome.field_name: outcome.verdict for outcome in scoring.outcomes}
    assert verdicts["invoice_number"] is FieldVerdict.WRONG


def test_a_value_on_a_null_truth_slot_produces_fabricated(anchor: CorpusDocument) -> None:
    """PROOF 3: fabricated is reachable, and is counted apart from wrong."""
    trap = anchor.fabrication_trap_fields[0]
    emission = _perfect_emission(anchor)
    emission[trap] = "180.00"

    scoring = score_emission(document=anchor, emitted=emission)

    assert scoring.fabricated == 1
    assert scoring.fabricated_fields() == (trap,)
    assert scoring.correctly_abstained == 9
    assert scoring.wrong == 0, "fabrication must never be counted as a wrong answer"
    assert scoring.matched == 19, "fabrication must never reduce the scorable numerator"


def test_an_unanswered_scorable_slot_produces_missed(anchor: CorpusDocument) -> None:
    """The fourth verdict: truth existed and the model did not find it."""
    emission = _perfect_emission(anchor)
    del emission["base_total"]

    scoring = score_emission(document=anchor, emitted=emission)

    assert scoring.missed == 1
    assert scoring.matched == 18


def test_all_three_counters_are_non_zero_in_one_emission(anchor: CorpusDocument) -> None:
    """The counters are independent, not one number rendered three ways.

    Each proof above moves one counter alone; a scorer that simply mirrored its
    input would pass all three. Driving all three at once pins that they can hold
    different non-zero values simultaneously.
    """
    emission = _perfect_emission(anchor)
    emission["invoice_number"] = "WRONG"
    emission["currency"] = "USD"
    emission[anchor.fabrication_trap_fields[0]] = "1.00"
    del emission["base_total"]

    scoring = score_emission(document=anchor, emitted=emission)

    assert (scoring.matched, scoring.wrong, scoring.missed, scoring.fabricated) == (16, 2, 1, 1)
    assert scoring.scorable_field_count == 19


# ----------------------------------------------------------------------------
# Abstention is not fabrication
# ----------------------------------------------------------------------------


@pytest.mark.parametrize("sentinel", ["", "  ", "null", "N/A", "none", "-", "Unknown"])
def test_an_abstention_spelling_on_a_trap_is_not_a_fabrication(anchor: CorpusDocument, sentinel: str) -> None:
    """A model that says "not found" must not be scored as one that invented."""
    emission = _perfect_emission(anchor)
    emission[anchor.fabrication_trap_fields[0]] = sentinel

    scoring = score_emission(document=anchor, emitted=emission)

    assert scoring.fabricated == 0
    assert scoring.correctly_abstained == 10


def test_an_abstention_spelling_on_a_scorable_slot_is_a_miss_not_a_wrong_answer(anchor: CorpusDocument) -> None:
    """The same sentinel means the same thing on the other kind of slot."""
    emission = _perfect_emission(anchor)
    emission["base_total"] = "N/A"

    scoring = score_emission(document=anchor, emitted=emission)

    assert scoring.missed == 1
    assert scoring.wrong == 0


# ----------------------------------------------------------------------------
# Comparison rules, each dispatched from the truth's own shape
# ----------------------------------------------------------------------------


def test_an_amount_matches_within_the_documents_own_tolerance(anchor: CorpusDocument) -> None:
    """Tolerance comes from the key, and is applied in exact decimal."""
    assert anchor.tolerance_cents == 1
    emission = _perfect_emission(anchor)
    emission["base_total"] = "766.31"

    assert score_emission(document=anchor, emitted=emission).matched == 19


def test_an_amount_outside_the_tolerance_is_wrong(anchor: CorpusDocument) -> None:
    """The tolerance is a cent, not a licence."""
    emission = _perfect_emission(anchor)
    emission["base_total"] = "766.32"

    scoring = score_emission(document=anchor, emitted=emission)
    assert scoring.wrong == 1


def test_a_comma_decimal_is_scored_wrong_rather_than_coerced(anchor: CorpusDocument) -> None:
    """The documented strictness, pinned so it cannot soften unreviewed.

    This understates a model that reads correctly and formats in the Spanish
    convention. That is a deliberate choice -- form is pinned by the field-form
    contract, not here -- and it is asserted rather than left to the docstring.
    """
    emission = _perfect_emission(anchor)
    emission["base_total"] = "766,30"

    assert score_emission(document=anchor, emitted=emission).wrong == 1


def test_a_composite_field_is_one_slot_compared_structurally(anchor: CorpusDocument) -> None:
    """A nested leaf changing makes the whole declared field wrong, not a fraction."""
    emission = _perfect_emission(anchor)
    issuer = dict(emission["issuer"])
    issuer["tax_id"] = "B0000000Z"
    emission["issuer"] = issuer

    scoring = score_emission(document=anchor, emitted=emission)

    assert scoring.wrong == 1
    assert scoring.matched == 18


def test_a_boolean_truth_does_not_match_the_integer_one(anchor: CorpusDocument) -> None:
    """``True == 1`` in Python; it must not be true in a verdict."""
    assert anchor.ground_truth["line_count_exact"] is True
    emission = _perfect_emission(anchor)
    emission["line_count_exact"] = 1

    assert score_emission(document=anchor, emitted=emission).wrong == 1


# ----------------------------------------------------------------------------
# What the key does not declare is not scored as anything
# ----------------------------------------------------------------------------


def test_an_undeclared_emitted_field_is_reported_beside_the_counts_not_inside_them(
    anchor: CorpusDocument,
) -> None:
    """The key asserts nothing here, so neither may the scorer."""
    emission = _perfect_emission(anchor)
    emission["invented_field_the_key_never_mentions"] = "something"

    scoring = score_emission(document=anchor, emitted=emission)

    assert scoring.undeclared == ("invented_field_the_key_never_mentions",)
    assert scoring.fabricated == 0
    assert scoring.matched == 19
    assert scoring.scorable_field_count == 19


# ----------------------------------------------------------------------------
# Refusals
# ----------------------------------------------------------------------------


def test_scoring_a_document_with_no_authored_truth_is_refused(key: CorpusKey) -> None:
    """The 81 truth-less documents have no denominator; scoring them invents one."""
    truthless = next(document for document in key.documents if not document.has_authored_truth)

    with pytest.raises(HarnessRefusalError, match=r"(?i)no authored truth"):
        score_emission(document=truthless, emitted={"grand_total": "10.00"})


def test_the_projection_carries_fabrication_into_the_reportable_outcome(anchor: CorpusDocument) -> None:
    """``as_scored`` must not drop the count the whole measurement is about."""
    emission = _perfect_emission(anchor)
    emission[anchor.fabrication_trap_fields[0]] = "99.00"

    outcome = score_emission(document=anchor, emitted=emission).as_scored()

    assert outcome.fabricated == 1
    assert outcome.scorable_field_count == 19
    assert outcome.matched == 19
    assert outcome.missed == 0
