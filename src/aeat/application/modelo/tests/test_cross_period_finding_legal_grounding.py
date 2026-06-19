"""Cross-period verification findings carry their legal grounding.

The verification-reports how-to promises every finding carries "the legal
references behind the rule". Before this gate the cross-period
``CROSS_PERIOD_DEPENDENCY_UNCLEAN`` findings (and the first-filer
activity-start finding) shipped with empty ``legal_refs``, so ``view`` rendered
no ``finding_legal_refs`` line for the most common blocking outcome on a
quarterly IVA filing. This locks the grounding onto each finding the
:func:`_cross_period_clean_state_findings` builder emits.
"""

from __future__ import annotations

import pytest

from ....core import Period
from ....domain.modelos import ModeloVerificationFindingKind
from ...calculations import (
    CrossPeriodCleanStateBlocker,
    CrossPeriodCleanStateVerdict,
    CrossPeriodDependencyEvidence,
    CrossPeriodDependencyOrigin,
    CrossPeriodDependencyRequirement,
)
from .._verification_actions import (
    _CROSS_PERIOD_ACTIVITY_START_LEGAL_REFS,
    _CROSS_PERIOD_DEPENDENCY_LEGAL_REFS,
    _IVA_COMPENSATION_CARRY_LEGAL_REF,
    _cross_period_clean_state_findings,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _unclean_evidence(*, origin_ids: tuple[str, ...]) -> CrossPeriodDependencyEvidence:
    return CrossPeriodDependencyEvidence(
        requirement=CrossPeriodDependencyRequirement(
            source_modelo="303",
            filing_year=2025,
            period=Period.from_year_and_code(2025, "4T"),
            source_casillas=("01",),
            origin=CrossPeriodDependencyOrigin.PREVIOUS_FILING_BINDING,
            origin_ids=origin_ids,
        ),
        blockers=(CrossPeriodCleanStateBlocker.MISSING_OBSERVATION,),
    )


def _verdict(evidence: CrossPeriodDependencyEvidence) -> CrossPeriodCleanStateVerdict:
    return CrossPeriodCleanStateVerdict(
        bucket_id="cross-period-grounding",
        target_modelo="303",
        target_filing_year=2026,
        target_period=Period.from_year_and_code(2026, "1T"),
        dependencies=(evidence,),
    )


def test_iva_compensacion_dependency_finding_cites_liva_and_lgt() -> None:
    """A compensación carry cites the prior-declaration LGT basis plus LIVA art. 99."""
    verdict = _verdict(_unclean_evidence(origin_ids=("modelo-303-compensacion-pendiente-anteriores",)))

    findings = _cross_period_clean_state_findings(verdict, activity_start_date=None)

    blocking = next(
        f
        for f in findings
        if f.kind is ModeloVerificationFindingKind.CROSS_PERIOD_DEPENDENCY_UNCLEAN and "not clean" in f.message
    )
    assert set(_CROSS_PERIOD_DEPENDENCY_LEGAL_REFS) <= set(blocking.legal_refs)
    assert _IVA_COMPENSATION_CARRY_LEGAL_REF in blocking.legal_refs


def test_non_compensacion_dependency_finding_cites_lgt_only() -> None:
    """A non-compensación carry cites the prior-declaration LGT basis, not LIVA art. 99."""
    verdict = _verdict(_unclean_evidence(origin_ids=("modelo-100-rel-pago-fraccionado",)))

    findings = _cross_period_clean_state_findings(verdict, activity_start_date=None)

    blocking = next(f for f in findings if "not clean" in f.message)
    assert tuple(blocking.legal_refs) == _CROSS_PERIOD_DEPENDENCY_LEGAL_REFS
    assert _IVA_COMPENSATION_CARRY_LEGAL_REF not in blocking.legal_refs


def test_missing_activity_start_finding_cites_censo_alta() -> None:
    """The first-filer fail-closed finding cites the start-of-activity censo basis."""
    verdict = _verdict(_unclean_evidence(origin_ids=("modelo-303-compensacion-pendiente-anteriores",)))

    findings = _cross_period_clean_state_findings(verdict, activity_start_date=None)

    activity_start = next(f for f in findings if "no activity-start date" in f.message)
    assert tuple(activity_start.legal_refs) == _CROSS_PERIOD_ACTIVITY_START_LEGAL_REFS


def test_every_cross_period_finding_carries_legal_refs() -> None:
    """No cross-period finding ships with empty grounding (the page's promise)."""
    verdict = _verdict(_unclean_evidence(origin_ids=("modelo-303-compensacion-pendiente-anteriores",)))

    findings = _cross_period_clean_state_findings(verdict, activity_start_date=None)

    assert findings
    assert all(f.legal_refs for f in findings)
