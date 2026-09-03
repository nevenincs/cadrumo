"""Real-behaviour tests for the capability continuity screen.

The screen's whole value is separating a capability a revision DROPPED from one
it deliberately renounced by declaring less authority. Both occur in the corpus,
one apiece, and confusing them would make a stub read like a regression.
"""

from __future__ import annotations

import pytest

from cadrumo.domain.calculations.registry.authority import bundled_authority

from ..analysis.capability_continuity import (
    GRADE_LADDER,
    KINDS,
    declared_capabilities,
    modelo_findings,
    screen_authority,
)
from ..analysis.corpus import bundled_modelo_ids

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_a_capability_lost_while_the_grade_holds_is_a_regression() -> None:
    """Modelo 322 lost its typed envelope between two filing-grade revisions.

    Pinned by modelo and capability rather than by count. If the declaration is
    repaired this fails, which is the correction landing; if another modelo joins
    it the count would move while the property did not.
    """
    findings = modelo_findings(bundled_authority(), modelo_id="322")
    regressions = [f for f in findings if f.kind == "capability_lost_at_same_grade"]
    assert regressions, "the regression that motivated this screen is no longer reported"
    assert {f.capability for f in regressions} == {"typed_filing_envelope", "product_identity_requirement"}
    for finding in regressions:
        assert finding.predecessor == "2024-2025"
        assert "filing to filing" in finding.detail


def test_a_capability_lost_with_the_grade_is_not_called_a_regression() -> None:
    """Modelo 165 drops a layout into an applicability-grade stub.

    Its 2023-2025 revision declares two casillas and no layout between two filing
    revisions, which is what a deliberate placeholder looks like. Reporting it
    beside modelo 322 would put an oversight and an intention under one name.
    """
    findings = modelo_findings(bundled_authority(), modelo_id="165")
    assert findings, "modelo 165 no longer loses a capability, so this proves nothing"
    assert all(f.kind == "capability_lost_with_grade" for f in findings)
    assert all("filing to applicability" in f.detail for f in findings)


def test_both_conditions_occur_and_the_screen_separates_them() -> None:
    """A screen reporting one kind for everything would order nothing."""
    findings = screen_authority(bundled_authority(), bundled_modelo_ids())
    assert findings, "the screen lost its live population"
    assert {f.kind for f in findings} == set(KINDS)
    for finding in findings:
        assert finding.revision != finding.predecessor
        assert finding.capability


def test_capabilities_are_directional_and_exclude_counts() -> None:
    """A revision with fewer casillas is not thereby weaker.

    Counting anything would report every revision that trimmed a field, burying
    the cases where something stopped being expressible at all.
    """
    authority = bundled_authority()
    revision = authority.modelo("322").revisions["2024-2025"]
    declared = declared_capabilities(revision)
    assert declared, "the fixture revision declares nothing, so this proves nothing"
    assert all(isinstance(item, str) for item in declared)
    assert "typed_filing_envelope" in declared


def test_the_grade_ladder_matches_the_shipped_enum() -> None:
    """The order comparison rests on the enum's own ladder, not a second spelling."""
    from cadrumo.core.authority_grade import RegistryAuthorityGrade

    assert tuple(member.value for member in RegistryAuthorityGrade) == GRADE_LADDER
