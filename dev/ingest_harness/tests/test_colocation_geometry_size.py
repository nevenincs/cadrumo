"""Controls for the geometry sizing probe.

The sizing answers "would column-aware rendering let the resolver partition",
and that answer is only worth anything if the probe can produce BOTH answers.
A probe that always says yes would report a fix that does not exist, and one
that always says no would report an impossibility. Both are tested here on
synthetic word boxes, so the controls run without the external corpus.

The corpus-side figures live in ``test_corpus_anchors.py`` on the integration
lane, and they carry no rate: like the ceiling they measure, a tally would
encode a moment. **Which gate carries which claim:** these controls carry
DISCRIMINATION -- the probe distinguishes a partitionable rendering from an
unpartitionable one -- and the corpus assertion carries NON-VACUITY, that a
population exists to measure. Neither substitutes for the other, and a green on
the corpus side alone would be coverage-shaped and empty.
"""

from __future__ import annotations

import pytest

from .._colocation_geometry_size import (
    column_aware_rendering_partitions,
    geometry_payload_ratio,
    render_page_text,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _word(text: str, x0: float, top: float) -> dict[str, object]:
    return {"text": text, "x0": x0, "x1": x0 + 10.0 * len(text), "top": top}


# A two-column header as pdfplumber reports one: both party labels on the same
# baseline, at opposite ends of a 600pt page.
_TWO_COLUMN_WORDS = [
    _word("FACTURA", 40, 60),
    _word("EMISOR", 40, 100),
    _word("DESTINATARIO", 320, 100),
    _word("Iberia", 40, 120),
    _word("Lucia", 320, 120),
    _word("28901", 40, 140),
    _word("35001", 320, 140),
    _word("TOTAL", 40, 200),
]

# The same parties stacked down the page, which is the layout the resolver was
# designed against and which already partitions without any geometry.
_STACKED_WORDS = [
    _word("FACTURA", 40, 60),
    _word("EMISOR", 40, 100),
    _word("Iberia", 40, 120),
    _word("DESTINATARIO", 40, 160),
    _word("Lucia", 40, 180),
]


def test_column_aware_rendering_flips_a_two_column_header() -> None:
    """The measured claim: geometry consumed at render time is enough.

    Both renderings use the same words. Only the ORDER they are written out in
    differs, so a flip here cannot be attributed to anything but the column
    segmentation -- which is what makes this a sizing result rather than an
    anecdote.
    """
    size = column_aware_rendering_partitions(
        doc_id="TWO-COLUMN",
        words=_TWO_COLUMN_WORDS,
        page_width=600.0,
        supplier_label="EMISOR",
        customer_label="DESTINATARIO",
    )

    assert size.partitions_in_reading_order is False
    assert size.partitions_column_aware is True


def test_a_stacked_header_partitions_either_way() -> None:
    """The negative control: column-awareness must not be what makes it work.

    If the probe only ever reported True for the column-aware rendering, the
    result above would be a property of the probe. Here a layout that needs no
    segmentation partitions in BOTH renderings, so the flip above is the layout
    changing rather than the second branch always answering yes.
    """
    size = column_aware_rendering_partitions(
        doc_id="STACKED",
        words=_STACKED_WORDS,
        page_width=600.0,
        supplier_label="EMISOR",
        customer_label="DESTINATARIO",
    )

    assert size.partitions_in_reading_order is True
    assert size.partitions_column_aware is True


def test_reading_order_puts_both_labels_on_one_line_and_column_order_does_not() -> None:
    """The rendering itself, so the outcome above is explained rather than asserted.

    A test that only checked the two booleans could not tell a correct
    segmentation from a coincidence. This states the mechanism: today's
    rendering genuinely emits both labels on one line, and the column-aware one
    genuinely separates them.
    """
    flat = render_page_text(_TWO_COLUMN_WORDS, split_x=300.0, column_aware=False)
    columns = render_page_text(_TWO_COLUMN_WORDS, split_x=300.0, column_aware=True)

    assert "EMISOR DESTINATARIO" in flat
    assert "EMISOR DESTINATARIO" not in columns
    # Same words either way; a rendering that dropped one would partition for
    # the wrong reason.
    assert sorted(flat.split()) == sorted(columns.split())


def test_the_payload_ratio_is_a_floor_and_scales_with_word_count() -> None:
    """Geometry costs multiples of the text it accompanies, not a fraction of it.

    Asserted as a relation rather than a constant: the exact ratio is a property
    of the corpus and belongs in the record that quotes it, while "geometry is
    the larger payload" is the property that decides whether preserving it is
    worth a namespace bump on a FINANCIAL record.
    """
    text = "\n".join(str(word["text"]) for word in _TWO_COLUMN_WORDS)

    ratio = geometry_payload_ratio(_TWO_COLUMN_WORDS, text=text)

    assert ratio > 1.0, "geometry must be measured as larger than the text it annotates"
    # No words is not zero bytes: an empty box list still serializes as "[]".
    # Asserted as written rather than rounded down to nothing, because a
    # measurement that quietly reports zero for a real payload is the shape
    # this package exists to refuse -- small is not absent.
    assert 0.0 < geometry_payload_ratio([], text=text) < ratio
    assert geometry_payload_ratio(_TWO_COLUMN_WORDS, text="") == 0.0, "no text means no ratio, not a division error"
