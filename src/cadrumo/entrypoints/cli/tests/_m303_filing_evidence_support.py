"""Shared writer for the complete Modelo 303 filing-evidence document.

`app modelo work calculate` refuses a Modelo 303 target that carries no
`--m303-filing-evidence` document, so every CLI test that calculates an M303
work unit needs one on disk. This module is that document's single test-side
home: the shape is non-trivial (an exonerado-390 block, an insolvency fact and
a regimen-simplificado block whose snapshot is resolved from the registry
authority), and a second hand-built copy would drift from the model the
boundary validates.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from ....core import Period
from ....domain.calculations.registry.authority import bundled_authority
from ....domain.calculations.registry.m303_orden_resolution import resolve_m303_regimen_simplificado_snapshot
from ....domain.filing_evidence import FilingEvidenceReference
from ....domain.iva import (
    M303RegimenSimplificadoScope,
    M303RegimenSimplificadoScopeDecision,
    RegimenSimplificadoFilingRows,
)
from ....domain.modelos.calculation_revision import (
    FilingInstanceEvidence,
    M303Exonerado390FilingEvidence,
    M303FilingInstanceEvidence,
    M303InsolvencyFilingFact,
    M303InsolvencyFilingSubtype,
)
from ....tests.filing_evidence import regimen_simplificado_filing_evidence

__all__ = ["build_m303_filing_evidence", "default_insolvency_fact", "write_m303_filing_evidence"]


def build_m303_filing_evidence(
    period: Period,
    *,
    joint_return_elected: bool = True,
    insolvency: M303InsolvencyFilingFact | None = None,
) -> FilingInstanceEvidence:
    """Build one complete evidence document for ``period``.

    The regimen-simplificado snapshot is resolved through the registry
    authority rather than hand-written, so the document stays valid as new
    ordenes open.
    """
    scope = M303RegimenSimplificadoScopeDecision(
        scope=M303RegimenSimplificadoScope.REGIMEN_SIMPLIFICADO_NOT_CLAIMED,
    )
    snapshot = resolve_m303_regimen_simplificado_snapshot(
        registry_snapshot=bundled_authority().snapshot(
            "303",
            filing_year=period.filing_year,
            period=period.code,
        ),
        scope_decision=scope,
    )
    return FilingInstanceEvidence(
        m303=M303FilingInstanceEvidence(
            period=period,
            joint_return_elected=joint_return_elected,
            annual_volume_nonzero=False,
            insolvency=insolvency,
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
        ),
    )


def write_m303_filing_evidence(
    path: Path,
    period: Period,
    *,
    joint_return_elected: bool = True,
    insolvency: M303InsolvencyFilingFact | None = None,
) -> Path:
    """Write the evidence document for ``period`` to ``path`` and return it."""
    evidence = build_m303_filing_evidence(
        period,
        joint_return_elected=joint_return_elected,
        insolvency=insolvency,
    )
    path.write_text(evidence.model_dump_json(), encoding="utf-8")
    return path


def default_insolvency_fact() -> M303InsolvencyFilingFact:
    """The post-order insolvency fact the boundary contract test asserts."""
    return M303InsolvencyFilingFact(
        judicial_order_date=date(2026, 2, 3),
        subtype=M303InsolvencyFilingSubtype.POST_ORDER,
    )
