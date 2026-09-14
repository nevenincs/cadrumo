"""Real typed filing-evidence fixtures shared by cross-layer tests."""

from __future__ import annotations

from dev.registry.compiler.authority import compiled_bundled_authority

from ....core.period import Period
from ....domain.calculations.registry.iva_schema_vocabulary import m303_regime_composition_simplified_scope
from ....domain.calculations.registry.m303_orden_projection_models import M303RegimenSimplificadoSnapshot
from ....domain.calculations.registry.m303_orden_resolution import resolve_m303_regimen_simplificado_snapshot
from ....domain.filing_evidence import FilingEvidenceReference
from ....domain.iva.regimen_simplificado_rows import (
    M303RegimenSimplificadoScope,
    M303RegimenSimplificadoScopeDecision,
    RegimenSimplificadoFilingRows,
)
from ....domain.modelos.calculation_revision_m303_evidence import (
    M303DANA2024EligibilityEvidence,
    M303Exonerado390FilingEvidence,
)
from ....domain.modelos.calculation_revision_m303_handoff import (
    FilingInstanceEvidence,
    M303FilingInstanceEvidence,
    M303RegimenSimplificadoFilingEvidence,
)
from ..m303_regimen_simplificado import calculate_m303_regimen_simplificado_result


def _m303_scope_for_composition(composition: str) -> M303RegimenSimplificadoScope:
    """Project one fixture composition through the canonical 0098 vocabulary."""
    return m303_regime_composition_simplified_scope(composition)


def regimen_simplificado_filing_evidence(
    *,
    period: Period,
    scope_decision: M303RegimenSimplificadoScopeDecision,
    rows: RegimenSimplificadoFilingRows,
    regimen_snapshot: M303RegimenSimplificadoSnapshot,
    dana_2024_eligibility: M303DANA2024EligibilityEvidence | None,
) -> M303RegimenSimplificadoFilingEvidence:
    """Build real calculation-bearing simplified-regime evidence for a test filing."""
    return M303RegimenSimplificadoFilingEvidence(
        scope_decision=scope_decision,
        rows=rows,
        regimen_snapshot=regimen_snapshot,
        dana_2024_eligibility=dana_2024_eligibility,
        calculation_result=calculate_m303_regimen_simplificado_result(
            period=period,
            scope_decision=scope_decision,
            rows=rows,
            regimen_snapshot=regimen_snapshot,
            dana_2024_eligibility=dana_2024_eligibility,
            authority=compiled_bundled_authority(),
        ),
    )


def general_m303_filing_evidence(period: Period, *, reference: str) -> FilingInstanceEvidence:
    """Build explicit not-claimed evidence bound to the exact registry snapshot."""
    scope = M303RegimenSimplificadoScopeDecision(
        scope=_m303_scope_for_composition("general"),
    )
    snapshot = compiled_bundled_authority().snapshot(
        "303",
        filing_year=period.filing_year,
        period=period.registry_token,
    )
    return FilingInstanceEvidence(
        m303=M303FilingInstanceEvidence(
            period=period,
            joint_return_elected=False,
            annual_volume_nonzero=False,
            insolvency=None,
            exonerado_390=M303Exonerado390FilingEvidence(
                applicable=False,
                applicability_reference=FilingEvidenceReference(reference=reference),
                endpoints=(),
                activity_rows=(),
                operaciones_terceros_declarables=None,
                operaciones_terceros_reference=None,
            ),
            regimen_simplificado=regimen_simplificado_filing_evidence(
                period=period,
                scope_decision=scope,
                rows=RegimenSimplificadoFilingRows(ejercicio=period.filing_year, activities=()),
                regimen_snapshot=resolve_m303_regimen_simplificado_snapshot(
                    registry_snapshot=snapshot,
                    scope_decision=scope,
                ),
                dana_2024_eligibility=None,
            ),
        ),
    )


def general_m303_filing_evidence_from_regimen_snapshot(
    period: Period,
    *,
    reference: str,
    regimen_snapshot: M303RegimenSimplificadoSnapshot,
) -> FilingInstanceEvidence:
    """Build real general-scope evidence from an already validated static authority coordinate."""
    scope = M303RegimenSimplificadoScopeDecision(
        scope=_m303_scope_for_composition("general"),
    )
    return FilingInstanceEvidence(
        m303=M303FilingInstanceEvidence(
            period=period,
            joint_return_elected=False,
            annual_volume_nonzero=False,
            insolvency=None,
            exonerado_390=M303Exonerado390FilingEvidence(
                applicable=False,
                applicability_reference=FilingEvidenceReference(reference=reference),
                endpoints=(),
                activity_rows=(),
                operaciones_terceros_declarables=None,
                operaciones_terceros_reference=None,
            ),
            regimen_simplificado=regimen_simplificado_filing_evidence(
                period=period,
                scope_decision=scope,
                rows=RegimenSimplificadoFilingRows(ejercicio=period.filing_year, activities=()),
                regimen_snapshot=regimen_snapshot,
                dana_2024_eligibility=None,
            ),
        ),
    )


__all__ = [
    "general_m303_filing_evidence",
    "general_m303_filing_evidence_from_regimen_snapshot",
    "regimen_simplificado_filing_evidence",
]
