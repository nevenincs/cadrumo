"""Real annual-Orden proofs for Modelo 303 simplified-regime calculation."""

from __future__ import annotations

from decimal import Decimal

import pytest

from ....core import M303RegimenSimplificadoFact, Period
from ....domain.calculations.registry.authority import bundled_authority
from ....domain.calculations.registry.m303_orden_projection_models import M303RegimenSimplificadoSnapshot
from ....domain.calculations.registry.m303_orden_resolution import resolve_m303_regimen_simplificado_snapshot
from ....domain.filing_evidence import FilingEvidenceReference
from ....domain.iva.regimen_simplificado_rows import ActividadNoAgricolaSimplificado, EntradaModuloSimplificado, HechoActividadSimplificado, M303RegimenSimplificadoScope, M303RegimenSimplificadoScopeDecision, RegimenSimplificadoFilingRows
from ....domain.modelos.calculation_revision import M303DANA2024EligibilityEvidence
from .. import M303RegimenSimplificadoCalculationError, calculate_m303_regimen_simplificado_result

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _annual_snapshot_and_rows(
    period: Period,
) -> tuple[
    M303RegimenSimplificadoScopeDecision,
    RegimenSimplificadoFilingRows,
    M303RegimenSimplificadoSnapshot,
]:
    scope = M303RegimenSimplificadoScopeDecision(
        scope=M303RegimenSimplificadoScope.REGIMEN_SIMPLIFICADO_EVIDENCE_REQUIRED,
    )
    snapshot = resolve_m303_regimen_simplificado_snapshot(
        registry_snapshot=bundled_authority().snapshot(
            "303",
            filing_year=period.filing_year,
            period=period.registry_token,
        ),
        scope_decision=scope,
    )
    annual = snapshot.orden.activities[0]
    assert annual.kind == "no_agricola"
    assert annual.iae_epigrafe is not None
    reference = FilingEvidenceReference(reference="test:m303-simplificado:annual-orden")
    rows = RegimenSimplificadoFilingRows(
        ejercicio=period.filing_year,
        activities=(
            ActividadNoAgricolaSimplificado(
                orden_id=annual.orden_id,
                ejercicio=period.filing_year,
                activity_id=annual.orden_id,
                iae_epigrafe=annual.iae_epigrafe,
                auxiliary_activity_indicator=annual.auxiliary_activity_indicator,
                modulos=tuple(
                    EntradaModuloSimplificado(
                        module_identity=module.identity,
                        declared_quantity=Decimal("1") if index == 0 else Decimal("0"),
                        evidence_reference=reference,
                    )
                    for index, module in enumerate(annual.modulos)
                ),
                facts=tuple(
                    HechoActividadSimplificado(
                        fact=M303RegimenSimplificadoFact.CUOTA_DEVENGADA_OPERACIONES_CORRIENTES,
                        value=Decimal("1"),
                        evidence_reference=reference,
                    )
                    for identity in annual.applicable_fact_identities
                ),
                evidence_reference=reference,
            ),
        ),
    )
    return scope, rows, snapshot


def test_2024_annual_dana_reduces_each_eligible_activity_once_from_bundled_authority() -> None:
    period = Period.from_year_and_code(2024, "4T")
    scope, rows, snapshot = _annual_snapshot_and_rows(period)
    eligibility = M303DANA2024EligibilityEvidence(
        eligible=True,
        evidence_reference=FilingEvidenceReference(reference="test:m303-simplificado:dana-eligibility"),
    )

    result = calculate_m303_regimen_simplificado_result(
        period=period,
        scope_decision=scope,
        rows=rows,
        regimen_snapshot=snapshot,
        dana_2024_eligibility=eligibility,
        catalogues=bundled_authority().catalogues,
    )

    activity = result.activities[0]
    assert activity.cuota_devengada_operaciones_corrientes == Decimal("1693.54")
    assert activity.dana_2024_reduction is not None
    assert activity.dana_2024_reduction.rate == Decimal("0.25")
    assert activity.dana_2024_reduction.amount == Decimal("423.39")
    assert activity.cuota_devengada_tras_dana_2024 == Decimal("1270.15")
    assert activity.cuota_resultante == Decimal("1257.45")
    assert activity.dana_2024_reduction.legal_refs == (
        "real-decreto-ley-7-2024:art-11.2",
        "real-decreto-ley-7-2024:df-14",
        "real-decreto-ley-6-2024:anexo",
        "real-decreto-ley-6-2024:art-1",
        "correccion-errores-rdl-6-2024",
    )
    assert activity.dana_2024_reduction.source_refs == (
        "boe-rdl-7-2024-dana-authority",
        "boe-rdl-6-2024-dana-authority",
        "boe-correccion-errores-rdl-6-2024",
    )
    assert result == calculate_m303_regimen_simplificado_result(
        period=period,
        scope_decision=scope,
        rows=rows,
        regimen_snapshot=snapshot,
        dana_2024_eligibility=eligibility,
        catalogues=bundled_authority().catalogues,
    )


def test_dana_eligibility_is_refused_outside_the_2024_annual_result() -> None:
    period = Period.from_year_and_code(2024, "3T")
    scope, rows, snapshot = _annual_snapshot_and_rows(period)
    eligibility = M303DANA2024EligibilityEvidence(
        eligible=True,
        evidence_reference=FilingEvidenceReference(reference="test:m303-simplificado:quarterly-dana"),
    )

    with pytest.raises(M303RegimenSimplificadoCalculationError, match="only for the 2024 annual"):
        calculate_m303_regimen_simplificado_result(
            period=period,
            scope_decision=scope,
            rows=rows,
            regimen_snapshot=snapshot,
            dana_2024_eligibility=eligibility,
            catalogues=bundled_authority().catalogues,
        )
