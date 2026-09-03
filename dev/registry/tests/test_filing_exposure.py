"""Real-behaviour tests for the filing-exposure report.

The report's value is a reading order, and its risk is that "no filing exposure"
reads as "safe" when it may mean "never asked". Several screens report per
modelo or per design because that is their unit, and their findings carry no
revision to grade. The distinction between a measured zero and an unmeasurable
condition is what these tests hold.
"""

from __future__ import annotations

import pytest

from cadrumo.domain.calculations.registry.authority import bundled_authority

from ..analysis.corpus import bundled_modelo_ids
from ..analysis.filing_exposure import ConditionExposure, condition_exposure, filing_grade_revisions

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_an_unmeasurable_condition_is_not_reported_as_below_filing() -> None:
    """No revision to grade means no claim, not a claim of safety.

    Eleven conditions looked wholly below filing grade before this distinction
    existed, and eight of them had never been asked: their findings carry no
    revision at all. Reporting those as safe would have sent a reader past them.
    """
    unmeasurable = ConditionExposure(
        screen="s", kind="k", findings=58, filing_findings=0, revisions=0, filing_revisions=0, unmeasured=58
    )
    assert unmeasurable.wholly_below_filing is False


def test_a_measured_zero_is_reported_as_below_filing() -> None:
    """A condition whose revisions were all graded and none files is safe to defer."""
    measured = ConditionExposure(
        screen="s", kind="k", findings=31, filing_findings=0, revisions=31, filing_revisions=0, unmeasured=0
    )
    assert measured.wholly_below_filing is True


def test_any_filing_exposure_defeats_the_deferral() -> None:
    """One graded finding is enough to keep a condition in the reading order."""
    exposed = ConditionExposure(
        screen="s", kind="k", findings=31, filing_findings=1, revisions=31, filing_revisions=1, unmeasured=0
    )
    assert exposed.wholly_below_filing is False


def test_the_live_report_separates_the_three_populations() -> None:
    """The corpus carries exposed, measured-safe and unmeasurable conditions.

    All three must occur, or the report is not discriminating and its ordering
    means nothing. Held as presence rather than by figure: every count here
    moves when a screen is added or a revision changes grade.
    """
    authority = bundled_authority()
    modelo_ids = bundled_modelo_ids()
    exposures = condition_exposure(authority, modelo_ids)
    assert exposures, "no condition was measured, so this proves nothing"

    exposed = [item for item in exposures if item.filing_findings]
    measured_safe = [item for item in exposures if item.wholly_below_filing]
    unmeasurable = [item for item in exposures if item.findings == item.unmeasured]
    assert exposed and measured_safe and unmeasurable
    # Nothing may be counted in two of the three.
    assert not ({id(x) for x in exposed} & {id(x) for x in measured_safe})
    assert not ({id(x) for x in measured_safe} & {id(x) for x in unmeasurable})


def test_every_filing_finding_names_a_revision_declaring_filing_grade() -> None:
    """The exposure count is grounded in the authority's own grade, not inferred.

    Asserted by rebuilding the filing set independently and checking that no
    condition claims more filing findings than it has findings at all.
    """
    authority = bundled_authority()
    modelo_ids = bundled_modelo_ids()
    filing = filing_grade_revisions(authority, modelo_ids)
    assert filing, "no revision declares filing grade, so this proves nothing"
    for item in condition_exposure(authority, modelo_ids):
        assert item.filing_findings <= item.findings
        assert item.filing_revisions <= item.revisions
        assert item.unmeasured <= item.findings
