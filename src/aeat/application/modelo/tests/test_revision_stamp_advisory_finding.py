"""Proof: the indeterminate revision-stamp advisory is operator-visible.

The period-revision-resolution decision (Ruling 3) mandates that a
cross-period carry from a prior filing with no re-confirmable registry revision
stamp MUST surface a NON-BLOCKING operator-facing advisory finding — never a
silent grant. These tests prove the WARNING ``ADVISORY`` finding IS PRODUCED by
the real findings path (``_cross_period_clean_state_findings``) for a dependency
carrying ``unstamped_revision_advisory``, even when that dependency is otherwise
``clean`` (the silent-degradation case the review flagged), and that the WARNING
does not flip the grant outcome.

These use the real production domain models (``CrossPeriodCleanStateVerdict``,
``CrossPeriodDependencyEvidence``, ``ModeloVerificationFinding``) — the same types
``evaluate_cross_period_clean_state`` constructs — not mocks or stubs.
"""

from __future__ import annotations

import pytest

from ....core import Period
from ....domain.calculations.registry import CasillaId, validated_casilla_id
from ....domain.modelos import (
    ModeloVerificationFinding,
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

_BUCKET_ID = "revision-stamp-advisory"
_M303_SOURCE_CASILLA_01: CasillaId = validated_casilla_id("01", surface="_M303_SOURCE_CASILLA_01")


def _requirement() -> CrossPeriodDependencyRequirement:
    return CrossPeriodDependencyRequirement(
        source_modelo="303",
        filing_year=2025,
        period=Period.from_year_and_code(2025, "1T"),
        source_casilla_ids=(_M303_SOURCE_CASILLA_01,),
        origin=CrossPeriodDependencyOrigin.PREVIOUS_FILING_BINDING,
        origin_ids=("binding-303-casilla-01",),
    )


def _verdict(evidence: CrossPeriodDependencyEvidence) -> CrossPeriodCleanStateVerdict:
    return CrossPeriodCleanStateVerdict(
        bucket_id=_BUCKET_ID,
        target_modelo="390",
        target_filing_year=2025,
        target_period=Period.from_year_and_code(2025, "0A"),
        dependencies=(evidence,),
    )


def test_unstamped_clean_dependency_produces_warning_advisory_finding() -> None:
    """A clean dependency carrying the unstamped advisory still produces a WARNING finding.

    This is the exact silent-degradation case the review flagged: the dependency
    is ``clean`` (no blocker) so the old early-return emitted NO finding. The fix
    surfaces the advisory regardless of clean status.
    """
    evidence = CrossPeriodDependencyEvidence(
        requirement=_requirement(),
        blockers=(),  # clean: no blocker
        unstamped_revision_advisory=True,
    )
    assert evidence.clean, "fixture must be a CLEAN dependency to prove the silent-degradation case"

    findings = _cross_period_clean_state_findings(_verdict(evidence))

    advisory = [
        f
        for f in findings
        if f.kind is ModeloVerificationFindingKind.ADVISORY and f.severity is ModeloVerificationFindingSeverity.WARNING
    ]
    assert len(advisory) == 1, (
        "a clean dependency carrying unstamped_revision_advisory MUST produce exactly one "
        f"WARNING ADVISORY finding; got findings={findings!r}"
    )
    finding = advisory[0]
    assert "revision stamp" in finding.message
    assert finding.next_action is not None
    assert "aeat app live filed pull-sources" in finding.next_action
    # No BLOCKING finding may be emitted for a clean-but-unstamped dependency.
    assert not any(f.severity is ModeloVerificationFindingSeverity.BLOCKING for f in findings)


def test_unstamped_advisory_finding_is_non_blocking_grant_proceeds() -> None:
    """The WARNING advisory does not block the verified-complete grant."""
    evidence = CrossPeriodDependencyEvidence(
        requirement=_requirement(),
        blockers=(),
        unstamped_revision_advisory=True,
    )
    findings = list(_cross_period_clean_state_findings(_verdict(evidence)))
    assert findings, "expected the advisory finding to be present"

    _completeness, granted = _classify_verification_outcome(findings=findings, missing_required=[])

    assert granted is True, "a WARNING-only advisory must not block the verified-complete grant"


def test_unclean_dependency_also_carrying_advisory_produces_both_findings() -> None:
    """An unclean dependency that also carries the advisory produces BLOCKING + WARNING findings.

    The advisory is independent of the blocking finding — both surface so the
    operator sees the hard blocker and the soft revision-stamp warning.
    """
    evidence = CrossPeriodDependencyEvidence(
        requirement=_requirement(),
        blockers=(CrossPeriodCleanStateBlocker.MISSING_OBSERVATION,),
        unstamped_revision_advisory=True,
    )
    findings = _cross_period_clean_state_findings(_verdict(evidence))

    kinds = {(f.kind, f.severity) for f in findings}
    assert (
        ModeloVerificationFindingKind.CROSS_PERIOD_DEPENDENCY_UNCLEAN,
        ModeloVerificationFindingSeverity.BLOCKING,
    ) in kinds
    assert (
        ModeloVerificationFindingKind.ADVISORY,
        ModeloVerificationFindingSeverity.WARNING,
    ) in kinds


def test_no_advisory_when_dependency_is_clean_and_stamped() -> None:
    """A clean, correctly-stamped dependency produces no findings at all."""
    evidence = CrossPeriodDependencyEvidence(
        requirement=_requirement(),
        blockers=(),
        unstamped_revision_advisory=False,
    )
    findings = _cross_period_clean_state_findings(_verdict(evidence))
    assert findings == ()


def test_registry_revision_divergence_next_action_names_re_file_remediation() -> None:
    """Recommendation (a): the REGISTRY_REVISION_DIVERGENCE blocker gets a dedicated re-file/re-stamp action."""
    evidence = CrossPeriodDependencyEvidence(
        requirement=_requirement(),
        blockers=(CrossPeriodCleanStateBlocker.REGISTRY_REVISION_DIVERGENCE,),
    )

    next_action = _cross_period_clean_state_next_action(_verdict(evidence), evidence)

    assert "no longer" in next_action
    assert "re-stamped under the current revision" in next_action
    # The remediation must name the SOURCE period capture, not the generic target import/reconcile message.
    assert "aeat app live filed pull-sources --modelo 303 --year 2025 --period 1T" in next_action
    assert "Import or capture the upstream justificante/CSV/live evidence" not in next_action


def test_finding_2_is_built_via_dedicated_advisory_helper() -> None:
    """The advisory finding's shape is stable (kind/severity/remediation) — guards the Finding-2 contract."""
    evidence = CrossPeriodDependencyEvidence(
        requirement=_requirement(),
        blockers=(),
        unstamped_revision_advisory=True,
    )
    (finding,) = _cross_period_clean_state_findings(_verdict(evidence))
    assert isinstance(finding, ModeloVerificationFinding)
    assert finding.kind is ModeloVerificationFindingKind.ADVISORY
    assert finding.severity is ModeloVerificationFindingSeverity.WARNING
    assert "could not be re-confirmed" in finding.message
