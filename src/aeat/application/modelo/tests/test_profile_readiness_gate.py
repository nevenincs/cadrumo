"""Application-level profile readiness gate coverage for modelo services."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....core import Modelo, Period
from ....domain.modelos._calculation_repository import (
    CalculationRevisionCatalogueRepository,
    upsert_calculation_revision,
)
from ....domain.modelos._calculation_revision import (
    CalculationRevision,
    CalculationRevisionState,
    derive_calculation_revision_id,
)
from ....domain.modelos._codes import ModeloCode
from ....domain.modelos._repository import WorkUnitCatalogueRepository, upsert_work_unit
from ....domain.modelos._work_unit import WorkUnit, derive_work_unit_id
from ....domain.user_profile import UserProfileFact, UserProfileRecord
from ....tests.secure_sql import isolated_runtime_profile
from ...calculations import IvaWalletDecisionRepository
from ...user_profile import UserProfileLifecycleRepository
from .. import (
    ModeloProfileReadinessError,
    calculate_modelo_revision,
    calculate_modelo_revision_from_bucket_aggregation_with_diagnostics,
    create_work_unit,
    ensure_modelo_work_unit_for_visible_target,
    mark_revision_verificado_completo,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_NOW = datetime(2026, 6, 27, 12, 0, 0, tzinfo=UTC)
_M130_REVISION = "2019-y-siguientes"
_M303_REVISION = "2023-y-siguientes"


def _store_incomplete_profile(bucket_id: str) -> None:
    UserProfileLifecycleRepository(bucket_id=bucket_id).save(
        UserProfileRecord(
            profile_id=bucket_id,
            display_name="Incomplete profile",
            facts=(UserProfileFact(path="identity.tax_id", value="12345678Z"),),
            created_at=_NOW,
            updated_at=_NOW,
        ),
    )


def _store_ready_profile(bucket_id: str, *, activity_start_date: date) -> None:
    UserProfileLifecycleRepository(bucket_id=bucket_id).save(
        UserProfileRecord(
            profile_id=bucket_id,
            display_name="Ready profile",
            facts=(
                UserProfileFact(path="identity.tax_id", value="12345678Z"),
                UserProfileFact(path="identity.name", value="Ready"),
                UserProfileFact(path="identity.surnames", value="Operator"),
                UserProfileFact(path="activities.description", value="design"),
                UserProfileFact(path="tax_residence.ccaa", value="madrid"),
                UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
                UserProfileFact(path="iva.regime", value="GENERAL"),
                UserProfileFact(path="taxpayer_type.entity_type", value="natural_person"),
                UserProfileFact(path="taxpayer_type.irpf_income_categories", value="actividad_economica"),
                UserProfileFact(path="irpf.estimation_regime", value="directa_normal"),
                UserProfileFact(path="censo.activity_start_date", value=activity_start_date),
            ),
            created_at=_NOW,
            updated_at=_NOW,
        ),
    )


def _store_work_unit(
    repository: WorkUnitCatalogueRepository,
    *,
    bucket_id: str,
    modelo: Modelo = Modelo.M303,
    filing_year: int = 2025,
    period_code: str = "1T",
    revision_id: str = _M303_REVISION,
) -> WorkUnit:
    period = Period.from_year_and_code(filing_year, period_code)
    modelo_code = modelo.value
    work_unit = WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id=bucket_id,
            modelo=modelo_code,
            filing_year=filing_year,
            period=period,
            revision_id=revision_id,
        ),
        bucket_id=bucket_id,
        modelo=ModeloCode(modelo_code),
        filing_year=filing_year,
        period=period,
        revision_id=revision_id,
        name=f"{modelo_code}-{filing_year}-{period.registry_token}",
        created_at=_NOW,
        updated_at=_NOW,
    )
    repository.save(upsert_work_unit(repository.load(), work_unit))
    return work_unit


def _store_draft_revision(repository: CalculationRevisionCatalogueRepository, *, work_unit: WorkUnit) -> str:
    revision_id = derive_calculation_revision_id(
        work_unit_id=work_unit.work_unit_id,
        input_values_by_casilla_id={},
        binding_overrides={},
        casilla_values={},
    )
    revision = CalculationRevision(
        calculation_revision_id=revision_id,
        work_unit_id=work_unit.work_unit_id,
        state=CalculationRevisionState.BORRADOR,
        created_at=_NOW,
        updated_at=_NOW,
    )
    repository.save(upsert_calculation_revision(repository.load(), revision))
    return revision_id


def test_create_work_unit_service_refuses_incomplete_profile(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="operator"):
        _store_incomplete_profile("operator")

        with pytest.raises(ModeloProfileReadinessError):
            create_work_unit(
                bucket_id="operator",
                modelo=Modelo.M303.value,
                filing_year=2025,
                period=Period.from_year_and_code(2025, "1T"),
                revision_id=_M303_REVISION,
                clock=_NOW,
            )


def test_mark_verified_service_refuses_existing_work_unit_with_incomplete_profile(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="operator"):
        _store_incomplete_profile("operator")
        work_repository = WorkUnitCatalogueRepository()
        calculation_repository = CalculationRevisionCatalogueRepository()
        work_unit = _store_work_unit(work_repository, bucket_id="operator")
        revision_id = _store_draft_revision(calculation_repository, work_unit=work_unit)

        with pytest.raises(ModeloProfileReadinessError):
            mark_revision_verificado_completo(
                revision_id,
                actor="operator",
                work_unit_repository=work_repository,
                calculation_repository=calculation_repository,
                clock=_NOW,
            )


def test_calculate_service_refuses_existing_work_unit_with_incomplete_profile(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="operator"):
        _store_incomplete_profile("operator")
        repository = WorkUnitCatalogueRepository()
        work_unit = _store_work_unit(repository, bucket_id="operator")

        with pytest.raises(ModeloProfileReadinessError):
            calculate_modelo_revision(
                work_unit.work_unit_id,
                actor="operator",
                casilla_inputs={},
                binding_values={"modelo-303-iva-repercutido-general-cuota": Decimal("100.00")},
                work_unit_repository=repository,
                clock=_NOW,
            )


def test_create_work_unit_service_refuses_pre_activity_m303_and_persists_no_work_unit(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="operator") as profile:
        _store_ready_profile("operator", activity_start_date=date(2026, 5, 1))
        repository = WorkUnitCatalogueRepository(objects=profile.repository)

        with pytest.raises(ModeloProfileReadinessError) as excinfo:
            create_work_unit(
                bucket_id="operator",
                modelo=Modelo.M303.value,
                filing_year=2026,
                period=Period.from_year_and_code(2026, "1T"),
                revision_id=_M303_REVISION,
                repository=repository,
                clock=_NOW,
            )

        assert "pre-activity period" in str(excinfo.value)
        assert excinfo.value.context == {
            "bucket_id": "operator",
            "modelo": "303",
            "filing_year": 2026,
            "period": "1T",
            "activity_start_date": "2026-05-01",
            "period_end_date": "2026-03-31",
        }
        assert len(repository.load()) == 0


def test_create_work_unit_service_refuses_pre_activity_m130_and_persists_no_work_unit(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="operator") as profile:
        _store_ready_profile("operator", activity_start_date=date(2026, 7, 15))
        repository = WorkUnitCatalogueRepository(objects=profile.repository)

        with pytest.raises(ModeloProfileReadinessError) as excinfo:
            create_work_unit(
                bucket_id="operator",
                modelo=Modelo.M130.value,
                filing_year=2026,
                period=Period.from_year_and_code(2026, "2T"),
                revision_id=_M130_REVISION,
                repository=repository,
                clock=_NOW,
            )

        assert "Modelo 130 2026 2T is before" in str(excinfo.value)
        assert "pre-activity period" in str(excinfo.value)
        assert excinfo.value.context == {
            "bucket_id": "operator",
            "modelo": Modelo.M130.value,
            "filing_year": 2026,
            "period": "2T",
            "activity_start_date": "2026-07-15",
            "period_end_date": "2026-06-30",
        }
        assert len(repository.load()) == 0


def test_stale_pre_activity_m303_calculate_refuses_before_wallet_or_revision(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="operator") as profile:
        _store_ready_profile("operator", activity_start_date=date(2026, 5, 1))
        work_repository = WorkUnitCatalogueRepository(objects=profile.repository)
        calculation_repository = CalculationRevisionCatalogueRepository(objects=profile.repository)
        wallet_repository = IvaWalletDecisionRepository(objects=profile.repository)
        work_unit = _store_work_unit(
            work_repository,
            bucket_id="operator",
            filing_year=2026,
            period_code="1T",
        )

        with pytest.raises(ModeloProfileReadinessError) as excinfo:
            calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
                work_unit.work_unit_id,
                actor="operator",
                work_unit_repository=work_repository,
                calculation_repository=calculation_repository,
                iva_compensation_decision_repository=wallet_repository,
                clock=_NOW,
            )

        assert "Modelo 303 2026 1T is before" in str(excinfo.value)
        assert len(calculation_repository.load()) == 0
        assert wallet_repository.list_decisions() == ()


def test_stale_pre_activity_m130_calculate_and_verify_refuse_before_revision_mutation(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="operator") as profile:
        _store_ready_profile("operator", activity_start_date=date(2026, 7, 15))
        work_repository = WorkUnitCatalogueRepository(objects=profile.repository)
        calculation_repository = CalculationRevisionCatalogueRepository(objects=profile.repository)
        work_unit = _store_work_unit(
            work_repository,
            bucket_id="operator",
            modelo=Modelo.M130,
            filing_year=2026,
            period_code="2T",
            revision_id=_M130_REVISION,
        )
        revision_id = _store_draft_revision(calculation_repository, work_unit=work_unit)

        with pytest.raises(ModeloProfileReadinessError) as calculate_exc:
            calculate_modelo_revision(
                work_unit.work_unit_id,
                actor="operator",
                casilla_inputs={},
                binding_values={},
                work_unit_repository=work_repository,
                calculation_repository=calculation_repository,
                clock=_NOW,
            )

        assert "Modelo 130 2026 2T is before" in str(calculate_exc.value)
        assert len(calculation_repository.load()) == 1

        with pytest.raises(ModeloProfileReadinessError) as verify_exc:
            mark_revision_verificado_completo(
                revision_id,
                actor="operator",
                work_unit_repository=work_repository,
                calculation_repository=calculation_repository,
                clock=_NOW,
        )

        assert "Modelo 130 2026 2T is before" in str(verify_exc.value)
        persisted_revision = calculation_repository.load().get(revision_id)
        assert persisted_revision is not None
        assert persisted_revision.state is CalculationRevisionState.BORRADOR


def test_first_active_m303_period_allows_create_and_calculate(tmp_path: Path) -> None:
    period = Period.from_year_and_code(2026, "2T")
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="operator") as profile:
        _store_ready_profile("operator", activity_start_date=date(2026, 5, 1))
        work_repository = WorkUnitCatalogueRepository(objects=profile.repository)
        calculation_repository = CalculationRevisionCatalogueRepository(objects=profile.repository)
        wallet_repository = IvaWalletDecisionRepository(objects=profile.repository)

        work_unit = create_work_unit(
            bucket_id="operator",
            modelo=Modelo.M303.value,
            filing_year=2026,
            period=period,
            revision_id=_M303_REVISION,
            repository=work_repository,
            clock=_NOW,
        )
        result = calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
            work_unit.work_unit_id,
            actor="operator",
            work_unit_repository=work_repository,
            calculation_repository=calculation_repository,
            iva_compensation_decision_repository=wallet_repository,
            clock=_NOW,
        )

        assert result.revision.work_unit_id == work_unit.work_unit_id
        assert tuple(calculation_repository.load().values()) == (result.revision,)
        decisions = wallet_repository.list_decisions()
        assert len(decisions) == 1
        assert decisions[0].target_period == period


def test_visible_target_ensure_refuses_reused_pre_activity_m303_before_rename(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="operator") as profile:
        _store_ready_profile("operator", activity_start_date=date(2026, 5, 1))
        work_repository = WorkUnitCatalogueRepository(objects=profile.repository)
        work_unit = _store_work_unit(
            work_repository,
            bucket_id="operator",
            filing_year=2026,
            period_code="1T",
            revision_id=_M303_REVISION,
        )

        with pytest.raises(ModeloProfileReadinessError) as excinfo:
            ensure_modelo_work_unit_for_visible_target(
                bucket_id="operator",
                modelo=Modelo.M303.value,
                filing_year=2026,
                period=Period.from_year_and_code(2026, "1T"),
                registry_revision_id=_M303_REVISION,
                name="renamed stale work",
                actor="operator",
            )

        assert "pre-activity period" in str(excinfo.value)
        assert tuple(work_repository.load().values()) == (work_unit,)
