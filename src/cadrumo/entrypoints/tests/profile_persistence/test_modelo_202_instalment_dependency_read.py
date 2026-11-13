"""The dependency read settles a not-owed Modelo 202 instalment exactly as verification does.

Below the LIS art. 40.3 threshold, and without the art. 40.3 election, a Modelo 202
is presented only in an instalment where an ingreso results (Orden HFP/227/2017
art. 1.3). The October and December instalments read the cuota of the Modelo 200
one year back (LIS art. 40.2); when that cuota was 0.00 no ingreso resulted and
no Modelo 202 was presented. Verification settles those instalments at 0.00
through each instalment's own verdict, so the registered dependency read of the
Modelo 200 must show them settled too rather than as missing filings.

Real behaviour throughout: an isolated encrypted profile, the bundled authority,
the production work-unit door, the production dependency composition and
executor, and the verification gate's own clean-state evaluation, with every year
taken from the published support envelope.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path
from uuid import UUID

import pytest

from cadrumo.adapters.persistence.profile.calculation_observations import CalculationObservationRepository
from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import (
    profile_authority_contexts,
    seed_test_profile_record,
)
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from cadrumo.application.calculations.cross_period_models import CrossPeriodCleanStateVerdict
from cadrumo.application.calculations.observations_repository import ObservationSourceKind
from cadrumo.application.modelo.dependency_operation import ModeloDependencyExecutor, ModeloDependencyRequest
from cadrumo.application.modelo.dependency_projection import DependencyEvidenceSnapshot
from cadrumo.application.modelo.verification_cross_period import cross_period_clean_state_verdict_for_work_unit
from cadrumo.application.modelo.work_lifecycle import create_work_unit
from cadrumo.application.operations.public_period import PublicPeriod
from cadrumo.application.user_profile.tests.persona_profile_facts import persona_facts_beneath
from cadrumo.core.authority_grade import RegistryAuthorityGrade
from cadrumo.core.casilla_id import CasillaId, validated_casilla_id
from cadrumo.core.period import Period
from cadrumo.domain.calculations.registry.applicability_modelo202 import derive_modelo_202_modality
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from cadrumo.domain.calculations.registry.tests.authored_editions import filing_year_envelope
from cadrumo.domain.calculations.registry.tests.registry_observations import (
    registry_grounded_modelo_observation,
    revision_id_for_observation,
)
from cadrumo.domain.modelos.work_unit import WorkUnit
from cadrumo.domain.user_profile.values import ProfileSetupState, UserProfileFact, create_user_profile_record
from cadrumo.entrypoints.adapter_composition_work_ports import build_work_lifecycle_ports

from ...modelo_dependency_composition import build_dependency_read_ports
from ..modelo_operator_work_storage import SEEDED_AT

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_BUCKET_ID = "13000000-0000-4000-8000-000000000202"
_PERSONA = "sociedad-limitada"
_MODELO_200 = "200"
_MODELO_202 = "202"
_ANNUAL = "0A"
_CUOTA_BASE_CASILLA = validated_casilla_id("DP200014B:00599")
_CUOTA_INSTALMENT_CASILLA: CasillaId = validated_casilla_id("03")
_LATER_INSTALMENTS = ("2P", "3P")


def _ejercicio() -> int:
    """The settled ejercicio: the one before the horizon, whose Modelo 200 is filed in the horizon."""
    return filing_year_envelope().horizon - 1


def _seed_sociedad_without_the_election(bucket_id: str) -> None:
    """The persona sociedad, below the art. 40.3 threshold, stating it never elected art. 40.3."""
    create_context, _ = profile_authority_contexts()
    seed_test_profile_record(
        create_user_profile_record(
            context=create_context,
            setup_state=ProfileSetupState.COMPLETE,
            profile_id=bucket_id,
            facts=persona_facts_beneath(
                (
                    UserProfileFact(path="taxpayer_type.incn_prior_12_months", value=Decimal("500000")),
                    UserProfileFact(path="taxpayer_type.regimen_entidades_navieras_tonelaje", value=False),
                    UserProfileFact(path="taxpayer_type.pago_fraccionado_art_40_3_elected", value=False),
                    UserProfileFact(
                        path="censo.activity_start_date", value=date(filing_year_envelope().floor - 1, 1, 1)
                    ),
                ),
                persona_id=_PERSONA,
            ),
            created_at=SEEDED_AT,
            updated_at=SEEDED_AT,
        )
    )


def _save(modelo: str, filing_year: int, period: str, casilla_values: dict[CasillaId, Decimal]) -> None:
    repository = CalculationObservationRepository()
    observation = registry_grounded_modelo_observation(
        modelo=modelo,
        filing_year=filing_year,
        period=period,
        casilla_values=casilla_values,
        grade=RegistryAuthorityGrade.CALCULATION,
    )
    repository.save(
        repository.prepare_observation_envelope(
            observation,
            source_kind=ObservationSourceKind.APP_FILING,
            stamped_revision_id=revision_id_for_observation(observation),
        )
    )


def _modelo_200_work(bucket_id: str, operation: PinnedAuthorityOperation) -> WorkUnit:
    period = Period.from_year_and_code(_ejercicio(), _ANNUAL)
    revision = operation.revision_for_context(_MODELO_200, filing_year=_ejercicio(), period=_ANNUAL)
    return create_work_unit(
        bucket_id=bucket_id,
        modelo=_MODELO_200,
        filing_year=_ejercicio(),
        period=period,
        revision_id=str(revision.id),
        ports=build_work_lifecycle_ports(bucket_id=bucket_id),
        clock=SEEDED_AT,
        operation=operation,
    )


def _dependency_read(unit: WorkUnit, operation: PinnedAuthorityOperation) -> tuple[DependencyEvidenceSnapshot, ...]:
    request = ModeloDependencyRequest(
        profile_id=UUID(unit.bucket_id),
        filing_year=unit.filing_year,
        modelo=_MODELO_200,
        period=PublicPeriod(filing_year=unit.filing_year, code=_ANNUAL),
    )
    clean_state = (
        ModeloDependencyExecutor(build_dependency_read_ports)._capture(request, operation).snapshot.clean_state
    )
    assert clean_state is not None
    return tuple(item for item in clean_state.dependencies if item.source_modelo == _MODELO_202)


def _verification_verdict(unit: WorkUnit, operation: PinnedAuthorityOperation) -> CrossPeriodCleanStateVerdict:
    """The clean state verification judges, with the inputs the verification gate passes."""
    ports = build_dependency_read_ports(bucket_id=unit.bucket_id, operation=operation)
    repositories = ports.repositories
    verdict = cross_period_clean_state_verdict_for_work_unit(
        unit,
        observation_repository=repositories.observation,
        filing_repository=repositories.filing,
        calculation_repository=repositories.calculation,
        verification_repository=repositories.verification,
        justificante_repository=repositories.justificante,
        taxpayer_tax_id=ports.profile.tax_id,
        activity_start_date=ports.profile.activity_start_date,
        modelo_202_modality=derive_modelo_202_modality(
            ports.profile, effective_date=date(unit.filing_year, 12, 31)
        ).modality,
        work_unit_repository=repositories.work_unit,
        operation=operation,
        transaction_repository=repositories.transaction,
    )
    assert verdict is not None
    return verdict


def test_the_dependency_read_settles_a_not_owed_instalment_as_verification_does(tmp_path: Path) -> None:
    with (
        isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile,
        bundled_indexed_authority().operation() as operation,
    ):
        _seed_sociedad_without_the_election(profile.bucket_id)
        # The April instalment presented at 54.00; the Modelo 200 one year back, the later base, at 0.00.
        _save(_MODELO_202, _ejercicio(), "1P", {_CUOTA_INSTALMENT_CASILLA: Decimal("54.00")})
        _save(_MODELO_200, _ejercicio() - 1, _ANNUAL, {_CUOTA_BASE_CASILLA: Decimal("0.00")})
        unit = _modelo_200_work(profile.bucket_id, operation)
        read = _dependency_read(unit, operation)
        verified = _verification_verdict(unit, operation)

    later = [item for item in verified.dependencies if item.requirement.source_modelo == _MODELO_202]
    assert {item.requirement.period.registry_token for item in later} >= set(_LATER_INSTALMENTS)
    for item in later:
        if item.requirement.period.registry_token in _LATER_INSTALMENTS:
            assert item.clean
            assert item.modelo_202_instalment_not_owed is not None
    assert sorted((row.period.code, row.clean) for row in read) == sorted(
        (item.requirement.period.registry_token, item.clean) for item in later
    )
    assert all(row.clean and row.blockers == () for row in read if row.period.code in _LATER_INSTALMENTS)
