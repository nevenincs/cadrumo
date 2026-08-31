"""Persisted evidence projects through the exact DP30302 annual-Orden authority."""

from __future__ import annotations

from decimal import Decimal

import pytest

from ....application.calculations._m303_regimen_simplificado import calculate_m303_regimen_simplificado_result
from ....application.filing._producer_snapshot import build_filing_producer_snapshot
from ....application.filing._projection import build_m303_filing_projection_plan
from ....core.filing_projection_ref import (
    M303RegimenSimplificadoActivityField,
    M303RegimenSimplificadoActivityProjectionRef,
    M303RegimenSimplificadoCohort,
    M303RegimenSimplificadoFact,
    M303RegimenSimplificadoFactProjectionRef,
    M303RegimenSimplificadoModuleProjectionRef,
    M303RegimenSimplificadoModuleValue,
)
from ....core.modelo import Modelo
from ....core.period import Period
from ....core.result_disposition import ResultDisposition
from ....domain.calculations.export_field_kind import CasillaFieldKind
from ....domain.calculations.registry.authority import bundled_authority
from ....domain.calculations.registry.errors import RegistryValidationError
from ....domain.calculations.registry.m303_orden_resolution import resolve_m303_regimen_simplificado_snapshot
from ....domain.calculations.registry.m303_regimen_simplificado_projection import project_m303_regimen_simplificado_rows
from ....domain.calculations.registry.schema_exports import (
    ExportFieldDefinition,
    ExportLayoutDefinition,
    ExportRecordDefinition,
)
from ....domain.filing_evidence import FilingEvidenceReference
from ....domain.iva.regimen_simplificado_rows import (
    ActividadNoAgricolaSimplificado,
    EntradaModuloSimplificado,
    HechoActividadSimplificado,
    M303RegimenSimplificadoScope,
    M303RegimenSimplificadoScopeDecision,
    RegimenSimplificadoFilingRows,
)
from ....domain.modelos.calculation_revision_m303_handoff import M303RegimenSimplificadoFilingEvidence
from .test_producer_snapshot import _elections, _m303_filing_facts, _m303_profile, _presenter, _taxpayer_identity

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_simplified_regime_evidence_projects_real_nonnumbered_dp30302_fields() -> None:
    period = Period.from_year_and_code(2026, "1T")
    registry_snapshot = bundled_authority().snapshot("303", filing_year=2026, period="1T")
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
                auxiliary_activity_indicator=annual_activity.auxiliary_activity_indicator,
                modulos=tuple(
                    EntradaModuloSimplificado(
                        module_identity=module.identity,
                        declared_quantity=Decimal("1"),
                        evidence_reference=reference,
                    )
                    for module in annual_activity.modulos
                ),
                facts=tuple(
                    HechoActividadSimplificado(
                        fact=M303RegimenSimplificadoFact.CUOTA_DEVENGADA_OPERACIONES_CORRIENTES,
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
        dana_2024_eligibility=None,
        calculation_result=calculate_m303_regimen_simplificado_result(
            period=period,
            scope_decision=scope,
            rows=rows,
            regimen_snapshot=regimen_snapshot,
            dana_2024_eligibility=None,
            catalogues=bundled_authority().catalogues,
        ),
    )

    assert evidence.rows.ejercicio == period.filing_year
    cuota_ref = M303RegimenSimplificadoModuleProjectionRef(
        projection_kind="m303_regimen_simplificado_module",
        cohort=M303RegimenSimplificadoCohort.NO_AGRICOLA,
        slot=1,
        module_order=1,
        value=M303RegimenSimplificadoModuleValue.CUOTA_DEVENGADA,
    )
    projected = project_m303_regimen_simplificado_rows(
        projection_refs=(
            M303RegimenSimplificadoActivityProjectionRef(
                projection_kind="m303_regimen_simplificado_activity",
                cohort=M303RegimenSimplificadoCohort.NO_AGRICOLA,
                slot=1,
                field=M303RegimenSimplificadoActivityField.IAE_EPIGRAFE,
            ),
            M303RegimenSimplificadoModuleProjectionRef(
                projection_kind="m303_regimen_simplificado_module",
                cohort=M303RegimenSimplificadoCohort.NO_AGRICOLA,
                slot=1,
                module_order=1,
                value=M303RegimenSimplificadoModuleValue.DECLARED_QUANTITY,
            ),
            M303RegimenSimplificadoModuleProjectionRef(
                projection_kind="m303_regimen_simplificado_module",
                cohort=M303RegimenSimplificadoCohort.NO_AGRICOLA,
                slot=1,
                module_order=7,
                value=M303RegimenSimplificadoModuleValue.DECLARED_QUANTITY,
            ),
            cuota_ref,
            M303RegimenSimplificadoFactProjectionRef(
                projection_kind="m303_regimen_simplificado_fact",
                cohort=M303RegimenSimplificadoCohort.NO_AGRICOLA,
                slot=1,
                fact=M303RegimenSimplificadoFact.CUOTA_DEVENGADA_OPERACIONES_CORRIENTES,
            ),
        ),
        rows=evidence.rows,
        orden=evidence.regimen_snapshot.orden.activities,
        agricultural_authority=evidence.regimen_snapshot.orden.agricultural_authority,
        applicable=not evidence.scope_decision.is_not_claimed,
        calculation_result=evidence.calculation_result,
        censo_iae_epigraphs=frozenset(
            activity.iae_epigrafe
            for activity in evidence.rows.activities
            if isinstance(activity, ActividadNoAgricolaSimplificado)
        ),
    )

    assert len(projected) == 1
    assert tuple(field.value for field in projected[0].fields) == (
        annual_activity.iae_epigrafe,
        Decimal("1"),
        None,
        evidence.calculation_result.activities[0].module_results[0].cuota_devengada,
        evidence.calculation_result.activities[0].cuota_devengada_operaciones_corrientes,
    )
    with pytest.raises(RegistryValidationError, match="requires the immutable calculation result"):
        project_m303_regimen_simplificado_rows(
            projection_refs=(cuota_ref,),
            rows=evidence.rows,
            orden=evidence.regimen_snapshot.orden.activities,
            agricultural_authority=evidence.regimen_snapshot.orden.agricultural_authority,
            applicable=True,
            calculation_result=None,
            censo_iae_epigraphs=frozenset(
                activity.iae_epigrafe
                for activity in evidence.rows.activities
                if isinstance(activity, ActividadNoAgricolaSimplificado)
            ),
        )


@pytest.mark.parametrize(
    ("filing_year", "period_code"),
    ((2023, "1T"), (2024, "1T"), (2024, "3T"), (2025, "1T"), (2026, "1T")),
)
def test_every_declared_module_cuota_endpoint_selects_the_complete_typed_result(
    filing_year: int,
    period_code: str,
) -> None:
    """All five live epochs preserve their calculated module endpoint values."""
    period = Period.from_year_and_code(filing_year, period_code)
    registry_snapshot = bundled_authority().snapshot(
        "303",
        filing_year=filing_year,
        period=period_code,
    )
    scope = M303RegimenSimplificadoScopeDecision(
        scope=M303RegimenSimplificadoScope.REGIMEN_SIMPLIFICADO_EVIDENCE_REQUIRED,
    )
    regimen_snapshot = resolve_m303_regimen_simplificado_snapshot(
        registry_snapshot=registry_snapshot,
        scope_decision=scope,
    )
    annual_activities = tuple(
        activity
        for activity in regimen_snapshot.orden.activities
        if activity.kind == "no_agricola" and len(activity.modulos) == 7
    )[:2]
    assert len(annual_activities) == 2
    reference = FilingEvidenceReference(reference=regimen_snapshot.orden.source_ref)
    filing_activities: list[ActividadNoAgricolaSimplificado] = []
    for activity in annual_activities:
        iae_epigrafe = activity.iae_epigrafe
        assert iae_epigrafe is not None
        filing_activities.append(
            ActividadNoAgricolaSimplificado(
                orden_id=activity.orden_id,
                ejercicio=filing_year,
                activity_id=activity.orden_id,
                iae_epigrafe=iae_epigrafe,
                auxiliary_activity_indicator=activity.auxiliary_activity_indicator,
                modulos=tuple(
                    EntradaModuloSimplificado(
                        module_identity=module.identity,
                        declared_quantity=Decimal("1"),
                        evidence_reference=reference,
                    )
                    for module in activity.modulos
                ),
                facts=tuple(
                    HechoActividadSimplificado(
                        fact=M303RegimenSimplificadoFact.CUOTA_DEVENGADA_OPERACIONES_CORRIENTES,
                        value=Decimal("1"),
                        evidence_reference=reference,
                    )
                    for identity in activity.applicable_fact_identities
                ),
                evidence_reference=reference,
            )
        )
    rows = RegimenSimplificadoFilingRows(
        ejercicio=filing_year,
        activities=tuple(filing_activities),
    )
    evidence = M303RegimenSimplificadoFilingEvidence(
        scope_decision=scope,
        rows=rows,
        regimen_snapshot=regimen_snapshot,
        dana_2024_eligibility=None,
        calculation_result=calculate_m303_regimen_simplificado_result(
            period=period,
            scope_decision=scope,
            rows=rows,
            regimen_snapshot=regimen_snapshot,
            dana_2024_eligibility=None,
            catalogues=bundled_authority().catalogues,
        ),
    )
    module_refs = tuple(
        declaration.projection_ref
        for declaration in registry_snapshot.revision.projection_endpoints
        if isinstance(declaration.projection_ref, M303RegimenSimplificadoModuleProjectionRef)
    )
    cuota_refs = tuple(
        reference for reference in module_refs if reference.value is M303RegimenSimplificadoModuleValue.CUOTA_DEVENGADA
    )
    assert len(module_refs) == 28
    assert len(cuota_refs) == 14

    projected = project_m303_regimen_simplificado_rows(
        projection_refs=module_refs,
        rows=evidence.rows,
        orden=evidence.regimen_snapshot.orden.activities,
        agricultural_authority=evidence.regimen_snapshot.orden.agricultural_authority,
        applicable=True,
        calculation_result=evidence.calculation_result,
        censo_iae_epigraphs=frozenset(
            row.iae_epigrafe for row in rows.activities if isinstance(row, ActividadNoAgricolaSimplificado)
        ),
    )
    actual_by_ref = {field.projection_ref: field.value for record in projected for field in record.fields}

    assert all(actual_by_ref[reference] is not None for reference in cuota_refs)
    assert tuple(actual_by_ref[reference] for reference in cuota_refs) == tuple(
        evidence.calculation_result.activities[reference.slot - 1]
        .module_results[reference.module_order - 1]
        .cuota_devengada
        for reference in cuota_refs
    )

    legal_ref = annual_activities[0].legal_refs[0]
    layout = ExportLayoutDefinition(
        id=f"m303-regimen-simplificado-result-{filing_year}",
        format="fixed_width",
        records=(
            ExportRecordDefinition(
                id="m303-regimen-simplificado-result",
                record_type="REGIMEN_SIMPLIFICADO",
                order=1,
                encoding="latin-1",
                line_ending="none",
                repeat="projection_rows",
                fields=tuple(
                    ExportFieldDefinition(
                        id=f"cuota-devengada-{index}",
                        offset=1 + (14 * index),
                        length=14,
                        kind=CasillaFieldKind.PROJECTION,
                        projection_ref=reference,
                        data_type="decimal",
                        required=True,
                        padding="left_zero",
                        justification="right",
                        decimals=2,
                        signed=False,
                        legal_refs=(legal_ref,),
                        source_refs=(regimen_snapshot.orden.source_ref,),
                    )
                    for index, reference in enumerate(cuota_refs)
                ),
            ),
        ),
        legal_refs=(legal_ref,),
        source_refs=(regimen_snapshot.orden.source_ref,),
    )
    projection_snapshot = registry_snapshot.model_copy(
        update={"revision": registry_snapshot.revision.model_copy(update={"export_layouts": (layout,)})},
    )
    facts = _m303_filing_facts(filing_year=filing_year, period_code=period_code).model_copy(
        update={
            "regimen_simplificado": evidence,
            "regimen_simplificado_result": evidence.calculation_result,
        },
    )
    producer = build_filing_producer_snapshot(
        modelo=Modelo.M303,
        taxpayer_tax_id="12345678Z",
        taxpayer_identity=_taxpayer_identity(),
        presenter=_presenter(),
        model_profile=_m303_profile(),
        elections=_elections(ResultDisposition.NEGATIVA),
        amendment_evidence=None,
        refund_account=None,
        charge_account=None,
        m303_filing_facts=facts,
    )
    plan = build_m303_filing_projection_plan(
        registry_snapshot=projection_snapshot,
        layout=layout,
        producer_snapshot=producer,
    )
    planned_by_ref = {value.projection_ref: value.value for value in plan.values}

    assert len(plan.contexts) == (len(annual_activities) + 1) // 2
    assert set(planned_by_ref) == set(cuota_refs)
    assert all(planned_by_ref[reference] is not None for reference in cuota_refs)
    assert tuple(planned_by_ref[reference] for reference in cuota_refs) == tuple(
        evidence.calculation_result.activities[reference.slot - 1]
        .module_results[reference.module_order - 1]
        .cuota_devengada
        for reference in cuota_refs
    )
