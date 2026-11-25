"""The grade screen demands a completeness manifest exactly when the build does.

A completeness manifest is the projection of the non-empty calculation
closure, so a revision with an empty closure can carry none. Read against the
compiled bundled registry; the planted defect strips the manifest from a real
closure-bearing revision.
"""

from __future__ import annotations

import pytest

from cadrumo.core.authority_grade import RegistryAuthorityGrade
from cadrumo.domain.calculations.registry.support_matrix import revision_capability_probe
from cadrumo.domain.calculations.registry.tests.authored_editions import authored_revisions, open_ended_revision

from ...compiler.authority import compiled_bundled_authority
from ..grade_earned import grade_findings

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("governed_fact_scope")]

_MANIFEST = "completeness_manifest"


def _manifest_findings(modelo_id: str, revision_id: str, *, strip_manifest: bool = False) -> list[str]:
    revision = compiled_bundled_authority().modelo(modelo_id).revisions[revision_id]
    if strip_manifest:
        revision = revision.model_copy(update={"completeness_manifest": None})
    return [f.kind for f in grade_findings(revision, modelo_id=modelo_id) if f.prerequisite == _MANIFEST]


def _closure_bearing_revision_ids(modelo_id: str, grade: RegistryAuthorityGrade) -> list[str]:
    """Return the authored revisions of a modelo declared at ``grade`` whose closure reaches calculation grade."""
    revisions = compiled_bundled_authority().modelo(modelo_id).revisions
    return [
        selection.id
        for selection in authored_revisions(modelo_id)
        if revisions[selection.id].effective_authority_grade is grade
        and revision_capability_probe(revisions[selection.id], modelo_id=modelo_id).calc_grade
    ]


@pytest.mark.parametrize(
    ("modelo_id", "grade"),
    [("222", RegistryAuthorityGrade.CALCULATION), ("390", RegistryAuthorityGrade.FILING)],
    ids=["calculation-revision", "filing-revision"],
)
def test_closure_bearing_revision_without_manifest_is_under_supported(
    modelo_id: str, grade: RegistryAuthorityGrade
) -> None:
    revision_ids = _closure_bearing_revision_ids(modelo_id, grade)
    assert revision_ids, f"modelo {modelo_id} has no closure-bearing {grade.value} revision to strip"
    for revision_id in revision_ids:
        assert _manifest_findings(modelo_id, revision_id, strip_manifest=True) == ["under_supported"], revision_id


def test_empty_closure_filing_revision_without_manifest_is_not_reported() -> None:
    revision_id = open_ended_revision("145").id
    revision = compiled_bundled_authority().modelo("145").revisions[revision_id]
    probe = revision_capability_probe(revision, modelo_id="145")
    assert not probe.calc_grade
    assert not probe.has_completeness_manifest
    assert _manifest_findings("145", revision_id) == []


def test_inherited_manifest_counts_as_present() -> None:
    # A revision that restates no manifest of its own inherits it by scope assertion.
    for selection in authored_revisions("222"):
        assert _manifest_findings("222", selection.id) == [], selection.id
