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


def test_every_declared_year_level_site_resolves_on_the_live_schema() -> None:
    """The declared site list is checked against the schema, not trusted.

    A list of dotted paths kept beside a screen is worth exactly as much as the
    guarantee that each one still exists. Without this, a field renamed in the
    schema leaves the list naming a site that is gone, and the count it supports
    - how many places one temporal fact is restated - silently overstates by
    one while reading like a measurement.

    Resolved through the model definitions rather than an instance, so the check
    holds even for a field no shipped revision happens to populate.
    """
    import typing

    from cadrumo.domain.calculations.registry.schema import ModeloRevision

    from ..analysis.temporal_site_agreement import YEAR_LEVEL_TEMPORAL_SITES

    assert YEAR_LEVEL_TEMPORAL_SITES, "the site list is empty, so it measures nothing"
    for path in YEAR_LEVEL_TEMPORAL_SITES:
        model: object = ModeloRevision
        for segment in path.split("."):
            fields = getattr(model, "model_fields", None)
            assert fields is not None, f"{path}: {model} declares no fields"
            assert segment in fields, f"{path}: no field named {segment!r}"
            annotation = fields[segment].annotation
            args = typing.get_args(annotation)
            model = next((arg for arg in args if hasattr(arg, "model_fields")), annotation)


def test_the_site_list_excludes_the_within_year_deadline_dates() -> None:
    """The boundary is a year-level claim, and the exclusion is deliberate.

    A deadline window carries three date fields saying when in a year a filing
    is due. They are not further statements of which years the revision serves,
    so they cannot disagree with the window, and counting them would inflate the
    restatement measurement with facts that are not restatements.
    """
    from ..analysis.temporal_site_agreement import YEAR_LEVEL_TEMPORAL_SITES

    excluded = {"opens_on", "closes_on", "payment_cutoff_on"}
    named = {path.rsplit(".", 1)[-1] for path in YEAR_LEVEL_TEMPORAL_SITES}
    assert not (named & excluded), f"a within-year deadline date entered the year-level site list: {named & excluded}"
