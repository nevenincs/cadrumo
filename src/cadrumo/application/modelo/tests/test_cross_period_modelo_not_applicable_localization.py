"""Locale regression coverage for cross-period not-applicable verify findings."""

from __future__ import annotations

import pytest

from ....core import Period
from ....core.config import override_settings
from ....domain.calculations.registry import CasillaId, SourceRefId, validated_casilla_id
from ...calculations import (
    CrossPeriodCleanStateVerdict,
    CrossPeriodDependencyEvidence,
    CrossPeriodDependencyOrigin,
    CrossPeriodDependencyRequirement,
)
from .._verification_actions import _CROSS_PERIOD_DEPENDENCY_LEGAL_REFS
from .._verification_cross_period import _cross_period_clean_state_findings

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_SOURCE_CASILLA_01: CasillaId = validated_casilla_id("01", surface="not-applicable localization")
_SOURCE_REF: SourceRefId = "aeat-modelo-303-procedure"


def test_not_applicable_verify_finding_localizes_binding_kv_guidance() -> None:
    """The verify advisory explains ``KEY=VALUE`` in the requested language."""

    evidence = CrossPeriodDependencyEvidence(
        requirement=CrossPeriodDependencyRequirement(
            source_modelo="303",
            filing_year=2025,
            period=Period.from_year_and_code(2025, "4T"),
            source_casilla_ids=(_SOURCE_CASILLA_01,),
            origin=CrossPeriodDependencyOrigin.PREVIOUS_FILING_BINDING,
            origin_ids=("modelo-303-compensacion-pendiente-anteriores",),
            legal_refs=("ley-58-2003:art-119",),
            source_refs=(_SOURCE_REF,),
        ),
        modelo_not_applicable_advisory=True,
    )
    verdict = CrossPeriodCleanStateVerdict(
        bucket_id="not-applicable-localization",
        target_modelo="303",
        target_filing_year=2026,
        target_period=Period.from_year_and_code(2026, "1T"),
        dependencies=(evidence,),
    )

    with override_settings(cadrumo_output_language="hu"):
        findings = _cross_period_clean_state_findings(verdict, activity_start_date=None)

    assert len(findings) == 1
    finding = findings[0]
    assert "KULCS=ÉRTÉK" in finding.message
    assert "egyenlőségjel bal oldalán" in finding.message
    assert "source modelos the taxpayer does not file" not in finding.message
    assert "put the binding id on the left" not in (finding.next_action or "")
    assert set(_CROSS_PERIOD_DEPENDENCY_LEGAL_REFS) <= set(finding.legal_refs)
    assert tuple(finding.source_refs) == (_SOURCE_REF,)
