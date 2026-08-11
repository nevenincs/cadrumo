"""Real typed filing-evidence fixtures shared by cross-layer tests."""

from __future__ import annotations

from ..core import Period
from ..core.resources import resources
from ..domain.calculations.registry import resolve_m303_regimen_simplificado_snapshot
from ..domain.filing_evidence import FilingEvidenceReference
from ..domain.iva import (
    M303RegimenSimplificadoScope,
    M303RegimenSimplificadoScopeDecision,
    RegimenSimplificadoFilingRows,
)
from ..domain.modelos import (
    FilingInstanceEvidence,
    M303Exonerado390FilingEvidence,
    M303FilingInstanceEvidence,
    M303RegimenSimplificadoFilingEvidence,
)


def general_m303_filing_evidence(period: Period, *, reference: str) -> FilingInstanceEvidence:
    """Build explicit not-claimed evidence bound to the exact registry snapshot."""
    scope = M303RegimenSimplificadoScopeDecision(
        scope=M303RegimenSimplificadoScope.REGIMEN_SIMPLIFICADO_NOT_CLAIMED,
    )
    snapshot = resources().modelos.authority.snapshot(
        "303",
        filing_year=period.filing_year,
        period=period.registry_token,
    )
    return FilingInstanceEvidence(
        m303=M303FilingInstanceEvidence(
            period=period,
            joint_return_elected=False,
            insolvency=None,
            exonerado_390=M303Exonerado390FilingEvidence(
                applicable=False,
                applicability_reference=FilingEvidenceReference(reference=reference),
                endpoints=(),
                activity_rows=(),
                operaciones_terceros_declarables=None,
                operaciones_terceros_reference=None,
            ),
            regimen_simplificado=M303RegimenSimplificadoFilingEvidence(
                scope_decision=scope,
                rows=RegimenSimplificadoFilingRows(ejercicio=period.filing_year, activities=()),
                regimen_snapshot=resolve_m303_regimen_simplificado_snapshot(
                    registry_snapshot=snapshot,
                    scope_decision=scope,
                ),
            ),
        ),
    )


__all__ = ["general_m303_filing_evidence"]
