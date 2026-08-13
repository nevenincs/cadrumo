"""Typed reference proofs for Modelo 303 simplified-regime projection."""

from __future__ import annotations

from decimal import Decimal

import pytest

from .....core import (
    M303RegimenSimplificadoActivityField,
    M303RegimenSimplificadoActivityProjectionRef,
    M303RegimenSimplificadoCohort,
    M303RegimenSimplificadoModuleProjectionRef,
    M303RegimenSimplificadoModuleValue,
)
from .....core.resources import resources
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
from .. import (
    RegistryValidationError,
    project_m303_regimen_simplificado_rows,
    resolve_m303_regimen_simplificado_snapshot,
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
    registry_snapshot = resources().modelos.authority.snapshot("303", filing_year=2026, period="1T")
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
            censo_iae_epigraphs=frozenset(),
        )
    with pytest.raises(RegistryValidationError, match="duplicate"):
        project_m303_regimen_simplificado_rows(
            projection_refs=(_activity_ref(), _activity_ref()),
            rows=rows,
            orden=(),
            agricultural_authority=annual_orden.agricultural_authority,
            applicable=False,
            censo_iae_epigraphs=frozenset(),
        )


def test_projection_identity_never_uses_json_serialisation() -> None:
    import inspect

    from .. import _m303_regimen_simplificado_projection as module

    source = inspect.getsource(module)
    assert "model_dump_json" not in source
    assert "json.dumps" not in source


def test_module_projection_uses_the_exact_annual_orden_ordinal() -> None:
    annual_orden = _resolved_annual_orden_for_2026()
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
        modulos=tuple(
            EntradaModuloSimplificado(
                module_identity=module.identity,
                declared_quantity=declared_quantity,
                off_form_result=off_form_result,
                evidence_reference=evidence,
            )
            for module, declared_quantity, off_form_result in zip(
                annual_activity.modulos,
                (Decimal("10"), Decimal("20"), Decimal("30")),
                (Decimal("100"), Decimal("200"), Decimal("300")),
                strict=True,
            )
        ),
        facts=tuple(
            HechoActividadSimplificado(
                identity=identity,
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
            M303RegimenSimplificadoModuleProjectionRef(
                projection_kind="m303_regimen_simplificado_module",
                cohort=M303RegimenSimplificadoCohort.NO_AGRICOLA,
                slot=1,
                module_order=3,
                value=M303RegimenSimplificadoModuleValue.OFF_FORM_RESULT,
            ),
        ),
        rows=RegimenSimplificadoFilingRows(ejercicio=annual_activity.ejercicio, activities=(activity,)),
        orden=annual_orden.activities,
        agricultural_authority=annual_orden.agricultural_authority,
        applicable=True,
        censo_iae_epigraphs=frozenset({annual_activity.iae_epigrafe}),
    )

    assert tuple(field.value for field in projected[0].fields) == (Decimal("20"), Decimal("300"))


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
                identity="test-s73-agricultural-fact",
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
            censo_iae_epigraphs=frozenset(),
        )

    assert str(caught.value) == (
        "agricultural annual Orden authority cannot resolve DP30302 activity code: "
        "annual_orden_does_not_publish_dp30302_two_digit_agricultural_crosswalk"
    )
