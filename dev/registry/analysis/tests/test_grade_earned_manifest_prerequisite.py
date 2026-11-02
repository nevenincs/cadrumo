"""The grade screen demands a completeness manifest exactly when the build does.

A completeness manifest is the projection of the non-empty calculation
closure, so a revision with an empty closure can carry none. Read against the
compiled bundled registry; the planted defect strips the manifest from a real
closure-bearing revision.
"""

from __future__ import annotations

import pytest

from cadrumo.domain.calculations.registry.support_matrix import revision_capability_probe

from ...compiler.authority import compiled_bundled_authority
from ..grade_earned import grade_findings

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("governed_fact_scope")]

_MANIFEST = "completeness_manifest"


def _manifest_findings(modelo_id: str, revision_id: str, *, strip_manifest: bool = False) -> list[str]:
    revision = compiled_bundled_authority().modelo(modelo_id).revisions[revision_id]
    if strip_manifest:
        revision = revision.model_copy(update={"completeness_manifest": None})
    return [f.kind for f in grade_findings(revision, modelo_id=modelo_id) if f.prerequisite == _MANIFEST]


def test_closure_bearing_calculation_revision_without_manifest_is_under_supported() -> None:
    revision = compiled_bundled_authority().modelo("222").revisions["2023"]
    assert revision_capability_probe(revision, modelo_id="222").calc_grade
    assert _manifest_findings("222", "2023", strip_manifest=True) == ["under_supported"]


def test_closure_bearing_filing_revision_without_manifest_is_under_supported() -> None:
    revision = compiled_bundled_authority().modelo("390").revisions["2023"]
    assert revision_capability_probe(revision, modelo_id="390").calc_grade
    assert _manifest_findings("390", "2023", strip_manifest=True) == ["under_supported"]


def test_empty_closure_filing_revision_without_manifest_is_not_reported() -> None:
    revision = compiled_bundled_authority().modelo("145").revisions["2012-01-31-y-siguientes"]
    probe = revision_capability_probe(revision, modelo_id="145")
    assert not probe.calc_grade
    assert not probe.has_completeness_manifest
    assert _manifest_findings("145", "2012-01-31-y-siguientes") == []


def test_inherited_manifest_counts_as_present() -> None:
    # 222/2024 restates no manifest of its own: it is inherited by scope assertion.
    assert _manifest_findings("222", "2024") == []
