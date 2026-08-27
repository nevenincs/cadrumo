"""The per-cell filing-bound advisory is proven to bite under a warm load.

Declared support is a claim the corpus must back per cell: a bundled AEAT or BOE
artefact covering it, a revision declaring filing grade, and a revision that
law-resolves for it at all. The whole-corpus projection of unbacked cells has
existed for some time with no production consumer, which is the shape of a
safety net that was built and switched off.

This module covers the narrowed accessor a resolution can actually use, and it
measures it WARM: the bundled authority is process-wide and validated once, so
every assertion below runs with the persisted validation verdict already present
rather than on a first cold build where different code assembles the answer.

The advisory is never a refusal. A bounded cell still calculates and inspects;
what the operator loses is the assurance that the corpus fully backs it, and
refusing would remove the surface that reports exactly that.
"""

from __future__ import annotations

import pytest

from ..authority import bundled_authority

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _warm_authority() -> object:
    """Return the process-wide authority after it has already served a read."""
    authority = bundled_authority()
    # Force the validated projection before measuring, so nothing below is cold.
    assert authority.supported_filing_year_gaps is not None
    return authority


def test_the_gap_projection_is_not_empty_so_the_narrowing_is_measurable() -> None:
    """An empty projection would make every assertion here vacuous."""
    authority = _warm_authority()

    assert authority.supported_filing_year_gaps, (
        "the corpus reports no unbacked cells at all; the per-cell advisory cannot be shown to bite"
    )


def test_a_bounded_cell_reports_its_missing_prerequisite_under_a_warm_load() -> None:
    """The advisory fires for a cell the projection names, and says what is missing."""
    authority = _warm_authority()
    gap = authority.supported_filing_year_gaps[0]

    advisories = authority.filing_bound_advisories_for_cell(
        gap.modelo,
        filing_year=gap.filing_year,
        period=str(gap.period),
    )

    assert advisories, f"no advisory for a cell the projection names as gapped: {gap}"
    assert gap.missing_prerequisite in advisories[0]
    assert gap.modelo in advisories[0]
    assert str(gap.filing_year) in advisories[0]


def test_every_gapped_cell_the_projection_names_produces_an_advisory() -> None:
    """The narrowing loses no cell: what the projection reports, the accessor reports.

    Without this the accessor could match on one field and silently answer
    empty for most gapped cells while still passing the single-cell proof above.
    """
    authority = _warm_authority()

    silent = [
        gap
        for gap in authority.supported_filing_year_gaps
        if not authority.filing_bound_advisories_for_cell(
            gap.modelo,
            filing_year=gap.filing_year,
            period=str(gap.period),
        )
    ]

    assert silent == [], f"{len(silent)} gapped cell(s) produced no advisory, e.g. {silent[:3]}"


def test_a_cell_the_projection_does_not_name_stays_silent() -> None:
    """Anti-noise: the advisory must not fire on a cell the corpus fully backs.

    An advisory that fires on a backed cell trains operators to ignore it, which
    costs more than the advisory is worth.
    """
    authority = _warm_authority()
    named = {(gap.modelo, gap.filing_year, str(gap.period)) for gap in authority.supported_filing_year_gaps}
    unbounded = [cell for cell in (("303", 2025, "1T"), ("100", 2025, "0A")) if cell not in named]
    assert unbounded, "the sample cells are all gapped; pick cells the corpus backs to prove silence"

    for modelo_id, filing_year, period in unbounded:
        assert authority.filing_bound_advisories_for_cell(modelo_id, filing_year=filing_year, period=period) == (), (
            f"the advisory fired on {modelo_id} {filing_year} {period}, which the projection does not name"
        )


def test_the_advisory_never_raises_for_an_unknown_cell() -> None:
    """Advisory means advisory: an unknown coordinate yields silence, not an exception."""
    authority = _warm_authority()

    assert authority.filing_bound_advisories_for_cell("999", filing_year=1999, period="0A") == ()
