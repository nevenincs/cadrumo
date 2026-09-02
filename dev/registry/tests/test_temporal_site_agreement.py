"""Real-behaviour tests for the temporal declaration-site agreement screen.

Detector cases mutate a copy of a real revision through the typed model the
loader produces, so no mock stands in for the schema and the working tree is
never touched.
"""

from __future__ import annotations

import datetime

import pytest

from cadrumo.domain.calculations.registry.authority import ValidatedRegistryAuthority, bundled_authority

from ..analysis.temporal_site_agreement import site_agreement_findings

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


@pytest.fixture(scope="module")
def authority() -> ValidatedRegistryAuthority:
    return bundled_authority()


def test_an_agreeing_revision_reports_nothing(authority: ValidatedRegistryAuthority) -> None:
    """A revision whose sites agree yields no finding."""
    revision = authority.modelo("303").revisions["2025"]
    assert revision.deadline_windows, "the fixture revision must declare deadline windows"
    assert site_agreement_findings(revision, modelo_id="303") == ()


def test_a_revision_without_deadline_windows_is_reported(authority: ValidatedRegistryAuthority) -> None:
    """An absent deadline declaration surfaces as its own kind, not as a year gap."""
    revision = authority.modelo("840").revisions["2003-y-siguientes"]
    kinds = [finding.kind for finding in site_agreement_findings(revision, modelo_id="840")]
    assert kinds == ["no_deadline_windows"]


def test_screen_detects_a_deadline_year_outside_the_declared_window(
    authority: ValidatedRegistryAuthority,
) -> None:
    """Moving the window away from its deadline years surfaces the disagreement.

    This is the detector case for the condition the corpus does not currently
    exhibit: a screen that never sees the defect cannot be trusted to report it,
    so the defect is constructed on a copy.
    """
    revision = authority.modelo("303").revisions["2025"]
    moved = revision.model_copy(
        update={"valid_from": datetime.date(2030, 1, 1), "valid_to": datetime.date(2031, 12, 31)}
    )
    kinds = {finding.kind for finding in site_agreement_findings(moved, modelo_id="303")}
    assert "deadline_year_outside_window" in kinds


def test_open_ended_windows_are_not_measured_for_year_gaps(authority: ValidatedRegistryAuthority) -> None:
    """An open-ended window yields no gap finding, because it declares no end.

    Measuring it against an invented horizon would manufacture findings the
    declaration does not support, which is the failure this exclusion prevents.
    """
    revision = authority.modelo("303").revisions["2026-y-siguientes"]
    assert revision.valid_to is None
    kinds = {finding.kind for finding in site_agreement_findings(revision, modelo_id="303")}
    assert "window_year_without_deadline" not in kinds


def test_a_closed_window_missing_a_year_is_reported(authority: ValidatedRegistryAuthority) -> None:
    """A closed window with no deadline window for one of its years is a gap."""
    revision = authority.modelo("353").revisions["2021-2025"]
    findings = site_agreement_findings(revision, modelo_id="353")
    gaps = [finding for finding in findings if finding.kind == "window_year_without_deadline"]
    assert gaps
    assert "2021" in gaps[0].detail
