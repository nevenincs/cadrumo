"""Immutable Modelo 303 filing-evidence CLI boundary checks."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
import typer

from cadrumo.domain.calculations.registry.m303_orden_resolution import resolve_m303_regimen_simplificado_snapshot

from ....core import Period
from ....domain.calculations.registry.authority import bundled_authority
from ....domain.filing_evidence import FilingEvidenceReference
from ....domain.iva import (
    M303RegimenSimplificadoScope,
    M303RegimenSimplificadoScopeDecision,
    RegimenSimplificadoFilingRows,
)
from ....domain.modelos import (
    FilingInstanceEvidence,
    M303Exonerado390FilingEvidence,
    M303FilingInstanceEvidence,
    M303InsolvencyFilingFact,
    M303InsolvencyFilingSubtype,
)
from ....tests.filing_evidence import regimen_simplificado_filing_evidence
from .._m303_filing_evidence_input import m303_filing_instance_evidence_from_cli

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def _write_evidence(path: Path, period: Period, *, joint_return_elected: bool = True) -> None:
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
    evidence = FilingInstanceEvidence(
        m303=M303FilingInstanceEvidence(
            period=period,
            joint_return_elected=joint_return_elected,
            annual_volume_nonzero=False,
            insolvency=M303InsolvencyFilingFact(
                judicial_order_date=date(2026, 2, 3),
                subtype=M303InsolvencyFilingSubtype.POST_ORDER,
            ),
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
    path.write_text(evidence.model_dump_json(), encoding="utf-8")


def test_cli_loads_complete_m303_evidence_before_revision_creation(tmp_path: Path) -> None:
    period = Period.from_year_and_code(2026, "1T")
    evidence_path = tmp_path / "m303-filing-evidence.json"
    _write_evidence(evidence_path, period)

    evidence = m303_filing_instance_evidence_from_cli(
        modelo="303",
        period=period,
        evidence_file=evidence_path,
    )

    assert evidence is not None
    assert evidence.m303.period == period
    assert evidence.m303.joint_return_elected is True
    assert evidence.m303.insolvency is not None
    assert evidence.m303.insolvency.judicial_order_date == date(2026, 2, 3)


def test_m303_creation_refuses_an_absent_evidence_document() -> None:
    with pytest.raises(typer.BadParameter):
        m303_filing_instance_evidence_from_cli(
            modelo="303",
            period=Period.from_year_and_code(2026, "1T"),
            evidence_file=None,
        )
