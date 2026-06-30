"""Real-behavior tests for centralized modelo work addressing facades."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from ....adapters.persistence.storage.sql import SecureObjectRepository
from ....core import Period
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
from ....domain.modelos._repository import WorkUnitCatalogueRepository, upsert_work_unit
from ....domain.modelos._work_unit import WorkUnit
from ....domain.user_profile import UserProfileFact, UserProfileRecord
from ....tests.registry_observations import registry_grounded_observations
from ....tests.secure_sql import isolated_runtime_profile
from ...user_profile import UserProfileLifecycleRepository
from .. import (
    ModeloCalculationRevisionSelector,
    ModeloExactWorkUnitTarget,
    ModeloRevisionPick,
    ModeloVisibleFilingTarget,
    create_work_unit,
    project_modelo_work_target,
    resolve_modelo_revision_pick,
    resolve_modelo_work_unit_id,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_T0 = datetime(2026, 6, 5, 9, 0, 0, tzinfo=UTC)
_ADDRESSING_PROFILE_ID = "13000000-0000-4000-8000-000000000230"
_READY_PROFILE_FACTS: tuple[UserProfileFact, ...] = (
    UserProfileFact(path="identity.tax_id", value="00000000T"),
    UserProfileFact(path="identity.name", value="Test Operator"),
    UserProfileFact(path="identity.surnames", value="Modelo Work"),
    UserProfileFact(path="tax_residence.ccaa", value="madrid"),
    UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
    UserProfileFact(path="activities.description", value="economic activity"),
    UserProfileFact(path="iva.regime", value="GENERAL"),
    UserProfileFact(path="provenance.source", value="test_fixture"),
    UserProfileFact(path="taxpayer_type.entity_type", value="natural_person"),
    UserProfileFact(path="taxpayer_type.irpf_income_categories", value="actividad_economica"),
    UserProfileFact(path="irpf.estimation_regime", value="directa_normal"),
)


def _seed_ready_profile(objects: SecureObjectRepository, *, bucket_id: str) -> None:
    UserProfileLifecycleRepository(bucket_id=bucket_id, objects=objects).save(
        UserProfileRecord(
            profile_id=bucket_id,
            display_name="Modelo work addressing profile",
            facts=_READY_PROFILE_FACTS,
            created_at=_T0,
            updated_at=_T0,
        ),
    )


def _casilla_id(value: object) -> CasillaId:
    try:
        return validated_casilla_id(value, surface="test casilla id")
    except ValueError as exc:
        raise AssertionError(f"test fixture casilla key {value!r} is not a canonical casilla.id") from exc


_OUTPUT_CASILLA: CasillaId = _casilla_id("01")


@pytest.fixture
def addressing_repos(
    tmp_path: Path,
) -> Iterator[tuple[str, WorkUnitCatalogueRepository, CalculationRevisionCatalogueRepository]]:
    """Yield real repositories over one isolated runtime profile."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_ADDRESSING_PROFILE_ID) as profile:
        objects = profile.repository
        _seed_ready_profile(objects, bucket_id=profile.bucket_id)
        yield (
            profile.bucket_id,
            WorkUnitCatalogueRepository(objects=objects),
            CalculationRevisionCatalogueRepository(objects=objects),
        )


def _seed_work_unit(
    repository: WorkUnitCatalogueRepository,
    *,
    bucket_id: str,
    clock: datetime = _T0,
) -> WorkUnit:
    return create_work_unit(
        bucket_id=bucket_id,
        modelo="130",
        filing_year=2026,
        period=Period.from_year_and_code(2026, "1T"),
        revision_id="2019-y-siguientes",
        repository=repository,
        clock=clock,
    )


def _seed_revision(
    repository: CalculationRevisionCatalogueRepository,
    *,
    work_unit_id: str,
    state: CalculationRevisionState,
    created_at: datetime,
    output: Decimal,
) -> CalculationRevision:
    calculation_revision_id = derive_calculation_revision_id(
        work_unit_id=work_unit_id,
        input_values_by_casilla_id={_OUTPUT_CASILLA: str(output)},
        binding_overrides={},
        casilla_values={_OUTPUT_CASILLA: output},
    )
    revision = CalculationRevision(
        calculation_revision_id=calculation_revision_id,
        work_unit_id=work_unit_id,
        state=state,
        input_values_by_casilla_id={_OUTPUT_CASILLA: str(output)},
        casilla_values={_OUTPUT_CASILLA: output},
        observations=registry_grounded_observations(
            modelo="130",
            filing_year=2026,
            period="1T",
            casilla_values={_OUTPUT_CASILLA: output},
        ),
        created_at=created_at,
        updated_at=created_at,
        verified_at=created_at if state is not CalculationRevisionState.BORRADOR else None,
        verified_by="operator" if state is not CalculationRevisionState.BORRADOR else None,
        filed_at=created_at if state is CalculationRevisionState.PRESENTADO else None,
        filed_by="operator" if state is CalculationRevisionState.PRESENTADO else None,
    )
    repository.save(upsert_calculation_revision(repository.load(), revision))
    return revision


def test_visible_and_exact_work_targets_round_trip_to_same_work_unit(
    addressing_repos: tuple[str, WorkUnitCatalogueRepository, CalculationRevisionCatalogueRepository],
) -> None:
    bucket_id, work_repository, calculation_repository = addressing_repos
    work_unit = _seed_work_unit(work_repository, bucket_id=bucket_id)
    draft = _seed_revision(
        calculation_repository,
        work_unit_id=work_unit.work_unit_id,
        state=CalculationRevisionState.BORRADOR,
        created_at=_T0 + timedelta(minutes=1),
        output=Decimal("10"),
    )
    work_repository.save(
        upsert_work_unit(
            work_repository.load(),
            work_unit.model_copy(update={"current_calculation_revision_id": draft.calculation_revision_id}),
        ),
    )

    visible = ModeloVisibleFilingTarget(
        modelo="130",
        filing_year=2026,
        period=Period.from_year_and_code(2026, "1T"),
        bucket_id=bucket_id,
    )
    exact = ModeloExactWorkUnitTarget(work_unit_id=work_unit.work_unit_id, bucket_id=bucket_id)

    assert resolve_modelo_work_unit_id(visible) == work_unit.work_unit_id
    assert resolve_modelo_work_unit_id(exact) == work_unit.work_unit_id

    projected = project_modelo_work_target(visible)
    assert projected.work_unit_id == work_unit.work_unit_id
    assert projected.short_work_unit_id == work_unit.work_unit_id[-12:]
    assert projected.modelo == "130"
    assert projected.filing_year == 2026
    assert projected.period == Period.from_year_and_code(2026, "1T")

    current_pick = resolve_modelo_revision_pick(target=visible, pick=ModeloRevisionPick(default_for="verify"))
    assert current_pick.calculation_revision_id == draft.calculation_revision_id
    assert current_pick.work_unit_id == work_unit.work_unit_id
    assert current_pick.short_calculation_revision_id == draft.calculation_revision_id[-12:]

    explicit_pick = resolve_modelo_revision_pick(
        target=exact,
        pick=ModeloRevisionPick.explicit(draft.calculation_revision_id),
    )
    assert explicit_pick.calculation_revision_id == draft.calculation_revision_id
    assert explicit_pick.work_unit_id == work_unit.work_unit_id
    assert explicit_pick.selector is ModeloCalculationRevisionSelector.EXPLICIT


def test_revision_pick_defaults_are_command_specific_under_one_work_unit(
    addressing_repos: tuple[str, WorkUnitCatalogueRepository, CalculationRevisionCatalogueRepository],
) -> None:
    bucket_id, work_repository, calculation_repository = addressing_repos
    work_unit = _seed_work_unit(work_repository, bucket_id=bucket_id)
    draft = _seed_revision(
        calculation_repository,
        work_unit_id=work_unit.work_unit_id,
        state=CalculationRevisionState.BORRADOR,
        created_at=_T0 + timedelta(minutes=1),
        output=Decimal("10"),
    )
    verified = _seed_revision(
        calculation_repository,
        work_unit_id=work_unit.work_unit_id,
        state=CalculationRevisionState.VERIFICADO_COMPLETO,
        created_at=_T0 + timedelta(minutes=2),
        output=Decimal("20"),
    )
    filed = _seed_revision(
        calculation_repository,
        work_unit_id=work_unit.work_unit_id,
        state=CalculationRevisionState.PRESENTADO,
        created_at=_T0 + timedelta(minutes=3),
        output=Decimal("30"),
    )
    visible = ModeloVisibleFilingTarget(
        modelo="130",
        filing_year=2026,
        period=Period.from_year_and_code(2026, "1T"),
        bucket_id=bucket_id,
    )
    work_repository.save(
        upsert_work_unit(
            work_repository.load(),
            work_unit.model_copy(
                update={
                    "current_calculation_revision_id": draft.calculation_revision_id,
                    "filed_calculation_revision_id": filed.calculation_revision_id,
                },
            ),
        ),
    )

    verify_pick = resolve_modelo_revision_pick(target=visible, pick=ModeloRevisionPick(default_for="verify"))
    export_pick = resolve_modelo_revision_pick(target=visible, pick=ModeloRevisionPick(default_for="export"))

    assert verify_pick.calculation_revision_id == draft.calculation_revision_id
    assert export_pick.calculation_revision_id == filed.calculation_revision_id

    work_repository.save(
        upsert_work_unit(
            work_repository.load(),
            work_unit.model_copy(
                update={
                    "current_calculation_revision_id": verified.calculation_revision_id,
                    "filed_calculation_revision_id": None,
                },
            ),
        ),
    )

    file_pick = resolve_modelo_revision_pick(target=visible, pick=ModeloRevisionPick(default_for="file"))
    assert file_pick.calculation_revision_id == verified.calculation_revision_id
    assert file_pick.work_unit_id == work_unit.work_unit_id
