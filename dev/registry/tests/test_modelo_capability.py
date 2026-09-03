"""Real-behaviour tests for the modelo capability screen.

The census answers the question a reader of this registry asks first - which
modelos can this product actually calculate and file - so its rows must come
from the declarations rather than a maintained list, and its findings must be
provably absent for a modelo that is honestly not filed here.
"""

from __future__ import annotations

import pytest

from cadrumo.application.modelo.registry_discovery import registry_modelo_codes
from cadrumo.domain.calculations.registry.authority import ValidatedRegistryAuthority, bundled_authority

from ..analysis.modelo_capability import capability_census, screen_authority

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


@pytest.fixture(scope="module")
def authority() -> ValidatedRegistryAuthority:
    return bundled_authority()


@pytest.fixture(scope="module")
def modelo_ids() -> tuple[str, ...]:
    return tuple(sorted(str(code) for code in registry_modelo_codes()))


def test_a_censal_modelo_carrying_nothing_produces_no_finding(authority: ValidatedRegistryAuthority) -> None:
    """A modelo honestly not filed here is silent, not flagged.

    Modelo 036 is the censal alta/modificacion/baja, filed on AEAT's sede and
    producing no fichero here. It declares applicability grade and carries no
    layout, which is the correct and complete state for such a modelo. A screen
    that reported it would be demanding filing machinery from a modelo that is
    not a filing.
    """
    assert screen_authority(authority, ("036",)) == ()


def test_the_census_reads_every_revision_and_marks_which_ones_file(
    authority: ValidatedRegistryAuthority, modelo_ids: tuple[str, ...]
) -> None:
    """Every revision is described, and filing capability is a derived property, not a label."""
    census = capability_census(authority, modelo_ids)

    assert len(census) > len(modelo_ids), "each modelo contributes at least one revision"
    assert any(row.files_here for row in census), "some revision must reach filing grade with a layout"
    assert any(not row.files_here for row in census), "some revision must not"
    for row in census:
        assert row.files_here == (row.grade == "filing" and row.layouts > 0)


def test_a_filing_claim_with_no_layout_behind_it_is_reported(authority: ValidatedRegistryAuthority) -> None:
    """A revision claiming filing grade while declaring no export layout is caught.

    Constructed rather than taken from the corpus: the shipped registry has no
    such revision today, so without building one this condition would be gated
    by a screen that had never seen it.
    """
    definition = authority.modelo("100")
    revision_id, revision = next(iter(definition.revisions.items()))
    stripped = revision.model_copy(update={"export_layouts": ()})
    patched = definition.model_copy(update={"revisions": {**definition.revisions, revision_id: stripped}})

    rows = capability_census(_SingleModeloAuthority(patched), ("100",))
    finding_kinds = {finding.kind for finding in screen_authority(_SingleModeloAuthority(patched), ("100",))}

    assert any(row.revision == str(revision_id) and row.layouts == 0 for row in rows)
    assert "claims_filing_without_layout" in finding_kinds


class _SingleModeloAuthority:
    """The narrowest thing the census reads: one modelo lookup.

    The census calls exactly ``authority.modelo(id)``, so a defect is shown to
    be caught by handing it a real definition carrying a constructed change
    rather than by mutating the shipped registry the whole suite reads.
    """

    def __init__(self, definition) -> None:
        self._definition = definition

    def modelo(self, modelo_id: str):
        return self._definition


def test_a_tree_shipped_below_filing_grade_is_reported(authority: ValidatedRegistryAuthority) -> None:
    """Shipping filing bytes for a revision that declares it cannot file is caught.

    This occurs live: two revisions ship a committed generated export tree while
    declaring applicability grade. It is reported structurally rather than by
    reading the reviewer prose, because one of those revisions carries an
    attestation limiting itself to scheduling and applicability and describing a
    much smaller declaration than the one now shipped. That attestation is a
    person's signed statement and must not be rewritten to match the data, so
    the disagreement between the shipped tree and the declared grade is the only
    honest signal available.
    """
    findings = [
        item for item in screen_authority(authority, ("222", "185")) if item.kind == "tree_ships_below_filing_grade"
    ]

    assert {item.modelo for item in findings} == {"222", "185"}
    assert all("cannot file" in item.detail for item in findings)


def test_a_filing_grade_revision_with_a_tree_is_not_reported(authority: ValidatedRegistryAuthority) -> None:
    """The condition is the contradiction, not the tree.

    Modelo 303 ships trees across six filing-grade revisions, which is the
    intended state. A screen that reported those would be flagging the product
    working correctly, and its reader would learn to ignore the kind.
    """
    findings = [item for item in screen_authority(authority, ("303",)) if item.kind == "tree_ships_below_filing_grade"]

    assert findings == []


def test_a_revision_that_files_without_a_deadline_is_reported(authority: ValidatedRegistryAuthority) -> None:
    """Claiming a filing without saying when it is due is caught.

    Modelo 151's earlier revision reaches filing grade with a layout and declares
    no deadline window. A filer asks two things of a modelo - what to send and by
    when - and this revision answers only the first.
    """
    findings = [item for item in screen_authority(authority, ("151",)) if item.kind == "files_here_without_deadline"]

    assert [item.revision for item in findings] == ["2015-2022"]
    assert "when the filing is due" in findings[0].detail


def test_a_non_filing_revision_without_a_deadline_is_not_reported(authority: ValidatedRegistryAuthority) -> None:
    """Silence about a due date is the correct answer for a modelo not filed here.

    Twenty-two revisions declare no deadline window and sit below filing grade.
    Modelo 036 is one: its censal alta and baja are filed on AEAT's sede, so it
    has no due date of its own to declare. Reporting those would demand a
    deadline from modelos that have none, which is how a screen earns being
    ignored.
    """
    findings = [item for item in screen_authority(authority, ("036",)) if item.kind == "files_here_without_deadline"]

    assert findings == []


def test_a_filing_calculation_class_without_formulas_is_reported(authority: ValidatedRegistryAuthority) -> None:
    """A modelo that claims to compute its filing, with nothing that computes, is caught."""
    findings = [
        item for item in screen_authority(authority, ("349",)) if item.kind == "claims_calculation_without_formulas"
    ]

    assert [item.revision for item in findings] == ["2020-y-siguientes"]
    assert "nothing computes" in findings[0].detail


def test_an_informative_modelo_without_formulas_is_not_reported(authority: ValidatedRegistryAuthority) -> None:
    """A declaracion informativa is never asked for arithmetic it has no reason to do.

    Modelo 347 reports operations with third parties: it transmits data and
    computes no liability, so declaring no formula is its complete and correct
    state. Ten of the fourteen formula-less filing-grade revisions are this case,
    which is why the condition reads the modelo's declared calculation class
    rather than counting formulas alone.
    """
    findings = [
        item
        for item in screen_authority(authority, ("347", "184", "720"))
        if item.kind == "claims_calculation_without_formulas"
    ]

    assert findings == []


def test_the_two_deadline_conditions_never_both_fire_on_one_revision() -> None:
    """A revision missing every deadline window is reported once, not once per year.

    "No deadline window at all" and "no deadline window for some years of the
    declared window" are the same defect at two scales, and the undated-year
    computation returns every year when there are none. Without a precedence the
    two conditions both fire, which is the duplication this screen retired
    another condition for - and which they did, on modelos 151 and 165, until
    measured.
    """
    from cadrumo.domain.calculations.registry.authority import bundled_authority

    from ..analysis.corpus import bundled_modelo_ids
    from ..analysis.modelo_capability import screen_authority

    findings = screen_authority(bundled_authority(), bundled_modelo_ids())
    none_at_all = {(f.modelo, f.revision) for f in findings if f.kind == "files_here_without_deadline"}
    some_years = {(f.modelo, f.revision) for f in findings if f.kind == "files_here_for_years_it_cannot_date"}
    assert none_at_all and some_years, "one of the two conditions is empty, so this proves nothing"
    assert not (none_at_all & some_years)


def test_the_year_gap_condition_is_the_filing_grade_subset_of_the_temporal_screen() -> None:
    """This screen narrows the temporal screen's finding; it does not restate it.

    The temporal screen reports every revision whose closed window has undated
    years. This one reports those that can actually be filed, where being unable
    to date a year is a defect a filer meets. A strict subset is the evidence
    that it narrows rather than duplicates - a screen reporting the same set
    would be one fact under two names.
    """
    from cadrumo.domain.calculations.registry.authority import bundled_authority

    from ..analysis.corpus import bundled_modelo_ids
    from ..analysis.modelo_capability import screen_authority
    from ..analysis.temporal_site_agreement import screen_authority as temporal_screen

    authority = bundled_authority()
    modelo_ids = bundled_modelo_ids()
    theirs = {
        (f.modelo, f.revision)
        for f in temporal_screen(authority, modelo_ids)
        if f.kind == "window_year_without_deadline"
    }
    mine = {
        (f.modelo, f.revision)
        for f in screen_authority(authority, modelo_ids)
        if f.kind == "files_here_for_years_it_cannot_date"
    }
    assert mine < theirs, "the year-gap condition no longer narrows the temporal screen"


def test_the_undated_years_come_from_the_temporal_screen() -> None:
    """One computation, one home.

    Which years a revision serves is stated in three places the temporal screen
    reconciles. An earlier draft read the years back out of that screen's
    finding PROSE, which is a second implementation in disguise and would have
    returned nothing at all had the wording changed.
    """
    from cadrumo.domain.calculations.registry.authority import bundled_authority

    from ..analysis.corpus import bundled_modelo_ids
    from ..analysis.modelo_capability import capability_census
    from ..analysis.temporal_site_agreement import undated_window_years

    authority = bundled_authority()
    modelo_ids = bundled_modelo_ids()
    checked = 0
    for row in capability_census(authority, modelo_ids):
        revision = authority.modelo(row.modelo).revisions[row.revision]
        assert row.undated_window_years == undated_window_years(revision)
        checked += 1
    assert checked, "the census is empty, so this compared nothing"
