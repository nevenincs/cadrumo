"""Real-behaviour tests for the M303 simplified-regime row authority."""

from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

from cadrumo.domain.iva import (
    ActividadAgricolaSimplificado,
    ActividadNoAgricolaSimplificado,
    ActividadOrdenAnual,
    EntradaModuloSimplificado,
    HechoActividadSimplificado,
    IvaValidationError,
    ModuloOrdenAnual,
    RegimenSimplificadoFilingRows,
    validate_regimen_simplificado_rows,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _orden_721_2() -> ActividadOrdenAnual:
    return ActividadOrdenAnual(
        ejercicio=2025,
        kind="no_agricola",
        activity_code="autotaxi",
        iae_epigrafe="721.2",
        modulos=(
            ModuloOrdenAnual(
                identity="personal-empleado",
                order=1,
                coefficient=Decimal("2176.99"),
                legal_refs=("orden-hac-1347-2024:anexo-ii:721.2",),
                source_refs=("boe-a-2024-26340",),
            ),
            ModuloOrdenAnual(
                identity="distancia-recorrida",
                order=2,
                coefficient=Decimal("13.42"),
                legal_refs=("orden-hac-1347-2024:anexo-ii:721.2",),
                source_refs=("boe-a-2024-26340",),
            ),
        ),
        applicable_fact_identities=("cuota-devengada-operaciones-corrientes",),
        legal_refs=("orden-hac-1347-2024:anexo-ii:721.2",),
        source_refs=("boe-a-2024-26340",),
    )


def _taxi_row(activity_id: str = "taxi-1", iae_epigrafe: str = "721.2") -> ActividadNoAgricolaSimplificado:
    return ActividadNoAgricolaSimplificado(
        ejercicio=2025,
        activity_id=activity_id,
        iae_epigrafe=iae_epigrafe,
        modulos=(
            EntradaModuloSimplificado(
                module_identity="personal-empleado",
                declared_quantity=Decimal("1"),
                off_form_result=Decimal("2176.99"),
                evidence_reference="calculation:taxi-1:personal",
            ),
            EntradaModuloSimplificado(
                module_identity="distancia-recorrida",
                declared_quantity=Decimal("10000"),
                off_form_result=Decimal("134200"),
                evidence_reference="odometer:taxi-1:2025",
            ),
        ),
        facts=(
            HechoActividadSimplificado(
                identity="cuota-devengada-operaciones-corrientes",
                value=Decimal("136376.99"),
                evidence_reference="calculation:taxi-1:cuota",
            ),
        ),
        evidence_reference="censo:activity:taxi-1",
    )


def test_rows_pack_two_agricultural_and_two_non_agricultural_per_record() -> None:
    agricultural = tuple(
        ActividadAgricolaSimplificado(
            ejercicio=2025,
            activity_id=f"agri-{index}",
            activity_code=f"AG{index}",
            facts=(
                HechoActividadSimplificado(
                    identity="ingresos",
                    value=Decimal("1000"),
                    evidence_reference=f"ledger:agri-{index}",
                ),
            ),
            evidence_reference=f"censo:agri-{index}",
        )
        for index in range(1, 6)
    )
    non_agricultural = tuple(_taxi_row(f"taxi-{index}", f"721.{index}") for index in range(1, 6))
    rows = RegimenSimplificadoFilingRows(ejercicio=2025, activities=agricultural + non_agricultural)

    records = rows.records()

    assert tuple(len(record) for record in records) == (4, 4, 2)
    assert tuple(activity.activity_id for activity in records[0]) == ("agri-1", "agri-2", "taxi-1", "taxi-2")


def test_rows_refuse_unknown_or_wrongly_ordered_annual_modules() -> None:
    row = _taxi_row().model_copy(
        update={"modulos": tuple(reversed(_taxi_row().modulos))},
    )
    rows = RegimenSimplificadoFilingRows(ejercicio=2025, activities=(row,))

    with pytest.raises(IvaValidationError, match="module identities/order"):
        validate_regimen_simplificado_rows(
            rows,
            orden=(_orden_721_2(),),
            applicable=True,
            censo_iae_epigraphs=frozenset({"721.2"}),
        )


def test_rows_refuse_censo_conflict_and_nonapplicable_data() -> None:
    rows = RegimenSimplificadoFilingRows(ejercicio=2025, activities=(_taxi_row(),))

    with pytest.raises(IvaValidationError, match="conflicts with censo"):
        validate_regimen_simplificado_rows(
            rows,
            orden=(_orden_721_2(),),
            applicable=True,
            censo_iae_epigraphs=frozenset({"722"}),
        )
    with pytest.raises(IvaValidationError, match="non-applicable"):
        validate_regimen_simplificado_rows(
            rows,
            orden=(_orden_721_2(),),
            applicable=False,
            censo_iae_epigraphs=frozenset({"721.2"}),
        )


def test_rows_refuse_more_than_six_activities_of_one_kind() -> None:
    activities = tuple(_taxi_row(f"taxi-{index}", f"721.{index}") for index in range(1, 8))

    with pytest.raises(ValidationError, match="at most six"):
        RegimenSimplificadoFilingRows(ejercicio=2025, activities=activities)
