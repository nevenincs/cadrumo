"""Persisted S58 evidence projects through the exact S59 DP30302 authority."""

from __future__ import annotations

from decimal import Decimal

import pytest

from ....core import Period
from ....core.resources import resources
from ....domain.calculations.registry import resolve_m303_regimen_simplificado_snapshot
from ....domain.filing_evidence import FilingEvidenceReference
from ....domain.iva import (
    ActividadNoAgricolaSimplificado,
    EntradaModuloSimplificado,
    HechoActividadSimplificado,
    M303RegimenSimplificadoScope,
    M303RegimenSimplificadoScopeDecision,
    RegimenSimplificadoFilingRows,
)
from ....domain.modelos import M303RegimenSimplificadoFilingEvidence
from .. import build_runtime_schema_provider, project_m303_regimen_simplificado_value_arrival

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_simplified_regime_evidence_projects_real_nonnumbered_dp30302_fields() -> None:
    period = Period.from_year_and_code(2026, "1T")
    registry_snapshot = resources().modelos.authority.snapshot("303", filing_year=2026, period="1T")
    scope = M303RegimenSimplificadoScopeDecision(
        scope=M303RegimenSimplificadoScope.REGIMEN_SIMPLIFICADO_EVIDENCE_REQUIRED,
    )
    regimen_snapshot = resolve_m303_regimen_simplificado_snapshot(
        registry_snapshot=registry_snapshot,
        scope_decision=scope,
    )
    annual_activity = regimen_snapshot.orden.activities[0]
    assert annual_activity.kind == "no_agricola"
    assert annual_activity.iae_epigrafe is not None
    assert annual_activity.orden_id == "m303:2026:iva:82e3988053fc055b601e"
    assert annual_activity.cuota_minima_pct == Decimal("20")
    reference = FilingEvidenceReference(reference=regimen_snapshot.orden.source_ref)
    rows = RegimenSimplificadoFilingRows(
        ejercicio=2026,
        activities=(
            ActividadNoAgricolaSimplificado(
                orden_id=annual_activity.orden_id,
                ejercicio=2026,
                activity_id=annual_activity.orden_id,
                iae_epigrafe=annual_activity.iae_epigrafe,
                modulos=tuple(
                    EntradaModuloSimplificado(
                        module_identity=module.identity,
                        declared_quantity=Decimal("1"),
                        off_form_result=module.coefficient,
                        evidence_reference=reference,
                    )
                    for module in annual_activity.modulos
                ),
                facts=tuple(
                    HechoActividadSimplificado(
                        identity=identity,
                        value=Decimal("1"),
                        evidence_reference=reference,
                    )
                    for identity in annual_activity.applicable_fact_identities
                ),
                evidence_reference=reference,
            ),
        ),
    )
    evidence = M303RegimenSimplificadoFilingEvidence(
        scope_decision=scope,
        rows=rows,
        regimen_snapshot=regimen_snapshot,
    )

    projected = project_m303_regimen_simplificado_value_arrival(
        period=period,
        schema_provider=build_runtime_schema_provider(filing_year=2026, period=period, modelos=("303",)),
        evidence=evidence,
    )

    assert len(projected) == 1
    assert projected[0].design_epoch == "2026"
    values = tuple(field.value for field in projected[0].fields if field.value is not None)
    assert annual_activity.iae_epigrafe in values
    assert Decimal("1") in values
