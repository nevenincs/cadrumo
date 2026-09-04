"""Real-behaviour tests for the manifest-uncited-reference screen.

The mirror of the provenance screen. Its condition has to separate a manifest
whose references are all cited from one declaring something nothing uses, and it
must read a different surface than its sibling or the two would measure the same
disagreement twice.
"""

from __future__ import annotations

import pytest

from cadrumo.domain.calculations.registry.authority import bundled_authority

from ..analysis.corpus import bundled_modelo_ids
from ..analysis.manifest_uncited_references import (
    KINDS,
    uncited_manifest_references,
)
from ..analysis.manifest_uncited_references import (
    screen_authority as uncited_screen,
)
from ..analysis.provenance_consistency import screen_authority as citing_screen

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_a_manifest_reference_no_child_cites_is_reported() -> None:
    """The condition, on the live corpus.

    A manifest and its children's citations describe the same revision's
    grounding, and neither contains the other. Screening only the children
    reported half a disagreement for as long as the sibling screen existed.
    """
    found = uncited_screen(bundled_authority(), bundled_modelo_ids())
    assert found, "the condition lost its live population"
    assert {item.ref_kind for item in found} == {"legal", "source"}
    assert {item.kind for item in found} == set(KINDS)
    for item in found:
        assert item.modelo and item.revision and item.reference


def test_a_manifest_whose_references_are_all_cited_reports_nothing() -> None:
    """No finding where the two surfaces agree.

    Most revisions are in this state, so a screen reporting every manifest
    reference rather than the uncited ones would bury the finding under the
    majority that is fine.
    """
    authority = bundled_authority()
    clean = [
        (modelo, revision)
        for modelo in bundled_modelo_ids()
        for revision in authority.modelo(modelo).revisions.values()
        if not uncited_manifest_references(revision, modelo_id=modelo)
    ]
    assert clean, "every revision carries an uncited manifest reference, so this proves nothing"


def test_this_screen_and_its_sibling_report_disjoint_populations() -> None:
    """One is cited-not-declared, the other declared-not-cited.

    They cannot overlap, and an overlap would mean one of them is reading the
    wrong surface. This screen deliberately ignores resolved export fields: a
    derived field's citations are copied from its template, so counting them
    would let a manifest reference look cited by a child that never declares it
    and would hide exactly the disagreement being measured.
    """
    authority = bundled_authority()
    modelo_ids = bundled_modelo_ids()
    cited_outside = {
        (item.modelo, item.revision, item.ref_kind, reference)
        for item in citing_screen(authority, modelo_ids)
        for reference in item.outside
    }
    uncited = {
        (item.modelo, item.revision, item.ref_kind, item.reference) for item in uncited_screen(authority, modelo_ids)
    }
    assert cited_outside, "the sibling screen reports nothing, so this proves nothing"
    assert uncited, "this screen reports nothing, so this proves nothing"
    assert not (cited_outside & uncited)


def test_a_reference_only_a_deadline_window_cites_is_not_uncited() -> None:
    """Deadline windows cite, and omitting them manufactures findings.

    The taxpayer calendar grounds a revision's due dates and no casilla, formula
    or binding would ever name it. Reading only those families reported it as a
    manifest reference nothing cites, in every revision that declares one - a
    hundred and four findings that were the screen's own blind spot rather than
    the corpus's state.
    """
    from cadrumo.domain.calculations.registry.authority import bundled_authority

    from ..analysis.corpus import bundled_modelo_ids
    from ..analysis.manifest_uncited_references import screen_authority as uncited

    authority = bundled_authority()
    reported = {(item.modelo, item.revision, item.reference) for item in uncited(authority, bundled_modelo_ids())}
    checked = 0
    for modelo in bundled_modelo_ids():
        for revision_id, revision in authority.modelo(modelo).revisions.items():
            for window in revision.deadline_windows:
                for reference in (*window.legal_refs, *window.source_refs):
                    checked += 1
                    assert (modelo, str(revision_id), str(reference)) not in reported
    assert checked, "no deadline window cites anything, so this proves nothing"
