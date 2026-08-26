"""Locale regression coverage for cross-period not-applicable verify findings."""

from __future__ import annotations

import pytest

from cadrumo.domain.calculations.registry.ids import SourceRefId

from ....core import CasillaId, Period, validated_casilla_id
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


def test_not_applicable_verify_finding_is_locale_neutral() -> None:
    """The application emits a locale identity and exact source-modelo facts."""

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

    findings = _cross_period_clean_state_findings(verdict, activity_start_date=None)

    assert len(findings) == 1
    finding = findings[0]
    assert finding.message_locale_key == "application.modelo.findings.cross_period_modelo_not_applicable.message"
    assert dict(finding.message_facts) == {"source_modelo_count": 1, "source_modelos": "303"}
    assert "next_action" not in finding.model_dump(mode="json")
    assert set(_CROSS_PERIOD_DEPENDENCY_LEGAL_REFS) <= set(finding.legal_refs)
    assert tuple(finding.source_refs) == (_SOURCE_REF,)
