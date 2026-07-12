"""Proof: unreconfirmable revision stamps are operator-visible blockers.

Current-schema cross-period carries must re-confirm the source observation's
``stamped_revision_id`` against the law-determined registry revision. A stale or
unresolvable stamp is not carried through a non-blocking advisory path; it
produces the same blocking clean-state finding used for revision divergence.
"""

from __future__ import annotations

import pytest

from ....core import Period
from ....domain.calculations.registry import CasillaId, validated_casilla_id
from ....domain.modelos import (
    ModeloVerificationFindingKind,
    ModeloVerificationFindingSeverity,
)
from ...calculations import (
    CrossPeriodCleanStateBlocker,
    CrossPeriodCleanStateVerdict,
    CrossPeriodDependencyEvidence,
    CrossPeriodDependencyOrigin,
    CrossPeriodDependencyRequirement,
)
from ...modelo._verification_actions import (
    _classify_verification_outcome,
    _cross_period_clean_state_findings,
    _cross_period_clean_state_next_action,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "revision-stamp-blocking"
_M303_SOURCE_CASILLA_01: CasillaId = validated_casilla_id("01", surface="_M303_SOURCE_CASILLA_01")
_M303_REQUIREMENT_LEGAL_REFS = ("ley-58-2003:art-119",)
_M303_REQUIREMENT_SOURCE_REFS = ("aeat-modelo-303-procedure",)


def _requirement() -> CrossPeriodDependencyRequirement:
    return CrossPeriodDependencyRequirement(
        source_modelo="303",
        filing_year=2025,
        period=Period.from_year_and_code(2025, "1T"),
        source_casilla_ids=(_M303_SOURCE_CASILLA_01,),
        origin=CrossPeriodDependencyOrigin.PREVIOUS_FILING_BINDING,
        origin_ids=("binding-303-casilla-01",),
        legal_refs=_M303_REQUIREMENT_LEGAL_REFS,
        source_refs=_M303_REQUIREMENT_SOURCE_REFS,
    )


def _verdict(evidence: CrossPeriodDependencyEvidence) -> CrossPeriodCleanStateVerdict:
    return CrossPeriodCleanStateVerdict(
        bucket_id=_BUCKET_ID,
        target_modelo="390",
        target_filing_year=2025,
        target_period=Period.from_year_and_code(2025, "0A"),
        dependencies=(evidence,),
    )


def test_registry_revision_divergence_produces_blocking_finding_with_grounding() -> None:
    evidence = CrossPeriodDependencyEvidence(
        requirement=_requirement(),
        blockers=(CrossPeriodCleanStateBlocker.REGISTRY_REVISION_DIVERGENCE,),
    )

    (finding,) = _cross_period_clean_state_findings(_verdict(evidence))

    assert finding.kind is ModeloVerificationFindingKind.CROSS_PERIOD_DEPENDENCY_UNCLEAN
    assert finding.severity is ModeloVerificationFindingSeverity.BLOCKING
    assert "registry_revision_divergence" in finding.message
    assert finding.next_action is not None
    assert "re-stamped under the current revision" in finding.next_action
    assert "aeat app live filed pull-sources --modelo 303 --year 2025 --period 1T" in finding.next_action
    assert "ley-58-2003:art-119" in finding.legal_refs
    assert finding.source_refs == _M303_REQUIREMENT_SOURCE_REFS


def test_registry_revision_divergence_blocks_verified_complete_grant() -> None:
    evidence = CrossPeriodDependencyEvidence(
        requirement=_requirement(),
        blockers=(CrossPeriodCleanStateBlocker.REGISTRY_REVISION_DIVERGENCE,),
    )
    findings = list(_cross_period_clean_state_findings(_verdict(evidence)))

    _completeness, granted = _classify_verification_outcome(findings=findings, missing_required=[])

    assert granted is False


def test_clean_current_dependency_produces_no_findings() -> None:
    evidence = CrossPeriodDependencyEvidence(
        requirement=_requirement(),
        blockers=(),
    )

    assert _cross_period_clean_state_findings(_verdict(evidence)) == ()


def test_registry_revision_divergence_next_action_names_re_file_remediation() -> None:
    evidence = CrossPeriodDependencyEvidence(
        requirement=_requirement(),
        blockers=(CrossPeriodCleanStateBlocker.REGISTRY_REVISION_DIVERGENCE,),
    )

    next_action = _cross_period_clean_state_next_action(_verdict(evidence), evidence)

    assert "does not re-confirm" in next_action
    assert "re-stamped under the current revision" in next_action
    assert "aeat app live filed pull-sources --modelo 303 --year 2025 --period 1T" in next_action
    assert "Import or capture the upstream justificante/CSV/live evidence" not in next_action
