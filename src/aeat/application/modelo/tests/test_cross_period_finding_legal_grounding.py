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
from ....core.resources import bundled_path
from ....domain.calculations.registry import (
    CasillaId,
    load_registry_tree,
    validated_casilla_id,
    verify_legal_catalogue,
)
from ....domain.modelos import ModeloVerificationFindingKind
from ...calculations import (
    CrossPeriodCleanStateBlocker,
    CrossPeriodCleanStateVerdict,
    CrossPeriodDependencyEvidence,
    CrossPeriodDependencyOrigin,
    CrossPeriodDependencyRequirement,
)
from .._action_errors import WORKFLOW_GATE_LEGAL_REFS
from .._verification_actions import (
    _CROSS_PERIOD_ACTIVITY_START_LEGAL_REFS,
    _CROSS_PERIOD_DEPENDENCY_LEGAL_REFS,
    _IVA_COMPENSATION_CARRY_LEGAL_REF,
    _cross_period_clean_state_findings,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_M303_SOURCE_CASILLA_01: CasillaId = validated_casilla_id("01", surface="_M303_SOURCE_CASILLA_01")


def _unclean_evidence(*, origin_ids: tuple[str, ...]) -> CrossPeriodDependencyEvidence:
    return CrossPeriodDependencyEvidence(
        requirement=CrossPeriodDependencyRequirement(
            source_modelo="303",
            filing_year=2025,
            period=Period.from_year_and_code(2025, "4T"),
            source_casilla_ids=(_M303_SOURCE_CASILLA_01,),
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


def test_application_legal_refs_resolve_to_bundled_corpus() -> None:
    """Application-level legal-ref constants must stay registry and corpus backed."""
    _, catalogues = load_registry_tree(bundled_path("registry", "aeat"))
    ref_ids = {
        *_CROSS_PERIOD_DEPENDENCY_LEGAL_REFS,
        *_CROSS_PERIOD_ACTIVITY_START_LEGAL_REFS,
        _IVA_COMPENSATION_CARRY_LEGAL_REF,
        *WORKFLOW_GATE_LEGAL_REFS,
    }

    missing = sorted(ref_ids - set(catalogues.legal))
    assert missing == []
    references = {ref_id: catalogues.legal[ref_id] for ref_id in sorted(ref_ids)}
    verify_legal_catalogue(references, source_root=bundled_path())

    assert {ref_id: ref.article for ref_id, ref in references.items()} == {
        "ley-37-1992:art-99": "99",
        "ley-58-2003:art-119": "119",
        "ley-58-2003:art-120": "120",
        "ley-58-2003:art-122": "122",
        "rd-1065-2007:art-9": "9",
    }
    assert references["ley-58-2003:art-119"].document_id == "BOE-A-2003-23186"
    assert references["ley-58-2003:art-120"].document_id == "BOE-A-2003-23186"
    assert references["ley-58-2003:art-122"].document_id == "BOE-A-2003-23186"
    assert references["ley-37-1992:art-99"].document_id == "BOE-A-1992-28740"
    assert references["rd-1065-2007:art-9"].document_id == "BOE-A-2007-15984"
    assert all(ref.required_text for ref in references.values())


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


def test_not_applicable_suppression_summary_carries_dependency_legal_refs() -> None:
    """The not-applicable suppression summary cites the scoped dependency basis."""
    evidence = CrossPeriodDependencyEvidence(
        requirement=CrossPeriodDependencyRequirement(
            source_modelo="303",
            filing_year=2025,
            period=Period.from_year_and_code(2025, "4T"),
            source_casilla_ids=(_M303_SOURCE_CASILLA_01,),
            origin=CrossPeriodDependencyOrigin.PREVIOUS_FILING_BINDING,
            origin_ids=("modelo-303-compensacion-pendiente-anteriores",),
        ),
        modelo_not_applicable_advisory=True,
    )
    verdict = _verdict(evidence)

    findings = _cross_period_clean_state_findings(verdict, activity_start_date=None)

    summary = next(f for f in findings if "not-applicable" in f.message)
    assert set(_CROSS_PERIOD_DEPENDENCY_LEGAL_REFS) <= set(summary.legal_refs)
    assert _IVA_COMPENSATION_CARRY_LEGAL_REF in summary.legal_refs


def test_non_official_local_chain_advisory_carries_dependency_legal_refs() -> None:
    """The same-year local-chain disclosure cites the dependency basis."""
    evidence = CrossPeriodDependencyEvidence(
        requirement=CrossPeriodDependencyRequirement(
            source_modelo="303",
            filing_year=2026,
            period=Period.from_year_and_code(2026, "1T"),
            source_casilla_ids=(_M303_SOURCE_CASILLA_01,),
            origin=CrossPeriodDependencyOrigin.PREVIOUS_FILING_BINDING,
            origin_ids=("modelo-303-compensacion-pendiente-anteriores",),
        ),
        non_official_local_chain_advisory=True,
    )
    verdict = _verdict(evidence)

    findings = _cross_period_clean_state_findings(verdict, activity_start_date=None)

    assert len(findings) == 1
    advisory = findings[0]
    assert advisory.kind is ModeloVerificationFindingKind.ADVISORY
    assert set(_CROSS_PERIOD_DEPENDENCY_LEGAL_REFS) <= set(advisory.legal_refs)
    assert _IVA_COMPENSATION_CARRY_LEGAL_REF in advisory.legal_refs
