"""The co-location ceiling: the instrument's controls, then the corpus figure.

These are the instrument's CONTROLS and they need no corpus, so they run
everywhere: an instrument never shown to discriminate turns a clean negative
into a fact about itself. The corpus-side assertion lives with the rest of this
package's external-corpus work in ``test_corpus_anchors.py``, on the
``integration`` lane, because the marker gate admits exactly one lane per test.

**Nothing here pins the ceiling as a number.** A tally encodes a moment: the
day a stacked-layout document is added the ceiling rises, and a gate asserting
zero would fail on an improvement. What is pinned is the PROPERTY -- that the
population is non-empty, that the instrument separates a partitionable document
from an unpartitionable one, and that every unpartitionable document carries a
MEASURED reason rather than a fall-through label. The figure itself belongs in
the record that quotes it beside the key hash it was scored against.
"""

from __future__ import annotations

import pytest

from cadrumo.application.ledger.party_colocation import party_regions

from .._colocation_ceiling import (
    CeilingOutcome,
    _draft,
    _transcription,
    colocation_ceiling,
    documents_with_authored_transcription,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

# A stacked header: each party's anchor on its own line. This is the layout the
# resolver was designed against, and the only shape known to clear the bar.
_STACKED = "\n".join(
    (
        "FACTURA",
        "EMISOR",
        "Suministros Iberia SA",
        "NIF A22633036",
        "DESTINATARIO / CLIENTE",
        "Lucia Fernandez Ortega",
        "NIF 45678912S",
        "TOTAL 815,16 EUR",
    ),
)

# The same two parties in a two-column header, as a reading-order text extractor
# emits it: both labels on one line, both names on the next.
_TWO_COLUMN = "\n".join(
    (
        "FACTURA",
        "EMISOR  DESTINATARIO / CLIENTE",
        "Suministros Iberia SA  Lucia Fernandez Ortega",
        "NIF A22633036  NIF 45678912S",
        "TOTAL 815,16 EUR",
    ),
)


def test_the_instrument_partitions_a_stacked_header() -> None:
    """The positive control. Without it a corpus-wide zero says nothing.

    A measurement that only ever reports "cannot partition" is indistinguishable
    from one whose partition call is broken, mis-wired or reading an empty
    transcription. This is the case that must come back TRUE for the corpus
    figure to carry any information at all.
    """
    regions = party_regions(
        draft=_draft("EMISOR", "DESTINATARIO / CLIENTE"),
        transcription=_transcription(_STACKED),
    )

    assert regions, "the instrument cannot partition even a stacked header"
    assert len(regions) == 2


def test_the_instrument_refuses_a_two_column_header() -> None:
    """The negative control, on the SAME two parties as the positive one.

    Holding the parties fixed and varying only the layout is what makes this a
    control rather than a second example: the difference in outcome can only be
    the line structure, which is the property the measurement claims to be
    sensitive to.
    """
    assert not party_regions(
        draft=_draft("EMISOR", "DESTINATARIO / CLIENTE"),
        transcription=_transcription(_TWO_COLUMN),
    )
    # And the names collapse the same way, so a reader quoting names instead of
    # labels is not a way around it.
    assert not party_regions(
        draft=_draft("Suministros Iberia SA", "Lucia Fernandez Ortega"),
        transcription=_transcription(_TWO_COLUMN),
    )


def test_a_document_with_no_authored_transcription_is_not_in_the_population() -> None:
    """An absent transcription yields no row, rather than a row scoring zero."""
    entries = [
        {"doc_id": "HAS-TEXT", "stage1_reference_text": _STACKED, "ground_truth": {}},
        {"doc_id": "NO-TEXT", "stage1_reference_text": "", "ground_truth": {}},
        {"doc_id": "NULL-TEXT", "stage1_reference_text": None, "ground_truth": {}},
    ]

    assert [entry["doc_id"] for entry in documents_with_authored_transcription(entries)] == ["HAS-TEXT"]


def test_a_shared_line_verdict_is_measured_rather_than_assumed() -> None:
    """The reason is derived from the line indices, not from the partition failing.

    Read off a failed partition, "both anchors were found, so they must share a
    line" is a fall-through that relabels every future cause as this one -- and
    a population that is 100 percent one reason, produced that way, is a fact
    about the instrument rather than about the corpus.
    """
    report = colocation_ceiling(
        [
            {
                "doc_id": "TWO-COLUMN",
                "stage1_reference_text": _TWO_COLUMN,
                "ground_truth": {"issuer": "Suministros Iberia SA", "counterparty_name": "Lucia Fernandez Ortega"},
            },
            {
                "doc_id": "STACKED",
                "stage1_reference_text": _STACKED,
                "ground_truth": {"issuer": "Suministros Iberia SA", "counterparty_name": "Lucia Fernandez Ortega"},
            },
            {
                "doc_id": "ABSENT-ANCHOR",
                "stage1_reference_text": "FACTURA\nTOTAL 10,00 EUR",
                "ground_truth": {"issuer": "Nobody SA", "counterparty_name": "Nobody Else SL"},
            },
            {
                "doc_id": "NO-TRUTH",
                "stage1_reference_text": "FACTURA\nTOTAL 10,00 EUR",
                "ground_truth": {},
            },
        ],
    )

    outcomes = {row.doc_id: row.outcome for row in report.rows}

    assert outcomes["TWO-COLUMN"] is CeilingOutcome.ANCHORS_SHARE_A_LINE
    assert outcomes["STACKED"] is CeilingOutcome.PARTITIONED
    assert outcomes["ABSENT-ANCHOR"] is CeilingOutcome.ANCHOR_NOT_PRINTED
    assert outcomes["NO-TRUTH"] is CeilingOutcome.NO_AUTHORED_ANCHORS
    # The four causes are genuinely distinguished, so a corpus-wide single
    # reason is a reading rather than the only value the code can produce.
    assert len(set(outcomes.values())) == 4


def test_the_undefined_population_is_excluded_from_the_denominator() -> None:
    """A document with no authored identity lowers no rate; it has none."""
    report = colocation_ceiling(
        [
            {
                "doc_id": "SCORABLE",
                "stage1_reference_text": _STACKED,
                "ground_truth": {"issuer": "Suministros Iberia SA", "counterparty_name": "Lucia Fernandez Ortega"},
            },
            {"doc_id": "UNDEFINED", "stage1_reference_text": "FACTURA\nTOTAL 10,00", "ground_truth": {}},
        ],
    )

    assert report.transcribed == 2
    assert report.testable == 1, "the undefined document must not sit in the denominator"
    assert report.partitioned == 1
