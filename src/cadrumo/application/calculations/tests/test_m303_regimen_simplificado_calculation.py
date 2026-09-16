"""Real annual-Orden proofs for Modelo 303 simplified-regime calculation."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date
from decimal import Decimal

import pytest

from ....core.filing_projection_ref import M303RegimenSimplificadoFact
from ....core.period import Period
from ....domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from ....domain.calculations.registry.errors import RegistryValidationError
from ....domain.calculations.registry.facts.resolution import ResolvedScalarFact, ScalarFactQuery
from ....domain.calculations.registry.iva_schema_vocabulary import m303_regime_composition_simplified_scope
from ....domain.calculations.registry.m303_orden_projection_models import M303RegimenSimplificadoSnapshot
from ....domain.calculations.registry.m303_orden_resolution import resolve_m303_regimen_simplificado_snapshot
from ....domain.calculations.registry.schema_base import DateAxis
from ....domain.calculations.registry.schema_references import TemporalProjectionDirection
from ....domain.calculations.registry.tests.published_authority import published_snapshot
from ....domain.filing_evidence import FilingEvidenceReference
from ....domain.iva.regimen_simplificado_rows import (
    ActividadNoAgricolaSimplificado,
    EntradaModuloSimplificado,
    HechoActividadSimplificado,
    LorcaActivityEligibility,
    M303RegimenSimplificadoScopeDecision,
    RegimenSimplificadoFilingRows,
)
from ....domain.modelos.calculation_revision_m303_evidence import M303DANAEligibilityEvidence
from ..m303_regimen_simplificado import (
    M303RegimenSimplificadoCalculationError,
    calculate_m303_regimen_simplificado_result,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


@pytest.fixture
def authority_operation() -> Iterator[PinnedAuthorityOperation]:
    with bundled_indexed_authority().operation() as operation:
        yield operation


def _annual_snapshot_and_rows(
    period: Period,
) -> tuple[
    M303RegimenSimplificadoScopeDecision,
    RegimenSimplificadoFilingRows,
    M303RegimenSimplificadoSnapshot,
]:
    scope = M303RegimenSimplificadoScopeDecision(
        scope=m303_regime_composition_simplified_scope("simplified", effective_date=period.end_date),
    )
    snapshot = resolve_m303_regimen_simplificado_snapshot(
        registry_snapshot=published_snapshot(
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
                lorca_eligibility=LorcaActivityEligibility(eligible=False, evidence_reference=reference),
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


def test_lorca_calculation_across_registry_support_envelope(authority_operation) -> None:
    support = authority_operation.modelo_directory("303").supported_filing_years
    assert support is not None
    upper = support.hard_ceiling if support.hard_ceiling is not None else support.horizon
    years = tuple(range(support.floor, upper + 1))
    if support.hard_ceiling is None:
        years += (support.horizon + 1,)
    for year in years:
        period = Period.from_year_and_code(year, "4T")
        scope, rows, snapshot = _annual_snapshot_and_rows(period)
        try:
            dana_fact = authority_operation.resolve_governed_fact(
                ScalarFactQuery(
                    fact_id="rdl-7-2024-art-11-2:iva-simplificado-reduccion-cuota-devengada",
                    date_axis=DateAxis.FILING_PERIOD,
                    effective_date=period.end_date,
                )
            )
            dana_available = dana_fact.projection_direction is TemporalProjectionDirection.AUTHORED
        except RegistryValidationError:
            dana_available = False
        dana = (
            M303DANAEligibilityEvidence(
                eligible=False,
                evidence_reference=FilingEvidenceReference(reference="test:lorca:not-dana"),
            )
            if dana_available
            else None
        )
        payload = rows.model_dump(mode="python")
        payload["activities"][0]["lorca_eligibility"]["eligible"] = True
        claimed_rows = RegimenSimplificadoFilingRows.model_validate(payload)
        if snapshot.orden.lorca_reduction is None:
            with pytest.raises(M303RegimenSimplificadoCalculationError, match="Lorca reduction is unavailable"):
                calculate_m303_regimen_simplificado_result(
                    period=period,
                    scope_decision=scope,
                    rows=claimed_rows,
                    regimen_snapshot=snapshot,
                    dana_eligibility=dana,
                    operation=authority_operation,
                )
            continue
        result = calculate_m303_regimen_simplificado_result(
            period=period,
            scope_decision=scope,
            rows=claimed_rows,
            regimen_snapshot=snapshot,
            dana_eligibility=dana,
            operation=authority_operation,
        )
        activity = result.activities[0]
        assert activity.lorca_reduction_amount == (
            activity.cuota_devengada_operaciones_corrientes * Decimal("0.20")
        ).quantize(Decimal("0.01"))
        assert activity.cuota_devengada_tras_reducciones == (
            activity.cuota_devengada_operaciones_corrientes - activity.lorca_reduction_amount
        )
        assert snapshot.orden.lorca_reduction.source_refs[0] in activity.source_refs
        payload["activities"][0]["lorca_eligibility"] = None
        missing_rows = RegimenSimplificadoFilingRows.model_validate(payload)
        with pytest.raises(M303RegimenSimplificadoCalculationError, match="requires Lorca eligibility evidence"):
            calculate_m303_regimen_simplificado_result(
                period=period,
                scope_decision=scope,
                rows=missing_rows,
                regimen_snapshot=snapshot,
                dana_eligibility=dana,
                operation=authority_operation,
            )


def test_2024_annual_dana_reduces_each_eligible_activity_once_from_bundled_authority(authority_operation) -> None:
    period = Period.from_year_and_code(2024, "4T")
    scope, rows, snapshot = _annual_snapshot_and_rows(period)
    eligibility = M303DANAEligibilityEvidence(
        eligible=True,
        evidence_reference=FilingEvidenceReference(reference="test:m303-simplificado:dana-eligibility"),
    )

    result = calculate_m303_regimen_simplificado_result(
        period=period,
        scope_decision=scope,
        rows=rows,
        regimen_snapshot=snapshot,
        dana_eligibility=eligibility,
        operation=authority_operation,
    )

    activity = result.activities[0]
    assert activity.cuota_devengada_operaciones_corrientes == Decimal("1693.54")
    assert activity.dana_reduction is not None
    assert activity.dana_reduction.rate == Decimal("0.25")
    assert activity.dana_reduction.amount == Decimal("423.39")
    assert activity.cuota_devengada_tras_dana == Decimal("1270.15")
    assert activity.cuota_resultante == Decimal("1257.45")
    assert activity.dana_reduction.legal_refs == (
        "real-decreto-ley-7-2024:art-11.2",
        "real-decreto-ley-7-2024:df-14",
        "real-decreto-ley-6-2024:anexo",
        "real-decreto-ley-6-2024:art-1",
        "correccion-errores-rdl-6-2024",
    )
    assert activity.dana_reduction.source_refs == (
        "boe-rdl-7-2024-dana-authority",
        "boe-rdl-6-2024-dana-authority",
        "boe-correccion-errores-rdl-6-2024",
    )
    assert result == calculate_m303_regimen_simplificado_result(
        period=period,
        scope_decision=scope,
        rows=rows,
        regimen_snapshot=snapshot,
        dana_eligibility=eligibility,
        operation=authority_operation,
    )


def test_dana_eligibility_is_refused_outside_the_2024_annual_result(authority_operation) -> None:
    period = Period.from_year_and_code(2024, "3T")
    scope, rows, snapshot = _annual_snapshot_and_rows(period)
    eligibility = M303DANAEligibilityEvidence(
        eligible=True,
        evidence_reference=FilingEvidenceReference(reference="test:m303-simplificado:quarterly-dana"),
    )

    with pytest.raises(
        M303RegimenSimplificadoCalculationError,
        match="only when the selected registry reduction applies to the annual simplified result",
    ):
        calculate_m303_regimen_simplificado_result(
            period=period,
            scope_decision=scope,
            rows=rows,
            regimen_snapshot=snapshot,
            dana_eligibility=eligibility,
            operation=authority_operation,
        )


def _resolve_dana_fact(operation: PinnedAuthorityOperation, effective_date: date) -> ResolvedScalarFact:
    resolved = operation.resolve_governed_fact(
        ScalarFactQuery(
            fact_id="rdl-7-2024-art-11-2:iva-simplificado-reduccion-cuota-devengada",
            date_axis=DateAxis.FILING_PERIOD,
            effective_date=effective_date,
        ),
    )
    assert isinstance(resolved, ResolvedScalarFact)
    return resolved


@pytest.mark.parametrize("effective_date", [date(2024, 11, 13), date(2024, 12, 1), date(2024, 12, 31)])
def test_dana_fact_is_authored_inside_and_at_the_edges_of_its_legal_window(
    authority_operation,
    effective_date: date,
) -> None:
    resolved = _resolve_dana_fact(authority_operation, effective_date)

    assert resolved.projection_direction is TemporalProjectionDirection.AUTHORED
    assert resolved.payload.value == Decimal("0.25")
    assert (resolved.authored_valid_from, resolved.authored_valid_to) == (date(2024, 11, 13), date(2024, 12, 31))


@pytest.mark.parametrize("effective_date", [date(2024, 11, 12), date(2025, 1, 1), date(2025, 12, 31)])
def test_dana_fact_outside_its_declared_hard_bounds_refuses(authority_operation, effective_date: date) -> None:
    with pytest.raises(RegistryValidationError, match="outside its hard support boundaries"):
        _resolve_dana_fact(authority_operation, effective_date)


def test_2025_annual_result_refuses_dana_evidence_and_applies_no_reduction(authority_operation) -> None:
    period = Period.from_year_and_code(2025, "4T")
    scope, rows, snapshot = _annual_snapshot_and_rows(period)
    eligibility = M303DANAEligibilityEvidence(
        eligible=True,
        evidence_reference=FilingEvidenceReference(reference="test:m303-simplificado:expired-dana"),
    )

    with pytest.raises(
        M303RegimenSimplificadoCalculationError,
        match="only when the selected registry reduction applies to the annual simplified result",
    ):
        calculate_m303_regimen_simplificado_result(
            period=period,
            scope_decision=scope,
            rows=rows,
            regimen_snapshot=snapshot,
            dana_eligibility=eligibility,
            operation=authority_operation,
        )

    result = calculate_m303_regimen_simplificado_result(
        period=period,
        scope_decision=scope,
        rows=rows,
        regimen_snapshot=snapshot,
        dana_eligibility=None,
        operation=authority_operation,
    )

    activity = result.activities[0]
    assert activity.dana_reduction is None
    assert activity.cuota_devengada_tras_dana == activity.cuota_devengada_operaciones_corrientes
    assert not any(ref.startswith("real-decreto-ley-7-2024") for ref in activity.legal_refs)
