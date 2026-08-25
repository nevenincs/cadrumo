"""Neither the authority grade nor an informational casilla excuses a missing layout.

The filing-capability worklist lists every revision this application cannot
file. It is long, and two of its entries look like they could be argued away
rather than authored:

* Modelo 390's ``2021`` revision is ``authority_grade = "applicability"`` and
  its own review note says "filing layout authority is not claimed";
* its ten casillas are all ``input_kind = "informational"`` -- observation-only
  boxes an extractor reads out of a filed return.

Both readings suggest the same shortcut: that such a revision is a
declaration PARSER rather than a filing gap, so the worklist should stop
counting it. Both were measured, and both are wrong.

WHY THE GRADE CANNOT EXCUSE IT. Applicability-grade revisions split 21 WITH an
export layout against 14 without, and every filing-grade revision has one. The
grade is an EFFECT of carrying a layout, not a licence to omit it, so excusing
an entry by its grade is circular.

WHY THE CASILLA KIND CANNOT EITHER. Modelo 840's ``2003-y-siguientes`` revision
is all-informational too -- 121 of 121 -- and is a genuine filing gap the
worklist correctly reports as authorable. An all-informational casilla set is
therefore not a parser fingerprint.

This module holds no opinion about whether Modelo 390's 2021 layout should be
authored. It fixes only that the two cheap arguments for not authoring it do
not hold, so a later reader reaches for evidence instead.
"""

from __future__ import annotations

import pytest

from .. import bundled_authority

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_APPLICABILITY = "applicability"


def _revisions():
    for modelo in bundled_authority().modelos:
        for revision_id, revision in modelo.revisions.items():
            yield modelo.id, revision_id, revision


def _grade(revision) -> str:
    return str(getattr(revision, "authority_grade", "")).rsplit(".", 1)[-1].strip("'>\" ").lower()


def test_the_authority_grade_does_not_predict_carrying_a_layout() -> None:
    """Asserted as BOTH populations being non-empty, which is the whole point.

    A grade that predicted the layout would put every applicability-grade
    revision on one side, and excusing the worklist by grade would then be
    defensible. It does not.
    """
    with_layout = [
        f"{modelo}/{revision_id}"
        for modelo, revision_id, revision in _revisions()
        if _APPLICABILITY in _grade(revision) and revision.export_layouts
    ]
    without_layout = [
        f"{modelo}/{revision_id}"
        for modelo, revision_id, revision in _revisions()
        if _APPLICABILITY in _grade(revision) and not revision.export_layouts
    ]

    assert with_layout, "no applicability-grade revision carries a layout any more"
    assert without_layout, "no applicability-grade revision lacks a layout any more"


def test_every_revision_carrying_a_layout_is_not_thereby_filing_grade_only() -> None:
    """The converse half: the grade is not simply a relabelling of the layout.

    Stated so the module cannot be read as claiming the two are unrelated. They
    correlate -- a revision with no layout cannot be filing grade -- and that is
    exactly why the implication runs one way only.
    """
    filing_without_layout = [
        f"{modelo}/{revision_id}"
        for modelo, revision_id, revision in _revisions()
        if _grade(revision) == "filing" and not revision.export_layouts
    ]

    assert not filing_without_layout, filing_without_layout


def test_an_all_informational_casilla_set_is_not_a_parser_fingerprint() -> None:
    """Modelo 840 is the counterexample, and it is named because it is the load-bearing one.

    If it ever stopped being all-informational, the argument this module refutes
    would need re-measuring rather than assuming, so its absence fails here.
    """
    all_informational = {
        f"{modelo}/{revision_id}"
        for modelo, revision_id, revision in _revisions()
        if revision.casillas and all(str(getattr(c, "input_kind", "")) == "informational" for c in revision.casillas)
    }

    assert "840/2003-y-siguientes" in all_informational, sorted(all_informational)
    assert "390/2021" in all_informational, sorted(all_informational)

    modelo_840 = next(m for m in bundled_authority().modelos if m.id == "840")
    revision = modelo_840.revisions["2003-y-siguientes"]

    assert not revision.export_layouts, "modelo 840 now carries a layout, so it is no longer the counterexample"
    assert len(revision.casillas) > 100, len(revision.casillas)
