"""303 envelope per-segment cumulative layout lock.

A complementary guard to the "total envelope = 7994" check.
The total alone doesn't catch a segment reordering — swapping
DP30301 and DP30302 in the ENVELOPE tuple still sums to 7994 but
shifts where every casilla after the reshuffle lands, breaking
byte-exact compatibility with AEAT.

the exact (segment_id, cumulative_start_offset,
segment_length) triple for every segment in the 303 2024 envelope.
Any reordering, insertion, deletion, or segment-length change
fails here.
"""

from __future__ import annotations

import pytest

from .modelo_303_2024 import ENVELOPE

pytestmark = [pytest.mark.unit, pytest.mark.domain_outbound, pytest.mark.domain_export]


#: Canonical per-segment layout of the Modelo 303 2024 envelope.
#: Order: (segment_id, cumulative_start_offset, segment_total_length).
#: The cumulative_start_offset is the 0-indexed byte position where
#: the segment begins in the serialised payload (before CRLF).
_EXPECTED_303_2024_LAYOUT: list[tuple[str, int, int]] = [
    ("DP30300", 0, 328),
    ("DP30301", 328, 1581),
    ("DP30302", 1909, 1706),
    ("DP30303", 3615, 1017),
    ("DP30304", 4632, 998),
    ("DP30305", 5630, 1523),
    ("DP303DID", 7153, 823),
    ("DP30300_TRAILER", 7976, 18),
]


class TestEnvelopeSegmentLayout:
    def test_segment_count_locked(self) -> None:
        assert len(ENVELOPE) == len(_EXPECTED_303_2024_LAYOUT), (
            f"303 2024 envelope has {len(ENVELOPE)} segment(s); expected "
            f"{len(_EXPECTED_303_2024_LAYOUT)} per the canonical DR303 layout."
        )

    def test_each_segment_matches_expected_layout(self) -> None:
        cursor = 0
        for i, (seg, expected) in enumerate(zip(ENVELOPE, _EXPECTED_303_2024_LAYOUT, strict=True)):
            expected_id, expected_start, expected_length = expected
            assert seg.segment_id == expected_id, (
                f"ENVELOPE[{i}].segment_id = {seg.segment_id!r}; expected {expected_id!r}. "
                "Segment reorder or rename detected."
            )
            assert cursor == expected_start, (
                f"ENVELOPE[{i}] ({seg.segment_id}) starts at cumulative byte {cursor}; expected {expected_start}."
            )
            assert seg.total_length == expected_length, (
                f"ENVELOPE[{i}] ({seg.segment_id}).total_length = {seg.total_length}; expected {expected_length}."
            )
            cursor += seg.total_length

    def test_cumulative_sum_is_7994(self) -> None:
        """Sanity: the per-segment lengths sum to the envelope total (defence
        in depth — the already locks this, but a broken layout
        lock should fail BOTH together rather than diverge."""
        assert sum(s.total_length for s in ENVELOPE) == 7994

    def test_trailer_is_the_final_segment(self) -> None:
        """The ``</T303...>`` closing marker must be the last thing on the
        wire. A future insertion that puts something after DP30300_TRAILER
        would still satisfy "length = 7994" if compensating truncation
        happened elsewhere, but would break AEAT's parser expectations."""
        final = ENVELOPE[-1]
        assert final.segment_id == "DP30300_TRAILER", (
            f"Last envelope segment is {final.segment_id!r}; expected DP30300_TRAILER. "
            "The closing </T303...> marker must be the final on-wire segment."
        )

    def test_header_is_the_first_segment(self) -> None:
        """Mirror: the opening ``<T303...>`` header must be segment zero."""
        head = ENVELOPE[0]
        assert head.segment_id == "DP30300", (
            f"First envelope segment is {head.segment_id!r}; expected DP30300 (opening header)."
        )
