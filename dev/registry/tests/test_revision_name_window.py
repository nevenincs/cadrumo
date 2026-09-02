"""Real-behaviour tests for the revision-name-against-declared-window screen.

Every test drives the bundled registry through the validated authority. The
detector cases mutate a copy of a real revision through the same typed model
the loader produces, so the working tree is never touched and no mock stands in
for the schema.
"""

from __future__ import annotations

import datetime

import pytest

from cadrumo.domain.calculations.registry.authority import ValidatedRegistryAuthority, bundled_authority

from ..analysis.revision_name_window import name_window_findings

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


@pytest.fixture(scope="module")
def authority() -> ValidatedRegistryAuthority:
    return bundled_authority()


def test_an_agreeing_name_reports_nothing(authority: ValidatedRegistryAuthority) -> None:
    """A revision whose name matches its declared window yields no finding."""
    revision = authority.modelo("303").revisions["2025"]
    assert name_window_findings(revision, modelo_id="303") == ()


def test_a_name_later_than_its_window_is_reported_apart_from_one_that_is_earlier(
    authority: ValidatedRegistryAuthority,
) -> None:
    """Modelo 151 names 2025 while declaring a window that opens in 2023.

    The direction is carried in the kind rather than left to the detail text,
    because the two directions want different corrections. A name later than its
    window understates the revision's reach - 151 serves filing years 2023 and
    2024 under a name claiming 2025 - while a name earlier than its window claims
    years the revision does not serve.
    """
    revision = authority.modelo("151").revisions["2025-y-siguientes"]
    findings = name_window_findings(revision, modelo_id="151")
    kinds = {finding.kind for finding in findings}
    assert "name_opens_after_window" in kinds
    assert "name_opens_before_window" not in kinds
    detail = next(item.detail for item in findings if item.kind == "name_opens_after_window")
    assert "2025" in detail
    assert "2023" in detail


def test_a_name_earlier_than_its_window_is_the_other_direction(
    authority: ValidatedRegistryAuthority,
) -> None:
    """Modelo 185 names 2025 while declaring a window that opens in 2026."""
    revision = authority.modelo("185").revisions["2025-y-siguientes"]
    kinds = {finding.kind for finding in name_window_findings(revision, modelo_id="185")}

    assert "name_opens_before_window" in kinds
    assert "name_opens_after_window" not in kinds


def test_a_name_without_a_year_is_reported_not_skipped(authority: ValidatedRegistryAuthority) -> None:
    """A revision slot holding a non-temporal axis surfaces rather than vanishing."""
    revision = authority.modelo("369").revisions["esquema-union"]
    findings = name_window_findings(revision, modelo_id="369")
    assert [finding.kind for finding in findings] == ["no_temporal_claim"]


def test_screen_detects_a_window_moved_away_from_its_name(authority: ValidatedRegistryAuthority) -> None:
    """Moving a clean revision's declared opening year makes its name a misstatement.

    This is the detector case: the defect is introduced on a copy, and a screen
    that read the name alone, or the window alone, could not see it.
    """
    revision = authority.modelo("303").revisions["2025"]
    assert name_window_findings(revision, modelo_id="303") == ()

    moved = revision.model_copy(update={"valid_from": datetime.date(2019, 1, 1)})
    findings = name_window_findings(moved, modelo_id="303")
    assert any(finding.kind == "name_opens_after_window" for finding in findings)


def test_screen_reports_disagreeing_window_sources(authority: ValidatedRegistryAuthority) -> None:
    """A valid_from and a period selector that disagree are reported in their own right.

    Neither source is preferred and neither silently wins; the disagreement is
    itself the finding, because a reader cannot tell which one the law meant.
    """
    revision = authority.modelo("303").revisions["2025"]
    selector = revision.period_selector

    moved = revision.model_copy(update={"valid_from": datetime.date(selector.year_from - 3, 1, 1)})
    kinds = {finding.kind for finding in name_window_findings(moved, modelo_id="303")}
    assert "window_sources_disagree" in kinds


def test_an_open_ended_window_its_selector_does_not_carry_is_reported(
    authority: ValidatedRegistryAuthority,
) -> None:
    """A revision reads as open-ended and selection stops at its named year.

    ``valid_to`` unset is how the corpus spells an open-ended window, and a
    reader takes it at face value. In this shape the selector carries neither
    bound, and selection does not extend: modelo 131's 2026 admits 2026 and
    refuses 2027, and the same holds for the other four instances.

    The condition is keyed on ``valid_to`` being unset rather than on the
    selector alone, and that distinction was established by measurement. Fifty
    revisions carry an empty selector beside an explicit ``valid_to``; their
    window is stated by the dates and they are correct, so reporting them would
    put fifty right declarations around five wrong ones.
    """
    revision = authority.modelo("131").revisions["2026"]
    kinds = {finding.kind for finding in name_window_findings(revision, modelo_id="131")}

    assert "open_ended_window_not_selectable" in kinds


def test_a_genuinely_open_ended_revision_carries_a_selector_opening_and_is_not_reported(
    authority: ValidatedRegistryAuthority,
) -> None:
    """The shape that really does serve later years must not be swept in.

    Modelo 721's 2024 declares no ``valid_to`` and a selector ``year_from``, and
    it admits filing year 2026 under a name saying 2024. That is a name
    understating its reach, which the single-year condition reports, and it is
    emphatically not an unselectable window.
    """
    revision = authority.modelo("721").revisions["2024"]
    kinds = {finding.kind for finding in name_window_findings(revision, modelo_id="721")}

    assert "open_ended_window_not_selectable" not in kinds


def test_an_explicit_closing_date_is_never_reported_as_unselectable(
    authority: ValidatedRegistryAuthority,
) -> None:
    """A revision whose window closes states its span in the dates, selector or not."""
    revision = authority.modelo("100").revisions["2025"]
    selector = revision.period_selector

    assert revision.valid_to is not None
    assert selector.year_from is None and selector.year_to is None
    kinds = {finding.kind for finding in name_window_findings(revision, modelo_id="100")}
    assert "open_ended_window_not_selectable" not in kinds


def test_an_unselectable_open_end_is_not_also_called_a_name_understating_its_reach(
    authority: ValidatedRegistryAuthority,
) -> None:
    """The two conditions overlap on the same field and must not both fire.

    A revision whose open-ended ``valid_to`` selection does not honour serves
    only its named year, so its single-year name is accurate. Reporting it as a
    name that omits years it serves would be the screen contradicting itself:
    one row saying the window does not extend, another saying the name fails to
    admit that it does.
    """
    revision = authority.modelo("131").revisions["2026"]
    kinds = {finding.kind for finding in name_window_findings(revision, modelo_id="131")}

    assert "open_ended_window_not_selectable" in kinds
    assert "name_claims_single_year" not in kinds


def test_a_selectable_open_end_still_reports_the_name_understating_its_reach(
    authority: ValidatedRegistryAuthority,
) -> None:
    """The exclusion is keyed on selectability, not on the name being one year.

    Modelo 721's 2024 is named for one year, runs open-ended, and admits filing
    year 2026. It must keep its finding, or the exclusion above would have
    silenced the condition rather than narrowed it.
    """
    revision = authority.modelo("721").revisions["2024"]
    kinds = {finding.kind for finding in name_window_findings(revision, modelo_id="721")}

    assert "name_claims_single_year" in kinds
    assert "open_ended_window_not_selectable" not in kinds
