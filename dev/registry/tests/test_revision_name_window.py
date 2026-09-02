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
from dev.registry.analysis.revision_name_window import name_window_findings

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


@pytest.fixture(scope="module")
def authority() -> ValidatedRegistryAuthority:
    return bundled_authority()


def test_an_agreeing_name_reports_nothing(authority: ValidatedRegistryAuthority) -> None:
    """A revision whose name matches its declared window yields no finding."""
    revision = authority.modelo("303").revisions["2025"]
    assert name_window_findings(revision, modelo_id="303") == ()


def test_a_misstated_opening_is_reported(authority: ValidatedRegistryAuthority) -> None:
    """Modelo 151 names 2025 while declaring a window that opens in 2023."""
    revision = authority.modelo("151").revisions["2025-y-siguientes"]
    findings = name_window_findings(revision, modelo_id="151")
    kinds = {finding.kind for finding in findings}
    assert "name_misstates_opening" in kinds
    detail = next(item.detail for item in findings if item.kind == "name_misstates_opening")
    assert "2025" in detail
    assert "2023" in detail


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
    assert any(finding.kind == "name_misstates_opening" for finding in findings)


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
