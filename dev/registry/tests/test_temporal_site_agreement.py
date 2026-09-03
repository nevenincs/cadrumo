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


def test_a_selector_declaring_both_forms_is_reported(authority: ValidatedRegistryAuthority) -> None:
    """The dual-form condition is proven, because the corpus cannot prove it.

    A selector may say which years a revision serves as an explicit ``years``
    tuple or as a ``year_from``/``year_to`` bound. Carrying both states the same
    fact twice with no rule for which wins, which is this package's subject in
    one field. No shipped revision does it, so the condition reported nothing
    and was exercised by nothing - declared, silent, and unproven, which is
    indistinguishable from broken.

    Constructed from a real revision rather than a stub, so the screen sees the
    shape it would meet in the registry.
    """
    revision = authority.modelo("303").revisions["2025"]
    selector = revision.period_selector
    assert not selector.years, "the fixture revision must not already carry both forms"

    dual = revision.model_copy(
        update={"period_selector": selector.model_copy(update={"years": (2025,), "year_from": 2025})}
    )

    findings = site_agreement_findings(dual, modelo_id="303")
    dual_form = [finding for finding in findings if finding.kind == "selector_dual_form"]

    assert len(dual_form) == 1, "one constructed disagreement must yield one finding"
    assert dual_form[0].detail == "years=[2025] and year_from=2025"


def test_the_unmodified_revision_carries_no_dual_form(authority: ValidatedRegistryAuthority) -> None:
    """The silence is the corpus, not the screen.

    Paired with the constructed case above: together they say the condition can
    fire and does not, which is what makes a zero readable. Either alone leaves
    the reader unable to tell a clean registry from a dead check.
    """
    revision = authority.modelo("303").revisions["2025"]
    kinds = [finding.kind for finding in site_agreement_findings(revision, modelo_id="303")]
    assert "selector_dual_form" not in kinds


def test_a_year_between_two_revisions_is_reported_unserved() -> None:
    """The condition the coverage gate refuses, constructed.

    No modelo in the corpus has one, so the gate over the live registry proves
    the corpus clean and says nothing about the gate. This is what proves it
    would catch one.
    """
    from ..analysis.temporal_site_agreement import unserved_interior_years

    assert unserved_interior_years(((2020, 2021), (2023, 2024))) == (2022,)


def test_years_before_the_first_revision_are_not_a_gap() -> None:
    """The interior is measured from the earliest year served, not a fixed year.

    Modelo 322's revision named `2008-2022` serves 2022 alone. Measuring from a
    fixed origin would report fourteen missing years; measuring from the modelo's
    own earliest coverage reports none, which is correct - years before a modelo
    begins are outside the registry rather than missing from it.
    """
    from ..analysis.temporal_site_agreement import unserved_interior_years

    assert unserved_interior_years(((2022, 2022), (2023, 2023), (2024, 2025))) == ()


def test_an_open_ended_revision_creates_no_gap_to_a_horizon_nobody_declared() -> None:
    """An unclosed window is closed at the latest year any revision mentions."""
    from ..analysis.temporal_site_agreement import unserved_interior_years

    assert unserved_interior_years(((2020, 2021), (2022, None))) == ()
    # It still cannot paper over a real gap beneath it.
    assert unserved_interior_years(((2020, 2020), (2022, None))) == (2021,)


def test_a_modelo_with_no_closed_window_yields_nothing() -> None:
    """With no closed revision there is no span to find an interior of."""
    from ..analysis.temporal_site_agreement import unserved_interior_years

    assert unserved_interior_years(((2020, None),)) == ()
