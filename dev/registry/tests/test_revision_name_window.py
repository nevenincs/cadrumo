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

    Pinned to a live defect. The plan carries an open Step to rename this
    revision, and this test fails when that lands: the failure is the rename, not
    a regression. One other revision is in this state - modelo 720's
    2013-y-siguientes - and it carries a rename Step of its own, so it is not a
    successor: when the cluster lands the corpus holds no member of this kind at
    all. The replacement is therefore a constructed one, a real revision copied
    with its opening year moved, as the sibling conditions already do. Do not
    delete the test - the direction is the reason this condition exists apart
    from its opposite.
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
    """Modelo 185 names 2025 while declaring a window that opens in 2026.

    Pinned to a live defect, deliberately, and this note is what the pin owes.
    The plan carries an open Step to rename this revision; when that happens the
    window and the name will agree and this test will fail. That failure is the
    correction landing, not a regression.

    What must replace it: another revision whose name opens before its window,
    or - if none remains - a constructed one, as the closing-year and
    open-ended conditions beside it already use. Do not delete the test to make
    the rename green: the direction it distinguishes is the reason the condition
    was split from its opposite.

    Modelo 322's 2008-2022 is the only other revision in this state and it is
    stepped for rename as well, so no live successor survives the cluster; the
    replacement is constructed.
"""
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

    Pinned to a live defect with an open Step to close or rename it. When that
    lands this test fails. Modelo 194's 2024 is in the same state for the same
    reason, but it carries a rename Step too, so it is a companion rather than a
    successor. Both leave together, and the replacement is a constructed
    revision: a real one copied with its closing bound removed.
    """
    revision = authority.modelo("721").revisions["2024"]
    kinds = {finding.kind for finding in name_window_findings(revision, modelo_id="721")}

    assert "name_claims_single_year" in kinds
    assert "open_ended_window_not_selectable" not in kinds


def test_an_open_ended_name_over_a_closing_window_is_reported(
    authority: ValidatedRegistryAuthority,
) -> None:
    """A name promising every later year over a window that ends is caught.

    Constructed, and it has to be: the corpus contains no such revision, so this
    condition has never fired. A condition that has never fired is
    indistinguishable from one that cannot, and the screen documents eight
    conditions while emitting five.

    Built from modelo 151's open-ended revision by giving it a closing date, so
    the name still promises "y-siguientes" while the window stops in 2027.
    """
    revision = authority.modelo("151").revisions["2025-y-siguientes"]
    closed = revision.model_copy(update={"valid_to": datetime.date(2027, 12, 31)})

    kinds = {finding.kind for finding in name_window_findings(closed, modelo_id="151")}

    assert "name_claims_open_ended" in kinds


def test_a_name_closing_at_the_wrong_year_is_reported(
    authority: ValidatedRegistryAuthority,
) -> None:
    """A name stating a span whose closing year is not the declared one is caught.

    Also constructed, and the second of the two conditions the corpus never
    exercises. Modelo 151's ``2015-2022`` agrees with its window today; moving
    the window's close to 2021 leaves the name claiming a year the revision no
    longer serves.
    """
    revision = authority.modelo("151").revisions["2015-2022"]
    assert name_window_findings(revision, modelo_id="151") == ()

    moved = revision.model_copy(update={"valid_to": datetime.date(2021, 12, 31)})
    findings = name_window_findings(moved, modelo_id="151")

    assert "name_misstates_closing" in {finding.kind for finding in findings}
    detail = next(item.detail for item in findings if item.kind == "name_misstates_closing")
    assert "2022" in detail and "2021" in detail


def test_every_condition_the_screen_documents_is_declared_and_reachable(
    authority: ValidatedRegistryAuthority,
) -> None:
    """The documented conditions, the declared set, and what fires all agree.

    This once recovered the emitted set by matching the screen's source with
    four regexes, one per assignment shape the author had used. That is the
    static extraction the sibling gates refuse for a stated reason: it
    under-reads whatever shape it does not know, and an under-read set still
    compares equal to a docstring that happens to have lost the same entry, so
    the gate reports agreement between two wrong answers.

    The screen now declares its kinds. This compares the docstring against that
    declaration, and separately asserts what fires on the corpus is a subset of
    it. The conditions that do not fire are constructed by the tests above,
    which is why those exist and why this one constructs nothing.
    """
    import re

    from cadrumo.application.modelo.registry_discovery import registry_modelo_codes

    from ..analysis import revision_name_window as screen
    from ..analysis.revision_name_window import KINDS

    documented = set(re.findall(r"^- ``([a-z_]+)``", screen.__doc__ or "", re.M))

    assert documented, "the screen documents no conditions, so this gate proves nothing"
    assert documented == set(KINDS), (
        f"documented but not declared: {sorted(documented - set(KINDS))}; "
        f"declared but undocumented: {sorted(set(KINDS) - documented)}"
    )

    live = {
        finding.kind
        for modelo in sorted(str(code) for code in registry_modelo_codes())
        for revision in authority.modelo(modelo).revisions.values()
        for finding in name_window_findings(revision, modelo_id=modelo)
    }
    assert live, "no condition fired on the corpus, so the declaration is unexercised"
    assert live <= set(KINDS), f"the screen emitted a kind it does not declare: {sorted(live - set(KINDS))}"
