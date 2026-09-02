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
