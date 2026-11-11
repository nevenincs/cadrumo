"""The fact-year gate catches a fact track that answers some supported years and not others."""

from __future__ import annotations

from datetime import date

import pytest

from cadrumo.domain.calculations.registry.facts.schema import GovernedFact
from cadrumo.domain.calculations.registry.snapshot_globals import SupportedFilingYearsCatalogue

from ..fact_year_coverage_audit import (
    TrackView,
    render_fact_year_findings,
    track_findings,
    year_valued_findings,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

SUPPORT = SupportedFilingYearsCatalogue(horizon=date.today().year, floor=date.today().year - 3)
YEARS = SUPPORT.years


def _track(*windows: tuple[date, date | None], standing: bool = False) -> TrackView:
    return TrackView("fact.example", "scalar", "axis|selector", windows, standing)


def test_track_missing_the_first_supported_year_is_flagged() -> None:
    track = _track((date(YEARS[1], 1, 1), None))
    (finding,) = track_findings([track], YEARS)
    assert finding.missing_years == (YEARS[0],)
    assert finding.covered_years == YEARS[1:]


def test_track_closed_before_the_horizon_is_flagged() -> None:
    track = _track((date(YEARS[0], 1, 1), date(YEARS[1], 12, 31)))
    (finding,) = track_findings([track], YEARS)
    assert finding.missing_years == YEARS[2:]


def test_track_covering_every_supported_year_is_clean() -> None:
    track = _track((date(YEARS[0], 1, 1), date(YEARS[1], 12, 31)), (date(YEARS[2], 1, 1), None))
    assert track_findings([track], YEARS) == ()


def test_window_starting_mid_year_still_answers_that_year() -> None:
    track = _track((date(YEARS[0], 1, 1), date(YEARS[1], 6, 30)), (date(YEARS[1], 7, 1), None))
    assert track_findings([track], YEARS) == ()


def test_standing_rate_and_track_with_no_supported_year_are_not_flagged() -> None:
    standing = _track((date(YEARS[2], 1, 1), None), standing=True)
    beyond = _track((date(YEARS[-1] + 5, 1, 1), None))
    assert track_findings([standing, beyond], YEARS) == ()


def test_findings_render_with_fact_identity_and_missing_years() -> None:
    track = _track((date(YEARS[1], 1, 1), None))
    lines = render_fact_year_findings(track_findings([track], YEARS))
    assert lines[0].startswith("fact tracks answering some supported years")
    assert any("fact.example" in line and str(YEARS[0]) in line for line in lines)


def _scalar_fact(value: int, quoted: str | None) -> GovernedFact:
    citations = () if quoted is None else ({"source_ref": "example-source", "required_text": (quoted,)},)
    return GovernedFact.model_validate(
        {
            "fact_id": "fact.year-valued",
            "family": "scalar",
            "variants": (
                {
                    "variant_id": "fact.year-valued:v1",
                    "date_axis": "filing_period",
                    "legal_refs": ("ley:art-1",),
                    "source_refs": ("example-source",),
                    "review_status": "agent_reviewed",
                    "ownership": "authored",
                    "source_citations": citations,
                    "payload": {"kind": "scalar", "value": value, "unit": "filing_year"},
                },
            ),
        }
    )


def test_fact_whose_value_is_a_supported_year_is_flagged_unless_a_citation_quotes_it() -> None:
    year = YEARS[-1]
    (finding,) = year_valued_findings([_scalar_fact(year, "Variacion de existencias")], YEARS)
    assert (finding.fact_id, finding.value) == ("fact.year-valued", year)
    assert year_valued_findings([_scalar_fact(year, f"ejercicio {year}")], YEARS) == ()


def test_scalar_outside_the_supported_years_is_not_a_year_value() -> None:
    assert year_valued_findings([_scalar_fact(YEARS[0] - 50, None)], YEARS) == ()
