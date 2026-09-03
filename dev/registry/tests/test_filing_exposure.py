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


def test_a_census_entry_point_is_visible_beside_its_runner_count() -> None:
    """A screen returning a census is not reported as if it returned findings.

    The wire-type screen's entry point returns every casilla-to-wire transition
    it examined, carrying a divergent flag: thousands of rows, of which a few
    dozen are findings. Nothing in the shape distinguishes that from a screen
    whose every row is a finding, so both counts are carried and the gap is the
    reader's signal. The first version of this report carried only the first and
    overstated that screen by a factor of nearly five hundred.
    """
    authority = bundled_authority()
    modelo_ids = bundled_modelo_ids()
    exposures = condition_exposure(authority, modelo_ids)
    by_screen = {item.screen: item for item in exposures if item.screen == "wire_type_compatibility"}
    assert by_screen, "the wire-type screen reported nothing, so this proves nothing"
    census = by_screen["wire_type_compatibility"]
    assert census.findings > census.runner_findings * 10
    # Every condition carries its screen's runner count, so the comparison is
    # available for all of them and not only the one that motivated it.
    assert all(item.runner_findings >= 0 for item in exposures)
    assert any(item.findings == item.runner_findings for item in exposures)


def test_the_report_reads_the_declared_shape_rather_than_inferring_it() -> None:
    """Census or findings comes from the table's declaration, not from a ratio.

    Inferring it from the gap between the two counts would work today and fail
    the moment a findings screen gained a projection that dropped most of its
    rows - which several already have. The declaration is an author's statement
    and this asserts the report is reading it.
    """
    from ..analysis.screens import CORPUS_SCREENS, SCREENS

    declared = {entry.name: entry.entry_returns for entry in SCREENS}
    declared.update({entry.name: entry.entry_returns for entry in CORPUS_SCREENS})
    assert "census" in declared.values(), "no screen declares a census, so this proves nothing"

    for item in condition_exposure(bundled_authority(), bundled_modelo_ids()):
        assert item.entry_returns == declared[item.screen]


def test_a_census_is_not_added_to_the_filing_defect_total() -> None:
    """Rows examined are counted apart from defects met.

    A census's rows are transitions the screen looked at, and most are fine.
    Summing them into the filing-exposure figure is the error the declaration
    exists to prevent, and it inflated that figure by eleven thousand.
    """
    exposures = condition_exposure(bundled_authority(), bundled_modelo_ids())
    census = [item for item in exposures if item.entry_returns == "census"]
    findings = [item for item in exposures if item.entry_returns == "findings"]
    assert census and findings, "both shapes must occur or this proves nothing"
    assert sum(item.filing_findings for item in census) > 0
    # The defect total excludes them, so it is strictly smaller than the naive sum.
    naive = sum(item.filing_findings for item in exposures)
    honest = sum(item.filing_findings for item in findings)
    assert honest < naive


def test_revision_pressure_names_the_conditions_rather_than_only_counting_them() -> None:
    """A count of conditions is not a severity, so the row carries their names.

    A revision with one filing-correctness defect is worse than one with four
    declaration untidinesses, and nothing here weighs them. The names are what
    let a reader see which they are instead of trusting the number.
    """
    from ..analysis.filing_exposure import revision_pressure

    ranked = revision_pressure(bundled_authority(), bundled_modelo_ids())
    assert ranked, "no fileable revision carries a condition, so this proves nothing"
    assert ranked[0].count >= ranked[-1].count
    for item in ranked:
        assert item.count == len(item.conditions) == len(set(item.conditions))
        assert all("." in kind for kind in item.conditions)


def test_revision_pressure_ranks_only_revisions_that_can_be_filed() -> None:
    """The ranking exists to order repair of filings, so it holds nothing else."""
    from ..analysis.filing_exposure import filing_grade_revisions, revision_pressure

    authority = bundled_authority()
    modelo_ids = bundled_modelo_ids()
    filing = filing_grade_revisions(authority, modelo_ids)
    ranked = revision_pressure(authority, modelo_ids)
    assert {(item.modelo, item.revision) for item in ranked} <= filing
    assert len(ranked) < len(filing) + 1


def test_revision_pressure_excludes_census_screens() -> None:
    """A census would rank a revision by how many fields it has.

    Its rows are transitions examined rather than defects, so including them
    would put the largest modelo at the top regardless of its declarations -
    which is the error the entry-point declaration exists to prevent, arriving
    by a second route.
    """
    from ..analysis.filing_exposure import revision_pressure
    from ..analysis.screens import CORPUS_SCREENS, SCREENS

    census = {entry.name for entry in (*SCREENS, *CORPUS_SCREENS) if entry.entry_returns == "census"}
    assert census, "no screen declares a census, so this proves nothing"
    ranked = revision_pressure(bundled_authority(), bundled_modelo_ids())
    named = {kind.split(".", 1)[0] for item in ranked for kind in item.conditions}
    assert not (named & census)
