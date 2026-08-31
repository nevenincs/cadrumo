"""Shared support for calculation-revision contract tests."""

from __future__ import annotations

from decimal import Decimal
from typing import TypedDict

from ....core.casilla_id import CasillaId, validated_casilla_id
from ....core.period import Period
from ....tests.filing_evidence import regimen_simplificado_filing_evidence
from ...calculations.registry.authority import bundled_authority
from ...calculations.registry.ids import RelationId
from ...calculations.registry.m303_orden_resolution import resolve_m303_regimen_simplificado_snapshot
from ...filing_evidence import FilingEvidenceReference
from ...iva.regimen_simplificado_rows import (
    M303RegimenSimplificadoScope,
    M303RegimenSimplificadoScopeDecision,
    RegimenSimplificadoFilingRows,
)
from ..calculation_revision_m303_evidence import M303Exonerado390FilingEvidence
from ..calculation_revision_m303_handoff import M303FilingInstanceEvidence

_INPUT_CASILLA_001: CasillaId = validated_casilla_id("001")
_INPUT_CASILLA_002: CasillaId = validated_casilla_id("002")
_PIN_INPUT_CASILLA_01: CasillaId = validated_casilla_id("01")
_PIN_INPUT_CASILLA_02: CasillaId = validated_casilla_id("02")
_PIN_INPUT_CASILLA_03: CasillaId = validated_casilla_id("03")
_OUTPUT_CASILLA_002: CasillaId = validated_casilla_id("002")
_PIN_OUTPUT_CASILLA_04: CasillaId = validated_casilla_id("04")
_PIN_OUTPUT_CASILLA_07: CasillaId = validated_casilla_id("07")
_PIN_OUTPUT_CASILLA_19: CasillaId = validated_casilla_id("19")
_OBSERVATION_CASILLA_100: CasillaId = validated_casilla_id("100")
_OBSERVATION_CASILLA_200: CasillaId = validated_casilla_id("200")
_ORDERED_OUTPUT_CASILLA_010: CasillaId = validated_casilla_id("010")
_ORDERED_OUTPUT_CASILLA_020: CasillaId = validated_casilla_id("020")
_PAGOS_RELATION: RelationId = "renta-2024-rel-130-pagos-fraccionados"
_NONCANONICAL_CASILLA_KEY = "bad key"
_WHITESPACE_CASILLA_KEY = " 001 "
_TEST_LEGAL_REFS = ("ley-58-2003:art-93",)
_TEST_SOURCE_REFS = ("aeat-dr-303-2025",)


class _CommonRevisionIdArgs(TypedDict):
    """Shared typed keyword payload for source-provenance hash cases."""

    work_unit_id: str
    input_values_by_casilla_id: dict[CasillaId, str]
    binding_overrides: dict[str, str]
    casilla_values: dict[CasillaId, Decimal]


def _general_m303_filing_evidence(period: Period) -> M303FilingInstanceEvidence:
    scope = M303RegimenSimplificadoScopeDecision(
        scope=M303RegimenSimplificadoScope.REGIMEN_SIMPLIFICADO_NOT_CLAIMED,
    )
    snapshot = resolve_m303_regimen_simplificado_snapshot(
        registry_snapshot=bundled_authority().snapshot(
            "303",
            filing_year=period.filing_year,
            period="1T",
        ),
        scope_decision=scope,
    )
    return M303FilingInstanceEvidence(
        period=period,
        joint_return_elected=True,
        annual_volume_nonzero=False,
        insolvency=None,
        exonerado_390=M303Exonerado390FilingEvidence(
            applicable=False,
            applicability_reference=FilingEvidenceReference(reference="test:exonerado-390:not-applicable"),
            endpoints=(),
            activity_rows=(),
            operaciones_terceros_declarables=None,
            operaciones_terceros_reference=None,
        ),
        regimen_simplificado=regimen_simplificado_filing_evidence(
            period=period,
            scope_decision=scope,
            rows=RegimenSimplificadoFilingRows(ejercicio=period.filing_year, activities=()),
            regimen_snapshot=snapshot,
            dana_2024_eligibility=None,
        ),
    )
