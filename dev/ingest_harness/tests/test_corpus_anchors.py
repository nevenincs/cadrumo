"""Facts about the real corpus, anchored so a change fails a gate rather than a figure.

Every denominator here was re-derived directly from the pinned key before being
written down. They are asserted rather than trusted because stale counts (34
transcriptions, 8 twins, 26 vision-path, 36 category-scorable) reached a decided
record before anyone re-derived them, and prose cannot notice when it goes stale.

These carry the ``integration`` marker because they read an EXTERNAL, read-only
corpus that in-repo CI does not have. That is a lane, not a skip: the assertions
run wherever the corpus exists and fail honestly if it is present but changed.
Report collected-versus-deselected counts when quoting a run of this file.
"""

from __future__ import annotations

import json

import pytest

from .._caveats import SPANISH_OPTIMISM_BIAS_CAVEAT, normalise_whitespace
from .._colocation_ceiling import CeilingOutcome, colocation_ceiling
from .._key import CORPUS_ROOT, EXPECTED_KEY_BYTES, EXPECTED_KEY_SHA256, CorpusKey, CorpusKeyError, load_corpus_key
from .._reference_points import SONNET_4_6_REC_DOM_IMG_008, reference_points_with_key_context

pytestmark = [pytest.mark.integration, pytest.mark.hex_core]


@pytest.fixture(scope="module")
def key() -> CorpusKey:
    """The real pinned key. Read-only; nothing here writes to the corpus."""
    return load_corpus_key()


def test_the_pinned_key_is_the_one_every_figure_is_quoted_against(key: CorpusKey) -> None:
    """Hash and length together, so a truncated read fails as a length mismatch."""
    assert key.sha256 == EXPECTED_KEY_SHA256
    assert key.byte_length == EXPECTED_KEY_BYTES


def test_the_internal_schema_version_is_the_stale_value_and_is_not_an_identifier(key: CorpusKey) -> None:
    """Pins the reason the harness prints it only as a do-not-cite.

    If this ever changes, the field started tracking something and the guidance
    around it needs revisiting -- which is a review, not a silent adoption.
    """
    assert key.stale_schema_version == "1.0"


def test_a_key_that_is_not_the_pinned_one_is_refused(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """The pin is enforced before parsing, so an unpinned key reaches no derivation."""
    impostor = tmp_path / "GROUND_TRUTH.json"
    impostor.write_text('{"schema_version": "1.0", "documents": []}', encoding="utf-8")

    with pytest.raises(CorpusKeyError, match=r"(?i)pinned"):
        load_corpus_key(impostor)


def test_every_denominator_matches_the_value_measured_from_the_key(key: CorpusKey) -> None:
    """The corrected denominators, each re-derived rather than inherited."""
    counts = key.denominators

    assert counts.documents == 302
    assert (counts.generated, counts.acquired_real, counts.operator) == (30, 66, 206)
    assert counts.generated + counts.acquired_real + counts.operator == counts.documents
    assert counts.stage1_reference_text == 48
    assert counts.twin_pairs == 7
    assert counts.vision_path == 130
    assert counts.category_scorable == 59


def test_the_documents_without_authored_truth_are_a_corpus_wide_hazard(key: CorpusKey) -> None:
    """81 documents, not the nine a single incident happened to involve.

    Anchored because the size of the set decides how much of the corpus the
    emitted-versus-scored distinction is load-bearing for.
    """
    assert key.denominators.documents_without_authored_truth == 81
    assert key.denominators.fabrication_trap_slots == 1364


def test_the_naive_scorability_filter_would_lose_the_generated_set(key: CorpusKey) -> None:
    """Proves the trap is real on the REAL key, not only on a synthetic one.

    The scorable set is 59; reading the flag alone yields 29. Both numbers are
    plausible, which is what makes the mistake survivable without a gate.
    """
    assert len(key.category_scorable_ids) == 59

    generated_ids = {row.doc_id for row in key.documents if row.provenance_class.value == "generated"}
    flag_only = key.category_scorable_ids - generated_ids
    assert len(flag_only) == 29, "the explicitly-flagged subset"
    assert len(generated_ids & key.category_scorable_ids) == 30, "the intrinsic subset a flag lookup drops"


def test_the_control_document_is_two_entries_and_both_are_addressable(key: CorpusKey) -> None:
    """Any claim about the poisoned control must name WHICH entry it is about."""
    matching = [row.doc_id for row in key.documents if "COM-2026-0005" in row.doc_id]

    assert sorted(matching) == [
        "OP-PUR-COM-2026-0005_camera-photo",
        "OP-PUR-COM-2026-0005_layout-minimal",
    ]
    for doc_id in matching:
        assert key.document(doc_id).doc_id == doc_id


def test_every_twin_resolves_to_a_document_that_exists(key: CorpusKey) -> None:
    """The prose link is verified, so a reworded note fails rather than drops a pair."""
    known = {row.doc_id for row in key.documents}

    assert len(key.twin_pairs) == 7
    for pair in key.twin_pairs:
        assert pair.original_doc_id in known
        assert pair.twin_doc_id in known
        assert key.document(pair.twin_doc_id).is_vision_path, "a vision twin must reach the pipeline as pixels"


def test_the_optimism_bias_caveat_is_verbatim_from_the_corpus_gap_register() -> None:
    """The caveat text must still occur in the corpus's own file.

    A paraphrase would drift, and worse would let the harness soften the finding
    over time with nobody reviewing the softening. Whitespace is normalised on
    both sides because the source is hard-wrapped prose and the column width is
    not the property being pinned.
    """
    gaps = normalise_whitespace((CORPUS_ROOT / "GAPS.md").read_text(encoding="utf-8"))

    assert normalise_whitespace(SPANISH_OPTIMISM_BIAS_CAVEAT) in gaps


def test_the_reference_point_names_a_real_document_and_states_its_confounds(key: CorpusKey) -> None:
    """The upper reference is recorded with every condition that qualifies it."""
    document = key.document(SONNET_4_6_REC_DOM_IMG_008.doc_id)

    assert not SONNET_4_6_REC_DOM_IMG_008.model_tier.is_baseline_eligible
    assert document.is_spanish and document.is_vision_path
    joined = " ".join(SONNET_4_6_REC_DOM_IMG_008.caveats)
    assert "NOT A BASELINE" in joined
    assert "field-form contract" in joined, "the prompt/grounding confound must travel with the figure"


def test_the_reference_points_reported_denominator_is_not_the_keys_own(key: CorpusKey) -> None:
    """The '7 of 8' subset is not defined by the corpus, and the record says so.

    The key authors 20 non-null fields for this document plus 5 null-truth traps,
    so the reported denominator of 8 cannot be reconstructed from the key. This
    anchors the discrepancy rather than leaving it to be rediscovered.
    """
    document = key.document(SONNET_4_6_REC_DOM_IMG_008.doc_id)

    assert len(document.scorable_fields) == 20
    assert len(document.fabrication_trap_fields) == 5
    assert SONNET_4_6_REC_DOM_IMG_008.reported_denominator == 8
    assert SONNET_4_6_REC_DOM_IMG_008.reported_denominator != len(document.scorable_fields)
    assert "DENOMINATOR IS NOT THE KEY'S" in " ".join(SONNET_4_6_REC_DOM_IMG_008.caveats)


def test_the_reference_point_inherits_the_spanish_caveat_from_the_key(key: CorpusKey) -> None:
    """Its document is a Spanish photograph, so the optimism bias applies to it too."""
    ((point, document_caveats),) = reference_points_with_key_context(key)

    assert point is SONNET_4_6_REC_DOM_IMG_008
    assert SPANISH_OPTIMISM_BIAS_CAVEAT in document_caveats


def test_the_colocation_ceiling_is_measurable_and_every_failure_is_explained() -> None:
    """The party-attribution ceiling over the corpus, asserted as a property not a rate.

    Deliberately pins no figure. A tally encodes a moment: the day a
    stacked-header document is added the ceiling rises, and a gate asserting the
    current value would fail on an improvement. What must hold is that the
    measurement is possible at all -- a non-empty population, a non-empty
    denominator -- and that every document failing to partition does so for a
    cause the instrument actually MEASURED.

    ``UNPARTITIONED_FOR_ANOTHER_REASON`` exists to stay empty. A member means
    the shared-line reading has stopped explaining the corpus, and the figure
    must be re-derived before anyone quotes it again. Without that population a
    new cause would arrive silently, folded into a total that was already large
    enough that nobody would look twice.

    **This assertion is structurally unable to detect a broken instrument, and
    that is measured rather than suspected.** Mutating the partition to answer
    "never" leaves every population here unchanged, because nothing in the
    corpus partitions to begin with; mutating it to answer "always" moves every
    document into ``PARTITIONED`` and still satisfies every property asserted
    below, because none of them pins a rate. So a green here is a statement
    about explainability and non-vacuity ONLY. The claim that the instrument can
    tell a partitionable document from an unpartitionable one rests entirely on
    the controls in ``test_colocation_ceiling.py``, on the unit lane, which do
    red under both of those mutations. Read the two together or neither means
    much.
    """
    documents = json.loads((CORPUS_ROOT / "GROUND_TRUTH.json").read_text(encoding="utf-8"))["documents"]

    report = colocation_ceiling(documents)

    assert report.transcribed > 0, "no authored transcriptions; the measurement would be vacuous"
    assert report.testable > 0, "no document carries an authored anchor for both parties"
    assert report.by_outcome(CeilingOutcome.UNPARTITIONED_FOR_ANOTHER_REASON) == (), (
        "a document failed to partition for a cause this instrument does not measure; "
        "re-derive the ceiling before quoting it"
    )
    accounted = (
        report.partitioned
        + len(report.by_outcome(CeilingOutcome.ANCHORS_SHARE_A_LINE))
        + len(report.by_outcome(CeilingOutcome.ANCHOR_NOT_PRINTED))
    )
    assert accounted == report.testable, "the outcome populations do not account for the denominator"
