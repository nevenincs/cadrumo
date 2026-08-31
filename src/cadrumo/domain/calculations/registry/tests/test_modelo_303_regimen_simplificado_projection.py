"""Typed reference proofs for Modelo 303 simplified-regime projection."""

from __future__ import annotations

from decimal import Decimal

import pytest

from .....application.calculations import calculate_m303_regimen_simplificado_result
from .....core import (
    M303RegimenSimplificadoActivityField,
    M303RegimenSimplificadoActivityProjectionRef,
    M303RegimenSimplificadoCohort,
    M303RegimenSimplificadoFact,
    M303RegimenSimplificadoFactProjectionRef,
    M303RegimenSimplificadoModuleProjectionRef,
    M303RegimenSimplificadoModuleValue,
    Period,
)
from .....domain.iva import (
    ActividadAgricolaSimplificado,
    ActividadNoAgricolaSimplificado,
    EntradaModuloSimplificado,
    HechoActividadSimplificado,
    IvaValidationError,
    M303RegimenSimplificadoScope,
    M303RegimenSimplificadoScopeDecision,
    RegimenSimplificadoFilingRows,
)
from ....filing_evidence import FilingEvidenceReference
from ..authority import bundled_authority
from ..errors import RegistryValidationError
from ..m303_orden_resolution import resolve_m303_regimen_simplificado_snapshot
from ..m303_regimen_simplificado_projection import (
    _m303_iae_epigraph_wire_value,
    project_m303_regimen_simplificado_rows,
    validate_m303_regimen_simplificado_endpoint_epoch,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _activity_ref() -> M303RegimenSimplificadoActivityProjectionRef:
    return M303RegimenSimplificadoActivityProjectionRef(
        projection_kind="m303_regimen_simplificado_activity",
        cohort=M303RegimenSimplificadoCohort.AGRICOLA,
        slot=1,
        field=M303RegimenSimplificadoActivityField.ACTIVITY_CODE,
    )


def _resolved_annual_orden_for_2026():
    registry_snapshot = bundled_authority().snapshot("303", filing_year=2026, period="1T")
    return resolve_m303_regimen_simplificado_snapshot(
        registry_snapshot=registry_snapshot,
        scope_decision=M303RegimenSimplificadoScopeDecision(
            scope=M303RegimenSimplificadoScope.REGIMEN_SIMPLIFICADO_EVIDENCE_REQUIRED,
        ),
    ).orden


def test_non_applicable_projection_retains_the_typed_contract_without_source_text_inference() -> None:
    annual_orden = _resolved_annual_orden_for_2026()
    projected = project_m303_regimen_simplificado_rows(
        projection_refs=(_activity_ref(),),
        rows=RegimenSimplificadoFilingRows(ejercicio=2025, activities=()),
        orden=(),
        agricultural_authority=annual_orden.agricultural_authority,
        applicable=False,
        calculation_result=None,
        censo_iae_epigraphs=frozenset(),
    )

    assert projected == ()


def test_projection_rejects_missing_or_duplicate_typed_references() -> None:
    rows = RegimenSimplificadoFilingRows(ejercicio=2025, activities=())
    annual_orden = _resolved_annual_orden_for_2026()
    with pytest.raises(RegistryValidationError, match="requires typed"):
        project_m303_regimen_simplificado_rows(
            projection_refs=(),
            rows=rows,
            orden=(),
            agricultural_authority=annual_orden.agricultural_authority,
            applicable=False,
            calculation_result=None,
            censo_iae_epigraphs=frozenset(),
        )
    with pytest.raises(RegistryValidationError, match="duplicate"):
        project_m303_regimen_simplificado_rows(
            projection_refs=(_activity_ref(), _activity_ref()),
            rows=rows,
            orden=(),
            agricultural_authority=annual_orden.agricultural_authority,
            applicable=False,
            calculation_result=None,
            censo_iae_epigraphs=frozenset(),
        )


@pytest.mark.parametrize(
    "revision_id, fact, sub_index",
    [
        ("2023", M303RegimenSimplificadoFact.SUPERFICIE_HORNO_CUARTO_TRIMESTRE, 1),
        ("2024-hasta-08-y-2t", M303RegimenSimplificadoFact.SUPERFICIE_HORNO_DIAS_CUARTO_TRIMESTRE, 1),
        ("2025", M303RegimenSimplificadoFact.SUPERFICIE_HORNO_DIAS_CUARTO_TRIMESTRE, None),
    ],
)
def test_epoch_admission_refuses_real_horno_fact_shapes_outside_the_selected_design(
    revision_id: str,
    fact: M303RegimenSimplificadoFact,
    sub_index: int | None,
) -> None:
    reference = M303RegimenSimplificadoFactProjectionRef(
        projection_kind="m303_regimen_simplificado_fact",
        cohort=M303RegimenSimplificadoCohort.NO_AGRICOLA,
        slot=1,
        fact=fact,
        sub_index=sub_index,
    )
    with pytest.raises(RegistryValidationError, match="not admitted"):
        validate_m303_regimen_simplificado_endpoint_epoch((reference,), revision_id=revision_id)


def test_projection_identity_never_uses_json_serialisation() -> None:
    import inspect

    from .. import m303_regimen_simplificado_projection as module

    source = inspect.getsource(module)
    assert "model_dump_json" not in source
    assert "json.dumps" not in source


def test_declared_quantity_projection_uses_the_exact_annual_orden_ordinal() -> None:
    registry_snapshot = bundled_authority().snapshot("303", filing_year=2026, period="1T")
    scope_decision = M303RegimenSimplificadoScopeDecision(
        scope=M303RegimenSimplificadoScope.REGIMEN_SIMPLIFICADO_EVIDENCE_REQUIRED,
    )
    regimen_snapshot = resolve_m303_regimen_simplificado_snapshot(
        registry_snapshot=registry_snapshot,
        scope_decision=scope_decision,
    )
    annual_orden = regimen_snapshot.orden
    annual_activity = annual_orden.activities[0]
    assert annual_activity.kind == "no_agricola"
    assert annual_activity.iae_epigrafe is not None
    assert len(annual_activity.modulos) == 3
    evidence = FilingEvidenceReference(reference="test:s60:annual-orden-module-ordinal")
    activity = ActividadNoAgricolaSimplificado(
        orden_id=annual_activity.orden_id,
        ejercicio=annual_activity.ejercicio,
        activity_id="test-s60-actividad",
        iae_epigrafe=annual_activity.iae_epigrafe,
        auxiliary_activity_indicator=annual_activity.auxiliary_activity_indicator,
        modulos=tuple(
            EntradaModuloSimplificado(
                module_identity=module.identity,
                declared_quantity=declared_quantity,
                evidence_reference=evidence,
            )
            for module, declared_quantity in zip(
                annual_activity.modulos,
                (Decimal("10"), Decimal("20"), Decimal("30")),
                strict=True,
            )
        ),
        facts=tuple(
            HechoActividadSimplificado(
                fact=M303RegimenSimplificadoFact.CUOTA_DEVENGADA_OPERACIONES_CORRIENTES,
                value=Decimal("1"),
                evidence_reference=evidence,
            )
            for identity in annual_activity.applicable_fact_identities
        ),
        evidence_reference=evidence,
    )

    projected = project_m303_regimen_simplificado_rows(
        projection_refs=(
            M303RegimenSimplificadoModuleProjectionRef(
                projection_kind="m303_regimen_simplificado_module",
                cohort=M303RegimenSimplificadoCohort.NO_AGRICOLA,
                slot=1,
                module_order=2,
                value=M303RegimenSimplificadoModuleValue.DECLARED_QUANTITY,
            ),
        ),
        rows=RegimenSimplificadoFilingRows(ejercicio=annual_activity.ejercicio, activities=(activity,)),
        orden=annual_orden.activities,
        agricultural_authority=annual_orden.agricultural_authority,
        applicable=True,
        calculation_result=calculate_m303_regimen_simplificado_result(
            period=Period.from_year_and_code(2026, "1T"),
            scope_decision=scope_decision,
            rows=RegimenSimplificadoFilingRows(ejercicio=annual_activity.ejercicio, activities=(activity,)),
            regimen_snapshot=regimen_snapshot,
            dana_2024_eligibility=None,
            catalogues=bundled_authority().catalogues,
        ),
        censo_iae_epigraphs=frozenset({annual_activity.iae_epigrafe}),
    )

    assert tuple(field.value for field in projected[0].fields) == (Decimal("20"),)


@pytest.mark.parametrize(("iae_epigrafe", "wire_value"), (("691.9", "6919"), ("722", "722")))
def test_non_agricultural_projection_keeps_the_canonical_iae_discriminator(
    iae_epigrafe: str,
    wire_value: str,
) -> None:
    """The two live same-IAE pairs remain distinct through typed projection refs."""
    registry_snapshot = bundled_authority().snapshot("303", filing_year=2026, period="1T")
    scope_decision = M303RegimenSimplificadoScopeDecision(
        scope=M303RegimenSimplificadoScope.REGIMEN_SIMPLIFICADO_EVIDENCE_REQUIRED,
    )
    regimen_snapshot = resolve_m303_regimen_simplificado_snapshot(
        registry_snapshot=registry_snapshot,
        scope_decision=scope_decision,
    )
    annual_activities = tuple(
        activity for activity in regimen_snapshot.orden.activities if activity.iae_epigrafe == iae_epigrafe
    )
    assert tuple(activity.auxiliary_activity_indicator for activity in annual_activities) == ("1", "2")
    evidence = FilingEvidenceReference(reference="test:s75:canonical-iae-discriminator")
    rows = RegimenSimplificadoFilingRows(
        ejercicio=2026,
        activities=tuple(
            ActividadNoAgricolaSimplificado(
                orden_id=activity.orden_id,
                ejercicio=2026,
                activity_id=activity.orden_id,
                iae_epigrafe=iae_epigrafe,
                auxiliary_activity_indicator=activity.auxiliary_activity_indicator,
                modulos=tuple(
                    EntradaModuloSimplificado(
                        module_identity=module.identity,
                        declared_quantity=Decimal("1"),
                        evidence_reference=evidence,
                    )
                    for module in activity.modulos
                ),
                facts=tuple(
                    HechoActividadSimplificado(
                        fact=M303RegimenSimplificadoFact.CUOTA_DEVENGADA_OPERACIONES_CORRIENTES,
                        value=Decimal("1"),
                        evidence_reference=evidence,
                    )
                    for identity in activity.applicable_fact_identities
                ),
                evidence_reference=evidence,
            )
            for activity in annual_activities
        ),
    )
    projection_refs = tuple(
        M303RegimenSimplificadoActivityProjectionRef(
            projection_kind="m303_regimen_simplificado_activity",
            cohort=M303RegimenSimplificadoCohort.NO_AGRICOLA,
            slot=slot,
            field=field,
        )
        for slot in (1, 2)
        for field in (
            M303RegimenSimplificadoActivityField.IAE_EPIGRAFE,
            M303RegimenSimplificadoActivityField.AUXILIARY_ACTIVITY_INDICATOR,
        )
    )

    projected = project_m303_regimen_simplificado_rows(
        projection_refs=projection_refs,
        rows=rows,
        orden=regimen_snapshot.orden.activities,
        agricultural_authority=regimen_snapshot.orden.agricultural_authority,
        applicable=True,
        calculation_result=calculate_m303_regimen_simplificado_result(
            period=Period.from_year_and_code(2026, "1T"),
            scope_decision=scope_decision,
            rows=rows,
            regimen_snapshot=regimen_snapshot,
            dana_2024_eligibility=None,
            catalogues=bundled_authority().catalogues,
        ),
        censo_iae_epigraphs=frozenset({iae_epigrafe}),
    )

    assert tuple(field.value for field in projected[0].fields) == (wire_value, "1", wire_value, "2")


@pytest.mark.parametrize("iae_epigrafe", ("6919", "691.90", "691.a", "642.1, 2 y 3"))
def test_m303_iae_epigraph_wire_value_refuses_noncanonical_or_unrepresentable_identity(
    iae_epigrafe: str,
) -> None:
    """A DP30302 four-byte IAE field never obtains its value by truncation."""
    with pytest.raises(RegistryValidationError, match="cannot encode"):
        _m303_iae_epigraph_wire_value(iae_epigrafe)


def test_agricultural_projection_refuses_without_official_code_crosswalk() -> None:
    annual_orden = _resolved_annual_orden_for_2026()
    agricultural_authority = annual_orden.agricultural_authority
    evidence = FilingEvidenceReference(reference="test:s73:agricultural-crosswalk")
    agricultural = ActividadAgricolaSimplificado(
        orden_id="test-s73-agricultural",
        ejercicio=annual_orden.ejercicio,
        activity_id="test-s73-agricultural",
        activity_code=agricultural_authority.quota_indexes[0].activity_name,
        facts=(
            HechoActividadSimplificado(
                fact=M303RegimenSimplificadoFact.CUOTA_DEVENGADA,
                value=Decimal("1"),
                evidence_reference=evidence,
            ),
        ),
        evidence_reference=evidence,
    )

    with pytest.raises(IvaValidationError) as caught:
        project_m303_regimen_simplificado_rows(
            projection_refs=(_activity_ref(),),
            rows=RegimenSimplificadoFilingRows(ejercicio=annual_orden.ejercicio, activities=(agricultural,)),
            orden=annual_orden.activities,
            agricultural_authority=agricultural_authority,
            applicable=True,
            calculation_result=None,
            censo_iae_epigraphs=frozenset(),
        )

    assert str(caught.value) == (
        "agricultural annual Orden authority cannot resolve DP30302 activity code: "
        "annual_orden_does_not_publish_dp30302_two_digit_agricultural_crosswalk"
    )
