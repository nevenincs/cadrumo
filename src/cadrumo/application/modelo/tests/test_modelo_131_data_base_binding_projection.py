"""Modelo 131 datos-base fixed-record bindings feed liquidation calculation."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ....adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ....adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ....adapters.persistence.storage.sql import SecureObjectRepository
from ....core import Period
from ....domain.user_profile import ProfileSetupState, UserProfileFact, UserProfileRecord
from ....tests.profile_capsule import seed_test_profile_record
from ....tests.secure_sql import isolated_runtime_profile
from .. import calculate_modelo_revision, create_work_unit

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "31313131-1313-4131-8131-313131313131"
_T0 = datetime(2026, 1, 10, 10, 0, tzinfo=UTC)


@pytest.fixture
def secure_objects(tmp_path: Path) -> Iterator[SecureObjectRepository]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        _store_objective_estimation_profile(profile.repository)
        yield profile.repository


def _store_objective_estimation_profile(objects: SecureObjectRepository) -> None:
    seed_test_profile_record(
        UserProfileRecord(
            setup_state=ProfileSetupState.COMPLETE,
            profile_id=_BUCKET_ID,
            facts=(
                UserProfileFact(path="identity.tax_id", value="12345678Z"),
                UserProfileFact(path="identity.name", value="Rosa"),
                UserProfileFact(path="identity.surnames", value="Modulos"),
                UserProfileFact(path="activities.description", value="transporte por modulos"),
                UserProfileFact(path="tax_residence.ccaa", value="madrid"),
                UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
                UserProfileFact(path="iva.regime", value="SIMPLIFICADO"),
                UserProfileFact(path="iva.m303_regime_composition", value="simplified"),
                UserProfileFact(path="iva.redeme_enrolled", value=False),
                UserProfileFact(path="iva.cash_accounting_regime_enrolled", value=False),
                UserProfileFact(path="iva.voluntary_sii_enrolled", value=False),
                UserProfileFact(path="iva.hydrocarbon_deposit_advance_payment_deduction_entitled", value=False),
                UserProfileFact(path="taxpayer_type.entity_type", value="natural_person"),
                UserProfileFact(path="taxpayer_type.irpf_income_categories", value="actividad_economica"),
                UserProfileFact(path="irpf.estimation_regime", value="objetiva"),
                UserProfileFact(path="censo.activity_start_date", value=date(2025, 1, 1)),
            ),
            created_at=_T0,
            updated_at=_T0,
        ),
    )


def _repos(objects: SecureObjectRepository):
    return (
        WorkUnitCatalogueRepository(objects=objects),
        CalculationRevisionCatalogueRepository(objects=objects),
        BucketEventHistoryRepository(objects=objects),
    )


def _seed_m131_work_unit(work_unit_repository: WorkUnitCatalogueRepository):
    return create_work_unit(
        bucket_id=_BUCKET_ID,
        modelo="131",
        filing_year=2026,
        period=Period.from_year_and_code(2026, "1T"),
        revision_id="2026",
        repository=work_unit_repository,
        clock=_T0,
    )


def test_m131_page1_activity_bindings_feed_data_base_liquidation_without_repurposing_casilla_04(
    secure_objects: SecureObjectRepository,
) -> None:
    wu_repo, cr_repo, bv_repo = _repos(secure_objects)
    work_unit = _seed_m131_work_unit(wu_repo)

    revision = calculate_modelo_revision(
        work_unit.work_unit_id,
        casilla_inputs={"03": Decimal("1000")},
        binding_values={
            "modelo-131.page1.114-130.actividad-1-rendimiento-neto": Decimal("10000"),
            "modelo-131.page1.131-135.actividad-1-porcentaje": Decimal("4"),
            "modelo-131.page1.157-173.actividad-2-rendimiento-neto": Decimal("2000"),
            "modelo-131.page1.179-195.actividad-2-resultado": Decimal("50"),
        },
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=bv_repo,
        clock=_T0,
    )

    assert revision.casilla_values["01"] == Decimal("12000")
    assert revision.casilla_values["02"] == Decimal("450.00")
    assert revision.casilla_values["04"] == Decimal("20.00")
    assert revision.casilla_values["07"] == Decimal("470.00")
    assert revision.casilla_values["10"] == Decimal("470.00")
    assert revision.casilla_values["13"] == Decimal("470.00")
    assert revision.casilla_values["15"] == Decimal("470.00")


def test_m131_dpa_module_rendimiento_can_supply_data_base_casilla_01_when_page1_base_is_absent(
    secure_objects: SecureObjectRepository,
) -> None:
    wu_repo, cr_repo, bv_repo = _repos(secure_objects)
    work_unit = _seed_m131_work_unit(wu_repo)

    revision = calculate_modelo_revision(
        work_unit.work_unit_id,
        casilla_inputs={"03": Decimal("500")},
        binding_values={
            "modelo-131.dpa.136-145.modulo-1-unidades": Decimal("2"),
            "modelo-131.dpa.146-162.modulo-1-rendimiento-neto": Decimal("1600"),
            "modelo-131.page1.136-152.actividad-1-resultado": Decimal("64"),
        },
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=bv_repo,
        clock=_T0,
    )

    assert revision.casilla_values["01"] == Decimal("1600")
    assert revision.casilla_values["02"] == Decimal("64")
    assert revision.casilla_values["04"] == Decimal("10.00")
    assert revision.casilla_values["07"] == Decimal("74.00")
    assert revision.casilla_values["10"] == Decimal("74.00")
    assert revision.casilla_values["13"] == Decimal("74.00")
    assert revision.casilla_values["15"] == Decimal("74.00")


def test_m131_unrelated_fixed_record_manual_binding_is_not_projected_as_a_casilla_input(
    secure_objects: SecureObjectRepository,
) -> None:
    wu_repo, cr_repo, bv_repo = _repos(secure_objects)
    work_unit = _seed_m131_work_unit(wu_repo)

    revision = calculate_modelo_revision(
        work_unit.work_unit_id,
        casilla_inputs={},
        binding_values={"modelo-131.dpa.031-032.vehiculos-afectos": Decimal("9")},
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=bv_repo,
        clock=_T0,
    )

    assert revision.casilla_values["01"] == Decimal("0")
    assert revision.casilla_values["02"] == Decimal("0")
    assert revision.casilla_values["07"] == Decimal("0.00")
    assert revision.casilla_values["15"] == Decimal("0.00")


def test_m131_explicit_casilla_inputs_override_data_base_binding_projection(
    secure_objects: SecureObjectRepository,
) -> None:
    wu_repo, cr_repo, bv_repo = _repos(secure_objects)
    work_unit = _seed_m131_work_unit(wu_repo)

    revision = calculate_modelo_revision(
        work_unit.work_unit_id,
        casilla_inputs={
            "01": Decimal("777"),
            "02": Decimal("33"),
        },
        binding_values={
            "modelo-131.page1.114-130.actividad-1-rendimiento-neto": Decimal("10000"),
            "modelo-131.page1.131-135.actividad-1-porcentaje": Decimal("4"),
        },
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=bv_repo,
        clock=_T0,
    )

    assert revision.casilla_values["01"] == Decimal("777")
    assert revision.casilla_values["02"] == Decimal("33")
    assert revision.casilla_values["07"] == Decimal("33.00")
    assert revision.casilla_values["15"] == Decimal("33.00")
