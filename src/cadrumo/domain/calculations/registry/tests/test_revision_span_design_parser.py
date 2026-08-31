"""Tests for revision-span design parser coverage."""

from __future__ import annotations

import pytest

from ._revision_span_design_support import (
    _claimed_years,
    _designs_for,
    _filing_revisions,
    _page_lengths_for,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_the_design_parser_reads_every_markdown_design_it_claims() -> None:
    """A design that parses to nothing must fail, never pass by silence.

    This is the gate's anti-vacuity guard and its most likely rot path. If the
    extraction shape changes, or a regex stops matching, every comparison below
    would run over an empty table and agree trivially. An unreadable design is
    reported as UNMEASURED here rather than quietly dropped, because a parser
    that cannot read a format returns the same answer as a format with no
    divergence.
    """
    blind_spots: list[str] = []
    measured = 0
    for modelo, revision_id, revision in _filing_revisions():
        designs, unreadable = _designs_for(modelo.id)
        measured += len(designs)
        if not unreadable:
            continue
        # Only a design INSIDE a gated revision's span can hide a divergence from
        # this gate. One outside every span is a corpus file nothing compares,
        # so failing on it would be noise about the extractor rather than about
        # coverage.
        # A year is only a blind spot when BOTH signals are blind. A design that
        # yields no bracketed boxes but does publish its per-page lengths is
        # still measured by the page-length check below, so reporting it here
        # would overstate the gap.
        page_lengths = _page_lengths_for(modelo.id)
        opaque = {year for year in unreadable if year not in page_lengths}
        in_span = _claimed_years(revision, opaque)
        blind_spots.extend(
            f"modelo {modelo.id} revision {revision_id!r} claims {year}, but its design "
            f"{unreadable[year]!r} yields neither box offsets nor page lengths"
            for year in sorted(in_span)
        )
    assert measured, "no bundled design parsed at all; the extractor or the corpus path has moved"
    assert not blind_spots, (
        "these years are UNMEASURED rather than clean -- the gate cannot see a re-layout there, "
        "so its silence about them means nothing:\n  " + "\n  ".join(sorted(set(blind_spots)))
    )
