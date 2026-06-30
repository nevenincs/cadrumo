"""Application compare-service provenance regression tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from ....core import Period
from ....core.resources import resources
from ....domain.calculations.registry import CasillaId, validated_casilla_id
from ....domain.modelos._calculation_repository import (
    CalculationRevisionCatalogueRepository,
    upsert_calculation_revision,
)
from ....domain.modelos._calculation_revision import (
    CalculationRevision,
    CalculationRevisionState,
    derive_calculation_revision_id,
)
from ....domain.modelos._repository import WorkUnitCatalogueRepository
from ....domain.modelos._work_unit import WorkUnit
from ....domain.user_profile import UserProfileFact, UserProfileRecord
from ....tests.registry_observations import registry_grounded_observations
from ....tests.secure_sql import isolated_runtime_profile
from ...user_profile import UserProfileLifecycleRepository
from .. import create_work_unit
from .._projection import compare_modelo_years

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_T0 = datetime(2026, 6, 25, 9, 0, tzinfo=UTC)
_BUCKET_ID = "13013013-0130-4130-8130-130130130130"
_M130_REVISION_ID = "2019-y-siguientes"


def _casilla_id(value: object) -> CasillaId:
    try:
        return validated_casilla_id(value, surface="projection compare test casilla id")
    except ValueError as exc:
        raise AssertionError(f"projection compare fixture casilla key {value!r} is not a canonical casilla.id") from exc


_M130_INGRESOS_CASILLA: CasillaId = _casilla_id("01")


def _seed_work_unit(
    repository: WorkUnitCatalogueRepository,
    *,
    bucket_id: str,
    filing_year: int,
    clock: datetime,
) -> WorkUnit:
    return create_work_unit(
        bucket_id=bucket_id,
        modelo="130",
        filing_year=filing_year,
        period=Period.from_year_and_code(filing_year, "1T"),
        revision_id=_M130_REVISION_ID,
        repository=repository,
        clock=clock,
    )


def _seed_revision(
    repository: CalculationRevisionCatalogueRepository,
    *,
    work_unit: WorkUnit,
    value: Decimal,
    clock: datetime,
) -> CalculationRevision:
    values = {_M130_INGRESOS_CASILLA: value}
    revision_id = derive_calculation_revision_id(
        work_unit_id=work_unit.work_unit_id,
        input_values_by_casilla_id={_M130_INGRESOS_CASILLA: str(value)},
        binding_overrides={},
        casilla_values=values,
    )
    revision = CalculationRevision(
        calculation_revision_id=revision_id,
        work_unit_id=work_unit.work_unit_id,
        state=CalculationRevisionState.VERIFICADO_COMPLETO,
        input_values_by_casilla_id={_M130_INGRESOS_CASILLA: str(value)},
        binding_overrides={},
        casilla_values=values,
        observations=registry_grounded_observations(
            modelo="130",
            filing_year=work_unit.filing_year,
            period=work_unit.period.registry_token,
            casilla_values=values,
        ),
        created_at=clock,
        updated_at=clock,
        verified_at=clock,
        verified_by="operator",
    )
    repository.save(upsert_calculation_revision(repository.load(), revision))
    return revision


def test_compare_uses_revision_observation_rows_from_registry_snapshot(tmp_path: Path) -> None:
    """Comparison rows must not lose registry-grounded provenance."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        UserProfileLifecycleRepository(bucket_id=profile.bucket_id, objects=profile.repository).save(
            UserProfileRecord(
                profile_id=profile.bucket_id,
                display_name="Modelo compare profile",
                facts=(
                    UserProfileFact(path="identity.tax_id", value="12345678Z"),
                    UserProfileFact(path="identity.name", value="Test"),
                    UserProfileFact(path="identity.surnames", value="Operator"),
                    UserProfileFact(path="activities.description", value="economic activity"),
                    UserProfileFact(path="tax_residence.ccaa", value="madrid"),
                    UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
                    UserProfileFact(path="iva.regime", value="GENERAL"),
                    UserProfileFact(path="taxpayer_type.entity_type", value="natural_person"),
                    UserProfileFact(path="taxpayer_type.irpf_income_categories", value="actividad_economica"),
                    UserProfileFact(path="irpf.estimation_regime", value="directa_normal"),
                    UserProfileFact(path="censo.activity_start_date", value="2020-01-01"),
                ),
                created_at=_T0,
                updated_at=_T0,
            ),
        )
        work_repository = WorkUnitCatalogueRepository(objects=profile.repository)
        calculation_repository = CalculationRevisionCatalogueRepository(objects=profile.repository)
        work_2025 = _seed_work_unit(
            work_repository,
            bucket_id=profile.bucket_id,
            filing_year=2025,
            clock=_T0,
        )
        work_2026 = _seed_work_unit(
            work_repository,
            bucket_id=profile.bucket_id,
            filing_year=2026,
            clock=_T0 + timedelta(minutes=1),
        )
        revision_2025 = _seed_revision(
            calculation_repository,
            work_unit=work_2025,
            value=Decimal("1000.00"),
            clock=_T0 + timedelta(minutes=2),
        )
        revision_2026 = _seed_revision(
            calculation_repository,
            work_unit=work_2026,
            value=Decimal("1500.00"),
            clock=_T0 + timedelta(minutes=3),
        )

        assert revision_2025.observations
        assert revision_2026.observations
        result = compare_modelo_years(modelo="130", years=(2025, 2026))

    row = next(item for item in result.delta_rows if item.casilla_id == _M130_INGRESOS_CASILLA)
    registry_casilla = next(
        item
        for item in resources().modelos.authority.snapshot("130", filing_year=2026, period="1T").revision.casillas
        if item.id == _M130_INGRESOS_CASILLA
    )
    assert row.delta == Decimal("500.00")
    assert row.legal_refs == tuple(registry_casilla.legal_refs)
    assert row.source_refs == tuple(registry_casilla.source_refs)
    assert row.legal_refs, "comparison rows must not emit blank legal_refs"
    assert row.source_refs, "comparison rows must not emit blank source_refs"
